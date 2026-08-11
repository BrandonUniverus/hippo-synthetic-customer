"""Verify one generated user's real OIDC and SAML group values without exposing secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from identity.scripts import verify_identity as identity_verifier


def _generated_user(realm: dict[str, Any], username: str) -> dict[str, Any]:
    matches = [user for user in realm.get("users", []) if user.get("username") == username]
    if len(matches) != 1:
        raise identity_verifier.VerificationError(
            f"Generated realm did not contain exactly one enabled user named {username}."
        )
    user = matches[0]
    if user.get("enabled") is not True:
        raise identity_verifier.VerificationError(
            f"Generated user {username} is disabled."
        )
    credentials = user.get("credentials", [])
    if (
        len(credentials) != 1
        or credentials[0].get("type") != "password"
        or not credentials[0].get("value")
    ):
        raise identity_verifier.VerificationError(
            f"Generated user {username} does not have one development credential."
        )
    return user


def _expected_groups(user: dict[str, Any]) -> list[str]:
    groups = user.get("groups")
    if not isinstance(groups, list) or any(
        not isinstance(group, str) or not group.startswith("/") for group in groups
    ):
        raise identity_verifier.VerificationError(
            "Generated user group paths are malformed."
        )
    return sorted(group.removeprefix("/") for group in groups)


def _group_values(value: Any, description: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(group, str) for group in value):
        raise identity_verifier.VerificationError(f"{description} was not a string list.")
    if len(value) != len(set(value)):
        raise identity_verifier.VerificationError(f"{description} contained duplicates.")
    return sorted(value)


def _verify_oidc_groups(
    profile: dict[str, Any],
    context: ssl.SSLContext,
    user: dict[str, Any],
    expected_groups: list[str],
) -> None:
    client = profile.get("clients", {}).get("modern")
    if client is None:
        raise identity_verifier.VerificationError("The Modern OIDC profile is disabled.")
    discovery = identity_verifier._json_request(profile["discoveryEndpoint"], context)
    jwks = identity_verifier._json_request(discovery["jwks_uri"], context)
    redirect_uri = client["redirectUris"][0]
    code_verifier = identity_verifier._base64url(secrets.token_bytes(48))
    code_challenge = identity_verifier._base64url(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    )
    state = identity_verifier._base64url(secrets.token_bytes(18))
    nonce = identity_verifier._base64url(secrets.token_bytes(18))
    authorization_parameters = identity_verifier._authorization_parameters(
        client,
        redirect_uri,
        response_type="code",
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
        prompt="login consent",
        acr_values="1",
    )
    pushed_request = identity_verifier._json_request(
        discovery["pushed_authorization_request_endpoint"],
        context,
        data={**authorization_parameters, "client_secret": client["clientSecret"]},
    )
    authorization_url = (
        f"{profile['authorizationEndpoint']}?"
        + urlencode(
            {
                "client_id": client["clientId"],
                "request_uri": pushed_request["request_uri"],
            }
        )
    )
    opener, login_document = identity_verifier._open_login(
        context,
        authorization_url,
        redirect_uri,
    )
    status, location, response_body = identity_verifier._submit_login(
        opener,
        login_document,
        user["username"],
        user["credentials"][0]["value"],
        redirect_uri,
    )
    if location:
        raise identity_verifier.VerificationError(
            "Modern group-claim login did not stop for consent."
        )
    consent_form = next(
        (
            form
            for form in identity_verifier._forms(response_body)
            if "login-actions/consent" in form.action
        ),
        None,
    )
    if status != 200 or consent_form is None:
        raise identity_verifier.VerificationError(
            "Modern group-claim login did not present consent."
        )
    status, location = identity_verifier._submit_consent(
        opener,
        consent_form,
        profile["baseUrl"],
        redirect_uri,
    )
    if status not in {301, 302, 303, 307, 308} or not location:
        raise identity_verifier.VerificationError(
            "Modern group-claim login did not return an authorization code."
        )
    parameters = parse_qs(urlparse(location).query)
    if (
        parameters.get("state") != [state]
        or parameters.get("iss") != [profile["issuer"]]
        or "code" not in parameters
    ):
        raise identity_verifier.VerificationError(
            "Modern group-claim callback failed state, issuer, or code binding."
        )
    tokens = identity_verifier._json_request(
        profile["tokenEndpoint"],
        context,
        data={
            "grant_type": "authorization_code",
            "client_id": client["clientId"],
            "client_secret": client["clientSecret"],
            "code": parameters["code"][0],
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )
    claims = identity_verifier._verify_id_token(
        tokens["id_token"],
        jwks,
        issuer=profile["issuer"],
        client_id=client["clientId"],
        nonce=nonce,
    )
    if claims.get("sub") != user["id"]:
        raise identity_verifier.VerificationError(
            "Modern group-claim ID token changed the generated subject."
        )
    userinfo = identity_verifier._json_request(
        profile["userinfoEndpoint"],
        context,
        bearer=tokens["access_token"],
    )
    if _group_values(claims.get("groups"), "ID-token groups") != expected_groups:
        raise identity_verifier.VerificationError(
            "ID-token groups did not match the generated membership."
        )
    if _group_values(userinfo.get("groups"), "UserInfo groups") != expected_groups:
        raise identity_verifier.VerificationError(
            "UserInfo groups did not match the generated membership."
        )


def _verify_saml_groups(
    profile: dict[str, Any],
    context: ssl.SSLContext,
    user: dict[str, Any],
    expected_groups: list[str],
) -> None:
    client = profile.get("clients", {}).get("saml")
    if client is None:
        raise identity_verifier.VerificationError("The Standard SAML profile is disabled.")
    metadata = identity_verifier._fetch_saml_metadata(profile, context)
    assertion_consumer_service_url = client["defaultAssertionConsumerServiceUrl"]
    request_id, relay_state, authentication_url = identity_verifier._saml_authentication_url(
        profile,
        assertion_consumer_service_url,
    )
    opener, login_document = identity_verifier._open_login(
        context,
        authentication_url,
        assertion_consumer_service_url,
    )
    status, location, response_body = identity_verifier._submit_login(
        opener,
        login_document,
        user["username"],
        user["credentials"][0]["value"],
        assertion_consumer_service_url,
    )
    if status != 200 or location:
        raise identity_verifier.VerificationError(
            "SP-initiated group-claim SAML login did not return an HTTP-POST form."
        )
    response_document = identity_verifier._saml_callback_form(
        response_body,
        assertion_consumer_service_url,
        relay_state,
    )
    name_id_attribute = f"saml.persistent.name.id.for.{client['entityId']}"
    name_id_values = user.get("attributes", {}).get(name_id_attribute, [])
    if len(name_id_values) != 1:
        raise identity_verifier.VerificationError(
            "Generated user did not contain one Standard SAML persistent NameID."
        )
    result = identity_verifier._validate_saml_response(
        response_document,
        profile,
        metadata,
        assertion_consumer_service_url=assertion_consumer_service_url,
        request_id=request_id,
        expected_user={
            "samlNameId": name_id_values[0],
            "expectedAttributes": {
                "groups": expected_groups,
                "eem_permission_profiles": user.get("attributes", {}).get(
                    "eem_permission_profiles",
                    [],
                ),
            },
        },
    )
    if _group_values(result.attributes.get("groups"), "SAML groups") != expected_groups:
        raise identity_verifier.VerificationError(
            "SAML groups did not match the generated membership."
        )


def verify_group_claims(
    connection_path: Path,
    realm_path: Path,
    ca_path: Path,
    username: str,
) -> list[str]:
    profile = json.loads(connection_path.read_text(encoding="utf-8"))
    realm = json.loads(realm_path.read_text(encoding="utf-8"))
    if realm.get("realm") != profile.get("realm"):
        raise identity_verifier.VerificationError(
            "Generated realm and connection profile identify different realms."
        )
    user = _generated_user(realm, username)
    expected_groups = _expected_groups(user)
    context = ssl.create_default_context(cafile=str(ca_path))
    _verify_oidc_groups(profile, context, user, expected_groups)
    _verify_saml_groups(profile, context, user, expected_groups)
    return expected_groups


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify one generated Northlake user's real OIDC and SAML group values."
    )
    parser.add_argument("--connection", required=True, type=Path)
    parser.add_argument("--realm", required=True, type=Path)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--username", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        groups = verify_group_claims(
            args.connection.resolve(),
            args.realm.resolve(),
            args.ca_file.resolve(),
            args.username,
        )
    except (
        OSError,
        HTTPError,
        URLError,
        KeyError,
        json.JSONDecodeError,
        identity_verifier.VerificationError,
    ) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    group_summary = ", ".join(groups) if groups else "(none)"
    print(
        f"[OK] {args.username} emitted matching OIDC ID-token, UserInfo, and SAML groups: "
        f"{group_summary}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
