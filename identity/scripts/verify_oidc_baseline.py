"""Focused live verification for configurable Northlake Modern and Legacy OIDC profiles."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import socket
import ssl
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from identity.scripts import verify_identity as identity_verifier


class LogoutPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.continue_url: str | None = None
        self.frontchannel_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("id") == "continue":
            self.continue_url = attributes.get("href")
        elif tag == "iframe" and attributes.get("src"):
            self.frontchannel_urls.append(attributes["src"] or "")


def _install_host_override(value: str | None) -> None:
    if value is None:
        return
    source, separator, target = value.partition("=")
    if (
        separator != "="
        or source != "localhost"
        or not target
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for character in target)
    ):
        raise identity_verifier.VerificationError(
            "Host override must use the localhost=container-name form."
        )
    original_getaddrinfo = socket.getaddrinfo

    def overridden_getaddrinfo(
        host: str | bytes | None,
        port: str | int | None,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> list[tuple[Any, ...]]:
        resolved_host = target if host == source else host
        return original_getaddrinfo(resolved_host, port, family, type, proto, flags)

    socket.getaddrinfo = overridden_getaddrinfo


def _client_headers(
    client: dict[str, Any],
    content_type: str = "application/x-www-form-urlencoded",
) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": content_type,
        "User-Agent": identity_verifier.VERIFIER_USER_AGENT,
    }
    if client["tokenEndpointAuthMethod"] == "ClientSecretBasic":
        encoded_client_id = quote(client["clientId"], safe="")
        encoded_secret = quote(client["clientSecret"], safe="")
        credential = base64.b64encode(
            f"{encoded_client_id}:{encoded_secret}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {credential}"
    return headers


def _client_form_values(
    values: dict[str, str],
    client: dict[str, Any],
) -> dict[str, str]:
    form = dict(values)
    if client["tokenEndpointAuthMethod"] == "ClientSecretPost":
        form["client_id"] = client["clientId"]
        form["client_secret"] = client["clientSecret"]
    return form


def _client_json_request(
    url: str,
    context: ssl.SSLContext,
    values: dict[str, str],
    client: dict[str, Any],
) -> Any:
    request = Request(
        url,
        data=urlencode(_client_form_values(values, client)).encode("utf-8"),
        headers=_client_headers(client),
    )
    with urlopen(request, context=context, timeout=20) as response:
        return json.load(response)


def _client_empty_request(
    url: str,
    context: ssl.SSLContext,
    values: dict[str, str],
    client: dict[str, Any],
) -> int:
    request = Request(
        url,
        data=urlencode(_client_form_values(values, client)).encode("utf-8"),
        headers=_client_headers(client),
    )
    with urlopen(request, context=context, timeout=20) as response:
        response.read()
        return response.status


def _authorization_url(
    profile: dict[str, Any],
    discovery: dict[str, Any],
    context: ssl.SSLContext,
    client: dict[str, Any],
    parameters: dict[str, str],
) -> tuple[str, bool]:
    par_behavior = client["parBehavior"]
    if par_behavior == "Disable":
        return f"{profile['authorizationEndpoint']}?{urlencode(parameters)}", False
    par_endpoint = discovery.get("pushed_authorization_request_endpoint")
    if not par_endpoint:
        raise identity_verifier.VerificationError(
            f"{par_behavior} selected but discovery did not publish PAR."
        )
    pushed = _client_json_request(par_endpoint, context, parameters, client)
    if not pushed.get("request_uri") or pushed.get("expires_in", 0) <= 0:
        raise identity_verifier.VerificationError(
            "PAR did not return a usable request URI and lifetime."
        )
    return (
        f"{profile['authorizationEndpoint']}?"
        + urlencode(
            {
                "client_id": client["clientId"],
                "request_uri": pushed["request_uri"],
            }
        ),
        True,
    )


def _callback_after_login(
    opener: Any,
    profile: dict[str, Any],
    client: dict[str, Any],
    login_document: bytes,
    redirect_uri: str,
) -> str:
    status, location, response_body = identity_verifier._submit_login(
        opener,
        login_document,
        profile["testUsers"]["active"]["username"],
        profile["testUsers"]["password"],
        redirect_uri,
    )
    if client["consentRequired"]:
        if location:
            raise identity_verifier.VerificationError(
                "Modern profile skipped its configured provider consent."
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
                "Modern profile did not present its configured provider consent."
            )
        status, location = identity_verifier._submit_consent(
            opener,
            consent_form,
            profile["baseUrl"],
            redirect_uri,
        )
    if status not in {301, 302, 303, 307, 308} or not location:
        raise identity_verifier.VerificationError(
            "Modern profile did not return an authorization-code callback."
        )
    return location


def _expect_invalid_grant(action: Any, description: str) -> None:
    try:
        action()
    except HTTPError as error:
        try:
            payload = json.loads(error.read() or b"{}")
        except json.JSONDecodeError as parse_error:
            raise identity_verifier.VerificationError(
                f"{description} did not return a JSON OAuth error."
            ) from parse_error
        if error.code == 400 and payload.get("error") == "invalid_grant":
            return
        raise identity_verifier.VerificationError(
            f"{description} did not return invalid_grant."
        ) from error
    raise identity_verifier.VerificationError(f"{description} was accepted.")


def _verify_rp_logout(
    opener: Any,
    profile: dict[str, Any],
    client: dict[str, Any],
    id_token: str,
    post_logout_uri: str,
) -> str:
    logout_state = identity_verifier._base64url(secrets.token_bytes(12))
    logout_url = (
        f"{profile['logoutEndpoint']}?"
        + urlencode(
            {
                "client_id": client["clientId"],
                "id_token_hint": id_token,
                "post_logout_redirect_uri": post_logout_uri,
                "state": logout_state,
            }
        )
    )
    try:
        with opener.open(
            Request(logout_url, headers={"User-Agent": identity_verifier.VERIFIER_USER_AGENT}),
            timeout=20,
        ) as response:
            if response.status != 200:
                raise identity_verifier.VerificationError(
                    f"RP-initiated logout returned HTTP {response.status}."
                )
            parser = LogoutPageParser()
            parser.feed(response.read().decode("utf-8", errors="replace"))
            if not parser.continue_url or not parser.frontchannel_urls:
                raise identity_verifier.VerificationError(
                    "RP-initiated logout returned no callback or front-channel notification."
                )
            location = parser.continue_url
            completion = "front-channel notification page"
    except HTTPError as error:
        if error.code not in {301, 302, 303, 307, 308}:
            raise
        location = error.headers.get("Location", "")
        completion = "direct redirect"

    parsed_location = urlparse(location)
    location_without_query = parsed_location._replace(query="", fragment="").geturl()
    if location_without_query != post_logout_uri:
        raise identity_verifier.VerificationError(
            "RP-initiated logout did not return the exact registered callback."
        )
    if parse_qs(parsed_location.query).get("state") != [logout_state]:
        raise identity_verifier.VerificationError(
            "RP-initiated logout did not preserve state."
        )
    return completion


def _verify_modern(
    profile: dict[str, Any],
    discovery: dict[str, Any],
    jwks: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    client = profile["clients"]["modern"]
    redirect_uri = client["redirectUris"][0]
    post_logout_uri = client["postLogoutRedirectUris"][0]
    code_verifier = identity_verifier._base64url(secrets.token_bytes(48))
    challenge = identity_verifier._base64url(
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
        code_challenge=challenge,
        prompt="login consent" if client["consentRequired"] else "login",
        acr_values="1",
    )
    authorization_url, used_par = _authorization_url(
        profile,
        discovery,
        context,
        client,
        parameters,
    )
    opener, login_document = identity_verifier._open_login(
        context,
        authorization_url,
        (redirect_uri, post_logout_uri),
    )
    callback_location = _callback_after_login(
        opener,
        profile,
        client,
        login_document,
        redirect_uri,
    )
    callback = parse_qs(urlparse(callback_location).query)
    if (
        callback.get("state") != [state]
        or callback.get("iss") != [profile["issuer"]]
        or "code" not in callback
    ):
        raise identity_verifier.VerificationError(
            "Modern callback failed state, issuer, or authorization-code binding."
        )
    tokens = _client_json_request(
        profile["tokenEndpoint"],
        context,
        {
            "grant_type": "authorization_code",
            "code": callback["code"][0],
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        client,
    )
    if not {"access_token", "id_token", "refresh_token"}.issubset(tokens):
        raise identity_verifier.VerificationError(
            "Modern token response omitted access, ID, or refresh token."
        )
    claims = identity_verifier._verify_id_token(
        tokens["id_token"],
        jwks,
        issuer=profile["issuer"],
        client_id=client["clientId"],
        nonce=nonce,
    )
    if claims.get("sub") != profile["testUsers"]["active"]["subject"]:
        raise identity_verifier.VerificationError("Modern ID token changed the synthetic subject.")
    _, access_claims, _, _ = identity_verifier._decode_jwt(tokens["access_token"])
    access_lifetime = access_claims.get("exp", 0) - access_claims.get("iat", 0)
    expected_lifetime = profile["oidcConfiguration"]["accessTokenLifetimeSeconds"]
    if abs(access_lifetime - expected_lifetime) > 2:
        raise identity_verifier.VerificationError(
            f"Access token lifetime was {access_lifetime}; expected {expected_lifetime}."
        )
    userinfo = identity_verifier._json_request(
        profile["userinfoEndpoint"],
        context,
        bearer=tokens["access_token"],
    )
    if (
        userinfo.get("sub") != profile["testUsers"]["active"]["subject"]
        or userinfo.get("preferred_username")
        != profile["testUsers"]["active"]["username"]
    ):
        raise identity_verifier.VerificationError(
            "UserInfo changed the authenticated synthetic identity."
        )
    if "northlake" in client["scope"].split() and "groups" not in userinfo:
        raise identity_verifier.VerificationError(
            "UserInfo omitted Northlake claims requested by the configured scope."
        )

    rotated = _client_json_request(
        profile["tokenEndpoint"],
        context,
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        client,
    )
    if not {"access_token", "id_token", "refresh_token"}.issubset(rotated):
        raise identity_verifier.VerificationError("Refresh did not return a complete token set.")
    if rotated["refresh_token"] == tokens["refresh_token"]:
        raise identity_verifier.VerificationError("Refresh token was not rotated.")
    refreshed_claims = identity_verifier._verify_id_token(
        rotated["id_token"],
        jwks,
        issuer=profile["issuer"],
        client_id=client["clientId"],
        nonce=None,
    )
    if refreshed_claims.get("sub") != profile["testUsers"]["active"]["subject"]:
        raise identity_verifier.VerificationError(
            "Refreshed ID token changed the synthetic subject."
        )
    _expect_invalid_grant(
        lambda: _client_json_request(
            profile["tokenEndpoint"],
            context,
            {
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
            },
            client,
        ),
        "Rotated-out refresh token",
    )
    revocation_status = _client_empty_request(
        discovery["revocation_endpoint"],
        context,
        {
            "token": rotated["refresh_token"],
            "token_type_hint": "refresh_token",
        },
        client,
    )
    if revocation_status != 200:
        raise identity_verifier.VerificationError(
            f"Refresh-token revocation returned HTTP {revocation_status}."
        )
    _expect_invalid_grant(
        lambda: _client_json_request(
            profile["tokenEndpoint"],
            context,
            {
                "grant_type": "refresh_token",
                "refresh_token": rotated["refresh_token"],
            },
            client,
        ),
        "Revoked refresh token",
    )

    logout_completion = _verify_rp_logout(
        opener,
        profile,
        client,
        rotated["id_token"],
        post_logout_uri,
    )

    print(
        "[OK] Modern OIDC: "
        f"configuration={client['configurationMode']}, "
        f"PAR={client['parBehavior']} ({'used' if used_par else 'not used'}), "
        f"token auth={client['tokenEndpointAuthMethod']}, scopes={client['scope']}; "
        "code + PKCE S256, signed ID token, UserInfo, refresh rotation/revocation, "
        f"and RP-initiated logout ({logout_completion}) passed."
    )


def _verify_legacy(
    profile: dict[str, Any],
    jwks: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    client = profile["clients"].get("legacy")
    if client is None:
        print("[OK] Historical Legacy OIDC: disabled by the bounded profile.")
        return
    redirect_uri = client["redirectUris"][0]
    post_logout_uri = client["postLogoutRedirectUris"][0]
    state = identity_verifier._base64url(secrets.token_bytes(12))
    nonce = identity_verifier._base64url(secrets.token_bytes(12))
    authorization_url = identity_verifier._authorization_url(
        profile,
        client,
        redirect_uri,
        response_type="id_token token",
        response_mode="form_post",
        state=state,
        nonce=nonce,
        prompt="login",
    )
    opener, login_document = identity_verifier._open_login(
        context,
        authorization_url,
        (redirect_uri, post_logout_uri),
    )
    status, location, body = identity_verifier._submit_login(
        opener,
        login_document,
        profile["testUsers"]["active"]["username"],
        profile["testUsers"]["password"],
        redirect_uri,
    )
    if location:
        raise identity_verifier.VerificationError(
            "Historical Legacy unexpectedly used a redirect response."
        )
    callback_form = next(
        (form for form in identity_verifier._forms(body) if form.action.startswith(redirect_uri)),
        None,
    )
    if status != 200 or callback_form is None:
        raise identity_verifier.VerificationError(
            "Historical Legacy did not return a form_post callback."
        )
    if not {"id_token", "access_token", "state"}.issubset(callback_form.inputs):
        raise identity_verifier.VerificationError(
            "Historical Legacy callback omitted expected values."
        )
    if callback_form.inputs["state"] != state:
        raise identity_verifier.VerificationError(
            "Historical Legacy callback changed state."
        )
    claims = identity_verifier._verify_id_token(
        callback_form.inputs["id_token"],
        jwks,
        issuer=profile["issuer"],
        client_id=client["clientId"],
        nonce=nonce,
    )
    if claims.get("sub") != profile["testUsers"]["active"]["subject"]:
        raise identity_verifier.VerificationError(
            "Historical Legacy ID token changed the synthetic subject."
        )

    logout_completion = _verify_rp_logout(
        opener,
        profile,
        client,
        callback_form.inputs["id_token"],
        post_logout_uri,
    )
    print(
        "[OK] Historical Legacy OIDC: retained id_token token + form_post login, "
        f"signed ID token, stable subject, and logout ({logout_completion}) passed."
    )


def _verify_negative_registration(
    profile: dict[str, Any],
    discovery: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    client = profile["clients"]["modern"]
    invalid_redirect = "https://attacker.example/callback"
    parameters = identity_verifier._authorization_parameters(
        client,
        invalid_redirect,
        response_type="code",
        state="invalid-redirect",
        nonce="invalid-redirect",
        code_challenge=identity_verifier._base64url(hashlib.sha256(b"verifier").digest()),
    )
    try:
        invalid_url, _ = _authorization_url(
            profile,
            discovery,
            context,
            client,
            parameters,
        )
        urlopen(invalid_url, context=context, timeout=20)
    except HTTPError as error:
        if error.headers.get("Location", "").startswith(invalid_redirect):
            raise identity_verifier.VerificationError(
                "Provider redirected an error to an unregistered URI."
            )
        if error.code in {400, 403}:
            print("[OK] OIDC registration: an unregistered redirect URI was rejected.")
            return
        raise
    raise identity_verifier.VerificationError("Unregistered OIDC redirect URI was accepted.")


def verify(connection_path: Path, ca_path: Path, host_override: str | None) -> None:
    _install_host_override(host_override)
    profile = json.loads(connection_path.read_text(encoding="utf-8"))
    if "modern" not in profile.get("clients", {}):
        raise identity_verifier.VerificationError("The Modern OIDC profile is disabled.")
    context = ssl.create_default_context(cafile=str(ca_path))
    discovery = identity_verifier._json_request(profile["discoveryEndpoint"], context)
    if discovery.get("issuer") != profile["issuer"]:
        raise identity_verifier.VerificationError(
            "Discovery issuer did not match the configured Northlake issuer."
        )
    required_endpoints = (
        "authorization_endpoint",
        "token_endpoint",
        "userinfo_endpoint",
        "jwks_uri",
        "end_session_endpoint",
        "revocation_endpoint",
    )
    missing = [endpoint for endpoint in required_endpoints if not discovery.get(endpoint)]
    if missing:
        raise identity_verifier.VerificationError(
            f"Discovery omitted {missing[0]}."
        )
    if "S256" not in discovery.get("code_challenge_methods_supported", []):
        raise identity_verifier.VerificationError("Discovery did not advertise PKCE S256.")
    auth_method = profile["clients"]["modern"]["tokenEndpointAuthMethod"]
    advertised_auth_method = {
        "ClientSecretPost": "client_secret_post",
        "ClientSecretBasic": "client_secret_basic",
    }[auth_method]
    if advertised_auth_method not in discovery.get(
        "token_endpoint_auth_methods_supported",
        [],
    ):
        raise identity_verifier.VerificationError(
            f"Discovery did not advertise {advertised_auth_method}."
        )
    jwks = identity_verifier._json_request(discovery["jwks_uri"], context)
    if not jwks.get("keys"):
        raise identity_verifier.VerificationError("JWKS contained no signing keys.")
    _verify_negative_registration(profile, discovery, context)
    _verify_modern(profile, discovery, jwks, context)
    _verify_legacy(profile, jwks, context)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify configurable Northlake Modern and Historical Legacy OIDC profiles."
    )
    parser.add_argument("--connection", required=True, type=Path)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--resolve-host")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    started = time.monotonic()
    try:
        verify(
            args.connection.resolve(),
            args.ca_file.resolve(),
            args.resolve_host,
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
    elapsed = time.monotonic() - started
    print(f"[OK] Northlake focused OIDC baseline completed in {elapsed:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
