"""Verify two concurrent Northlake OIDC/SAML realms and their isolation contract."""

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
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from identity.scripts import verify_identity as identity_verifier
from identity.scripts.verify_oidc_baseline import _install_host_override


NORTHLAKE_CUSTOM_CLAIMS = {
    "groups",
    "synthetic_user_id",
    "primary_company_id",
    "title",
    "synthetic_status",
    "eem_company_ids",
    "eem_permission_profiles",
}


def _admin_token(profile: dict[str, Any], context: ssl.SSLContext) -> str:
    return identity_verifier._json_request(
        f"{profile['baseUrl']}/realms/master/protocol/openid-connect/token",
        context,
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": profile["admin"]["username"],
            "password": profile["admin"]["password"],
        },
    )["access_token"]


def _verify_admin_shape(profile: dict[str, Any], context: ssl.SSLContext) -> None:
    token = _admin_token(profile, context)
    realm_path = f"{profile['baseUrl']}/admin/realms/{profile['realm']}"
    clients = identity_verifier._json_request(
        f"{realm_path}/clients",
        context,
        bearer=token,
    )
    clients_by_id = {client["clientId"]: client for client in clients}
    modern_profile = profile["clients"]["modern"]
    saml_profile = profile["clients"]["saml"]
    for expected in (modern_profile, saml_profile):
        actual = clients_by_id.get(expected["clientId"])
        if actual is None:
            raise identity_verifier.VerificationError(
                f"{profile['realm']} did not install client {expected['clientId']}."
            )
        if set(actual.get("redirectUris", [])) != set(expected["redirectUris"]):
            raise identity_verifier.VerificationError(
                f"{profile['realm']} client redirect URIs drifted."
            )

    modern = clients_by_id[modern_profile["clientId"]]
    if (
        modern.get("protocol") != "openid-connect"
        or modern.get("implicitFlowEnabled")
        or not modern.get("standardFlowEnabled")
        or modern.get("attributes", {}).get("pkce.code.challenge.method") != "S256"
    ):
        raise identity_verifier.VerificationError(
            f"{profile['realm']} modern OIDC client drifted from code plus PKCE."
        )
    required_par = modern_profile["parBehavior"] == "Require"
    if (
        modern.get("attributes", {}).get("pushed.authorization.request.required")
        != str(required_par).lower()
    ):
        raise identity_verifier.VerificationError(
            f"{profile['realm']} OIDC PAR enforcement drifted."
        )

    client_scopes = identity_verifier._json_request(
        f"{realm_path}/client-scopes",
        context,
        bearer=token,
    )
    northlake_scope = next(
        (scope for scope in client_scopes if scope.get("name") == "northlake"),
        None,
    )
    if northlake_scope is None:
        raise identity_verifier.VerificationError(
            f"{profile['realm']} omitted the Northlake client scope."
        )
    scope_mappers = identity_verifier._json_request(
        f"{realm_path}/client-scopes/{northlake_scope['id']}/protocol-mappers/models",
        context,
        bearer=token,
    )
    if {mapper["name"] for mapper in scope_mappers} != set(modern_profile["allowedClaims"]):
        raise identity_verifier.VerificationError(
            f"{profile['realm']} OIDC claim shape drifted."
        )

    saml = clients_by_id[saml_profile["clientId"]]
    saml_attributes = saml.get("attributes", {})
    if (
        saml.get("protocol") != "saml"
        or saml_attributes.get("saml.server.signature") != "true"
        or saml_attributes.get("saml.assertion.signature") != "true"
        or saml_attributes.get("saml.client.signature") != "false"
        or saml_attributes.get("saml.encrypt") != "false"
    ):
        raise identity_verifier.VerificationError(
            f"{profile['realm']} Standard SAML client drifted."
        )
    if {mapper["name"] for mapper in saml.get("protocolMappers", [])} != set(
        saml_profile["allowedClaims"]
    ):
        raise identity_verifier.VerificationError(
            f"{profile['realm']} SAML claim shape drifted."
        )
    print(
        f"[OK] {profile['realm']} installed one bounded Modern OIDC and one Standard SAML "
        "registration with the selected claim shape."
    )


def _verify_oidc_login(
    profile: dict[str, Any],
    context: ssl.SSLContext,
    discovery: dict[str, Any],
    jwks: dict[str, Any],
) -> dict[str, Any]:
    client = profile["clients"]["modern"]
    redirect_uri = client["redirectUris"][0]
    code_verifier = identity_verifier._base64url(secrets.token_bytes(48))
    code_challenge = identity_verifier._base64url(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    )
    state = identity_verifier._base64url(secrets.token_bytes(18))
    nonce = identity_verifier._base64url(secrets.token_bytes(18))
    parameters = identity_verifier._authorization_parameters(
        client,
        redirect_uri,
        response_type="code",
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
        prompt="login",
    )
    if client["parBehavior"] == "Require":
        pushed = identity_verifier._json_request(
            discovery["pushed_authorization_request_endpoint"],
            context,
            data={**parameters, "client_secret": client["clientSecret"]},
        )
        if not pushed.get("request_uri"):
            raise identity_verifier.VerificationError(
                f"{profile['realm']} PAR did not return a request URI."
            )
        authorization_url = (
            f"{profile['authorizationEndpoint']}?"
            + urlencode(
                {
                    "client_id": client["clientId"],
                    "request_uri": pushed["request_uri"],
                }
            )
        )
    else:
        authorization_url = f"{profile['authorizationEndpoint']}?{urlencode(parameters)}"

    opener, login_document = identity_verifier._open_login(
        context,
        authorization_url,
        redirect_uri,
    )
    status, location, response_body = identity_verifier._submit_login(
        opener,
        login_document,
        profile["testUsers"]["active"]["username"],
        profile["testUsers"]["password"],
        redirect_uri,
    )
    if not location:
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
                f"{profile['realm']} login did not return a callback or consent form."
            )
        status, location = identity_verifier._submit_consent(
            opener,
            consent_form,
            profile["baseUrl"],
            redirect_uri,
        )
    if status not in {301, 302, 303, 307, 308} or not location:
        raise identity_verifier.VerificationError(
            f"{profile['realm']} authorization code login did not redirect."
        )
    callback = parse_qs(urlparse(location).query)
    if (
        callback.get("state") != [state]
        or callback.get("iss") != [profile["issuer"]]
        or "code" not in callback
    ):
        raise identity_verifier.VerificationError(
            f"{profile['realm']} callback did not bind state, issuer, and code."
        )
    tokens = identity_verifier._json_request(
        profile["tokenEndpoint"],
        context,
        data={
            "grant_type": "authorization_code",
            "client_id": client["clientId"],
            "client_secret": client["clientSecret"],
            "code": callback["code"][0],
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )
    if not {"access_token", "id_token", "refresh_token"}.issubset(tokens):
        raise identity_verifier.VerificationError(
            f"{profile['realm']} token response was incomplete."
        )
    id_claims = identity_verifier._verify_id_token(
        tokens["id_token"],
        jwks,
        issuer=profile["issuer"],
        client_id=client["clientId"],
        nonce=nonce,
    )
    if id_claims.get("sub") != profile["testUsers"]["active"]["subject"]:
        raise identity_verifier.VerificationError(
            f"{profile['realm']} returned an unexpected external subject."
        )
    userinfo = identity_verifier._json_request(
        profile["userinfoEndpoint"],
        context,
        bearer=tokens["access_token"],
    )
    for claim in ("sub", "preferred_username", "email"):
        if claim not in userinfo:
            raise identity_verifier.VerificationError(
                f"{profile['realm']} UserInfo omitted {claim}."
            )
    if userinfo["sub"] != id_claims["sub"]:
        raise identity_verifier.VerificationError(
            f"{profile['realm']} UserInfo and ID token subjects differed."
        )
    allowed_claims = set(client["allowedClaims"])
    unexpected = sorted((set(userinfo) & NORTHLAKE_CUSTOM_CLAIMS) - allowed_claims)
    if unexpected:
        raise identity_verifier.VerificationError(
            f"{profile['realm']} emitted out-of-shape OIDC claim {unexpected[0]}."
        )
    expected_attributes = profile["testUsers"]["active"]["expectedAttributes"]
    for claim in allowed_claims:
        expected = expected_attributes[claim]
        actual = userinfo.get(claim)
        if isinstance(expected, list):
            if sorted(str(value) for value in expected) != sorted(
                str(value) for value in (actual if isinstance(actual, list) else [actual])
            ):
                raise identity_verifier.VerificationError(
                    f"{profile['realm']} OIDC claim {claim} did not match."
                )
        elif str(actual) != str(expected):
            raise identity_verifier.VerificationError(
                f"{profile['realm']} OIDC claim {claim} did not match."
            )

    invalid_redirect = "https://attacker.example/oidc/callback"
    invalid_url = identity_verifier._authorization_url(
        profile,
        client,
        invalid_redirect,
        response_type="code",
        state="invalid-state",
        nonce="invalid-nonce",
        code_challenge=code_challenge,
    )
    try:
        urlopen(invalid_url, context=context, timeout=20)
        raise identity_verifier.VerificationError(
            f"{profile['realm']} accepted an unregistered OIDC redirect."
        )
    except HTTPError as error:
        if error.headers.get("Location", "").startswith(invalid_redirect) or error.code != 400:
            raise identity_verifier.VerificationError(
                f"{profile['realm']} did not safely reject an invalid OIDC redirect."
            ) from error
    print(
        f"[OK] {profile['realm']} completed code plus PKCE login with issuer-bound callback, "
        "selected claims, refresh token, and exact redirect rejection."
    )
    return {"sub": id_claims["sub"], "userinfo": userinfo}


def _signing_key_fingerprints(jwks: dict[str, Any]) -> set[str]:
    fingerprints = set()
    for key in jwks.get("keys", []):
        if key.get("use") == "sig" and key.get("kty") == "RSA":
            fingerprints.add(
                hashlib.sha256(
                    f"{key.get('n', '')}.{key.get('e', '')}".encode("ascii")
                ).hexdigest()
            )
    return fingerprints


def verify(connection_paths: list[Path], ca_path: Path) -> None:
    if len(connection_paths) != 2:
        raise identity_verifier.VerificationError("Exactly two lab connection profiles are required.")
    profiles = [json.loads(path.read_text(encoding="utf-8")) for path in connection_paths]
    context = ssl.create_default_context(cafile=str(ca_path))
    results: list[dict[str, Any]] = []
    key_sets: list[set[str]] = []
    saml_certificate_sets: list[set[str]] = []
    for profile in profiles:
        if set(profile["clients"]) != {"modern", "saml"}:
            raise identity_verifier.VerificationError(
                f"{profile['realm']} did not expose exactly one OIDC and one SAML test client."
            )
        discovery = identity_verifier._json_request(profile["discoveryEndpoint"], context)
        if discovery.get("issuer") != profile["issuer"]:
            raise identity_verifier.VerificationError(
                f"{profile['realm']} discovery issuer drifted."
            )
        jwks = identity_verifier._json_request(discovery["jwks_uri"], context)
        fingerprints = _signing_key_fingerprints(jwks)
        if not fingerprints:
            raise identity_verifier.VerificationError(
                f"{profile['realm']} JWKS had no RSA signing key."
            )
        metadata = identity_verifier._fetch_saml_metadata(profile, context)
        if metadata.entity_id != profile["issuer"] or not metadata.signing_certificates:
            raise identity_verifier.VerificationError(
                f"{profile['realm']} SAML metadata identity or signing keys drifted."
            )
        key_sets.append(fingerprints)
        saml_certificate_sets.append(
            {
                hashlib.sha256(certificate.encode("ascii")).hexdigest()
                for certificate in metadata.signing_certificates
            }
        )
        _verify_admin_shape(profile, context)
        results.append(_verify_oidc_login(profile, context, discovery, jwks))
        identity_verifier._verify_saml(profile, context)

    if profiles[0]["issuer"] == profiles[1]["issuer"]:
        raise identity_verifier.VerificationError("The two lab realms shared one OIDC issuer.")
    if key_sets[0] & key_sets[1]:
        raise identity_verifier.VerificationError("The two lab realms shared an OIDC signing key.")
    if saml_certificate_sets[0] & saml_certificate_sets[1]:
        raise identity_verifier.VerificationError("The two lab realms shared a SAML signing key.")
    if len({profile["clients"]["modern"]["providerKey"] for profile in profiles}) != 2:
        raise identity_verifier.VerificationError("The two lab realms shared an OIDC provider key.")
    if len({profile["clients"]["saml"]["providerKey"] for profile in profiles}) != 2:
        raise identity_verifier.VerificationError("The two lab realms shared a SAML provider key.")
    if len({profile["clients"]["saml"]["clientId"] for profile in profiles}) != 2:
        raise identity_verifier.VerificationError("The two lab realms shared a SAML SP entity ID.")
    if set(profiles[0]["clients"]["saml"]["redirectUris"]) & set(
        profiles[1]["clients"]["saml"]["redirectUris"]
    ):
        raise identity_verifier.VerificationError(
            "The two lab realms shared a provider-specific SAML callback."
        )
    shared_expected = all(
        profile.get("scenario", {}).get("sharedExternalSubject") for profile in profiles
    )
    subjects_equal = results[0]["sub"] == results[1]["sub"]
    if subjects_equal != shared_expected:
        raise identity_verifier.VerificationError(
            "The cross-realm external-subject relationship did not match the selected scenario."
        )
    print(
        "[OK] Two concurrent realms expose distinct OIDC issuers, SAML IdP entities, "
        "OIDC signing keys, SAML signing keys, provider keys, and provider-specific SAML "
        "callback registrations."
    )
    print(
        "[OK] Equal external subjects remain issuer-qualified across both live providers."
        if subjects_equal
        else "[OK] The isolation preset emitted distinct external subjects across both providers."
    )
    print(
        "[GAP] Northlake cannot prove EnergyHippo's concurrent provider display, selection, "
        "or issuer-subject database isolation without the installed EnergyHippo path."
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify two concurrent Northlake lab realms.")
    parser.add_argument("--connection", action="append", required=True, type=Path)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--resolve-host")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        _install_host_override(args.resolve_host)
        verify([path.resolve() for path in args.connection], args.ca_file.resolve())
    except (
        OSError,
        HTTPError,
        URLError,
        identity_verifier.VerificationError,
        KeyError,
        AttributeError,
        json.JSONDecodeError,
    ) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print("[OK] Northlake concurrent identity scenario verification completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
