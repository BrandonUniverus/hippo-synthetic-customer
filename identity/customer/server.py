"""Small real-browser OIDC relying party for Northlake Phase 7 evidence."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature


COOKIE_NAME = "northlake_customer_session"
CLIENT_KINDS = frozenset({"customer", "probe"})
COOKIE_MODES = frozenset({"Lax", "None"})
PROMPTS = frozenset({"", "none", "login", "consent"})
TRANSACTION_LIFETIME_SECONDS = 600
SESSION_LIFETIME_SECONDS = 8 * 60 * 60
MAX_EVIDENCE_EVENTS = 200


class CustomerLabError(ValueError):
    """Raised when a bounded browser-lab request cannot be completed."""


def safe_return_path(value: str | None) -> str:
    candidate = value or "/customer/"
    if (
        len(candidate) > 2048
        or not candidate.startswith("/customer/")
        or candidate.startswith("//")
        or "\\" in candidate
        or any(ord(character) < 32 for character in candidate)
    ):
        return "/customer/"
    parsed = parse.urlsplit(candidate)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return "/customer/"
    decoded_path = parsed.path
    for _ in range(3):
        decoded_path = parse.unquote(decoded_path)
    if (
        not decoded_path.startswith("/customer/")
        or decoded_path.startswith("//")
        or "\\" in decoded_path
        or any(segment in {".", ".."} for segment in decoded_path.split("/"))
    ):
        return "/customer/"
    return candidate


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_base64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RealmProfile:
    slot: str
    realm: str
    display_name: str
    issuer: str
    active_username: str
    customer_site: dict[str, Any]

    def client(self, kind: str) -> dict[str, Any]:
        if kind not in CLIENT_KINDS:
            raise CustomerLabError("Unknown synthetic customer client.")
        client = self.customer_site.get("clients", {}).get(kind)
        if not isinstance(client, dict):
            raise CustomerLabError(f"The {kind} client is not configured for {self.realm}.")
        return client


class EvidenceStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def read(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_unlocked()

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        events = payload.get("events") if isinstance(payload, dict) else None
        return events if isinstance(events, list) else []

    def add(
        self,
        event: str,
        *,
        realm: str | None,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = {
            "atUtc": _utc_now(),
            "event": event,
            "realm": realm,
            "outcome": outcome,
            "details": details or {},
        }
        with self._lock:
            events = [*self._read_unlocked(), item][-MAX_EVIDENCE_EVENTS:]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps({"schemaVersion": 1, "events": events}, indent=2) + os.linesep,
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        return item

    def clear(self) -> None:
        with self._lock:
            self.path.unlink(missing_ok=True)


class CustomerLab:
    def __init__(
        self,
        runtime_directory: Path,
        public_base_url: str,
        provider_base_url: str,
        keycloak_internal_url: str,
        client_secret: str,
        admin_username: str,
        admin_password: str,
    ) -> None:
        self.runtime_directory = runtime_directory
        self.public_base_url = public_base_url.rstrip("/")
        self.provider_base_url = provider_base_url.rstrip("/")
        self.keycloak_internal_url = keycloak_internal_url.rstrip("/")
        self.client_secret = client_secret
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.evidence = EvidenceStore(runtime_directory / "browser-evidence.json")
        self._transactions: dict[str, dict[str, Any]] = {}
        self._logout_transactions: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _profiles(self) -> dict[str, RealmProfile]:
        profiles: dict[str, RealmProfile] = {}
        for slot in ("labA", "labB"):
            path = self.runtime_directory / "scenarios" / slot / "connection.json"
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                customer_site = payload["customerSite"]
                profile = RealmProfile(
                    slot=slot,
                    realm=payload["realm"],
                    display_name=payload.get("scenario", {}).get(
                        "scenarioName",
                        payload["realm"],
                    ),
                    issuer=payload["issuer"],
                    active_username=payload["testUsers"]["active"]["username"],
                    customer_site=customer_site,
                )
                if customer_site.get("publicBaseUrl") != self.public_base_url:
                    continue
                profile.client("customer")
                profile.client("probe")
                profiles[slot] = profile
            except (OSError, json.JSONDecodeError, KeyError, TypeError, CustomerLabError):
                continue
        return profiles

    def profile(self, *, slot: str | None = None, realm: str | None = None) -> RealmProfile:
        profiles = self._profiles()
        matches = [
            profile
            for profile in profiles.values()
            if (slot is None or profile.slot == slot) and (realm is None or profile.realm == realm)
        ]
        if len(matches) != 1:
            raise CustomerLabError("Apply the selected Northlake lab realm before testing it.")
        return matches[0]

    def _purge(self) -> None:
        now = time.time()
        self._transactions = {
            key: value
            for key, value in self._transactions.items()
            if now - value["createdAt"] <= TRANSACTION_LIFETIME_SECONDS
        }
        self._logout_transactions = {
            key: value
            for key, value in self._logout_transactions.items()
            if now - value["createdAt"] <= TRANSACTION_LIFETIME_SECONDS
        }
        self._sessions = {
            key: value
            for key, value in self._sessions.items()
            if now - value["lastSeen"] <= SESSION_LIFETIME_SECONDS
        }

    def session(self, session_id: str | None) -> dict[str, Any] | None:
        if not session_id:
            return None
        with self._lock:
            self._purge()
            session = self._sessions.get(session_id)
            if session is not None:
                session["lastSeen"] = time.time()
            return session

    def public_state(self, session_id: str | None) -> dict[str, Any]:
        profiles = self._profiles()
        session = self.session(session_id)
        return {
            "ready": len(profiles) == 2,
            "providerOrigin": self.provider_base_url,
            "customerOrigin": self.public_base_url,
            "crossSite": parse.urlsplit(self.provider_base_url).hostname
            != parse.urlsplit(self.public_base_url).hostname,
            "realms": {
                slot: {
                    "realm": profile.realm,
                    "displayName": profile.display_name,
                    "issuer": profile.issuer,
                    "loginHint": profile.active_username,
                    "primaryClientId": profile.client("customer")["clientId"],
                    "probeClientId": profile.client("probe")["clientId"],
                    "probeConsentRequired": profile.client("probe")["consentRequired"],
                }
                for slot, profile in profiles.items()
            },
            "session": (
                {
                    "authenticated": True,
                    "realm": session["realm"],
                    "issuer": session["issuer"],
                    "username": session["username"],
                    "subject": session["subject"],
                    "cookieMode": session["cookieMode"],
                    "clients": sorted(session["clients"]),
                    "providerTerminationRequested": session.get(
                        "providerTerminationRequested",
                        False,
                    ),
                }
                if session
                else {"authenticated": False}
            ),
            "coverage": {
                "samlSpAdded": False,
                "samlSpReason": (
                    "The Phase 5 verifier and installed EnergyHippo SP already own SAML browser evidence."
                ),
                "backChannelLogoutClaimed": False,
                "oidcSessionManagementClaimed": False,
            },
        }

    def begin_authorization(
        self,
        *,
        slot: str,
        kind: str,
        prompt: str,
        login_hint: str | None,
        max_age: int | None,
        return_to: str | None,
        cookie_mode: str,
        frame: bool,
        session_id: str | None,
    ) -> str:
        profile = self.profile(slot=slot)
        client = profile.client(kind)
        if prompt not in PROMPTS:
            raise CustomerLabError("Unsupported prompt value.")
        if cookie_mode not in COOKIE_MODES:
            raise CustomerLabError("Cookie mode must be Lax or None.")
        if max_age is not None and not 0 <= max_age <= 86_400:
            raise CustomerLabError("max_age must be between 0 and 86400 seconds.")
        if login_hint is not None and (
            len(login_hint) > 254 or any(ord(character) < 32 for character in login_hint)
        ):
            raise CustomerLabError("login_hint is invalid.")

        state = _base64url(secrets.token_bytes(24))
        nonce = _base64url(secrets.token_bytes(24))
        verifier = _base64url(secrets.token_bytes(48))
        challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
        transaction = {
            "createdAt": time.time(),
            "slot": slot,
            "realm": profile.realm,
            "kind": kind,
            "nonce": nonce,
            "verifier": verifier,
            "redirectUri": client["redirectUri"],
            "returnTo": safe_return_path(return_to),
            "cookieMode": cookie_mode,
            "frame": frame,
            "sessionId": session_id,
            "prompt": prompt,
            "maxAge": max_age,
            "loginHintSupplied": bool(login_hint),
        }
        with self._lock:
            self._purge()
            self._transactions[state] = transaction

        parameters: dict[str, str] = {
            "client_id": client["clientId"],
            "redirect_uri": client["redirectUri"],
            "response_type": "code",
            "scope": "openid profile email northlake",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if prompt:
            parameters["prompt"] = prompt
        if login_hint:
            parameters["login_hint"] = login_hint
        if max_age is not None:
            parameters["max_age"] = str(max_age)
        self.evidence.add(
            "authorization-started",
            realm=profile.realm,
            outcome="redirected-to-provider",
            details={
                "client": kind,
                "prompt": prompt or "default",
                "loginHintSupplied": bool(login_hint),
                "maxAge": max_age,
                "frame": frame,
                "cookieMode": cookie_mode,
                "returnPath": transaction["returnTo"],
            },
        )
        return f"{profile.issuer}/protocol/openid-connect/auth?{parse.urlencode(parameters)}"

    def _request_json(
        self,
        url: str,
        *,
        data: dict[str, str] | None = None,
        authorization: str | None = None,
        method: str | None = None,
        expected: tuple[int, ...] = (HTTPStatus.OK,),
    ) -> Any:
        encoded = parse.urlencode(data).encode("utf-8") if data is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if authorization:
            headers["Authorization"] = authorization
        outbound = request.Request(url, data=encoded, headers=headers, method=method)
        try:
            with request.urlopen(outbound, timeout=15) as response:
                if response.status not in expected:
                    raise CustomerLabError(f"Provider returned HTTP {response.status}.")
                body = response.read()
        except error.HTTPError as failure:
            raise CustomerLabError(f"Provider returned HTTP {failure.code}.") from failure
        except (error.URLError, TimeoutError) as failure:
            raise CustomerLabError("Provider is unavailable.") from failure
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as failure:
            raise CustomerLabError("Provider returned malformed JSON.") from failure

    def _verify_id_token(
        self,
        token: str,
        *,
        profile: RealmProfile,
        client_id: str,
        nonce: str,
    ) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise CustomerLabError("Provider returned a malformed ID token.")
        try:
            header = json.loads(_decode_base64url(parts[0]))
            claims = json.loads(_decode_base64url(parts[1]))
            signature = _decode_base64url(parts[2])
        except (ValueError, json.JSONDecodeError) as failure:
            raise CustomerLabError("Provider returned a malformed ID token.") from failure
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise CustomerLabError("ID token did not use the expected signing algorithm.")
        internal_issuer = f"{self.keycloak_internal_url}/realms/{parse.quote(profile.realm)}"
        jwks = self._request_json(f"{internal_issuer}/protocol/openid-connect/certs")
        key = next(
            (
                value
                for value in jwks.get("keys", [])
                if value.get("kid") == header["kid"]
                and value.get("kty") == "RSA"
                and value.get("use") == "sig"
            ),
            None,
        )
        if key is None:
            raise CustomerLabError("ID token signing key was not published.")
        public_key = rsa.RSAPublicNumbers(
            int.from_bytes(_decode_base64url(key["e"]), "big"),
            int.from_bytes(_decode_base64url(key["n"]), "big"),
        ).public_key()
        try:
            public_key.verify(
                signature,
                f"{parts[0]}.{parts[1]}".encode("ascii"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature as failure:
            raise CustomerLabError("ID token signature validation failed.") from failure

        now = int(time.time())
        audience = claims.get("aud")
        audiences = [audience] if isinstance(audience, str) else audience
        if (
            not hmac.compare_digest(str(claims.get("iss", "")), profile.issuer)
            or not isinstance(audiences, list)
            or client_id not in audiences
            or not hmac.compare_digest(str(claims.get("nonce", "")), nonce)
            or not isinstance(claims.get("exp"), int)
            or claims["exp"] < now - 60
            or not isinstance(claims.get("iat"), int)
            or claims["iat"] > now + 60
        ):
            raise CustomerLabError("ID token security bindings did not validate.")
        if len(audiences) > 1 and claims.get("azp") != client_id:
            raise CustomerLabError("ID token authorized-party binding did not validate.")
        return claims

    def complete_authorization(
        self,
        *,
        realm: str,
        kind: str,
        parameters: dict[str, list[str]],
        cookie_session_id: str | None,
    ) -> dict[str, Any]:
        state = parameters.get("state", [""])[0]
        with self._lock:
            self._purge()
            transaction = self._transactions.pop(state, None)
        if transaction is None:
            raise CustomerLabError("Authorization state was missing, expired, or already used.")
        if transaction["realm"] != realm or transaction["kind"] != kind:
            raise CustomerLabError("Authorization callback did not match its client and realm.")
        if transaction["sessionId"] and transaction["sessionId"] != cookie_session_id:
            raise CustomerLabError("Authorization callback lost its initiating RP session.")
        profile = self.profile(realm=realm)
        client = profile.client(kind)

        provider_error = parameters.get("error", [None])[0]
        if provider_error:
            if provider_error not in {
                "login_required",
                "consent_required",
                "interaction_required",
                "account_selection_required",
            }:
                provider_error = "provider_error"
            self.evidence.add(
                "authorization-completed",
                realm=realm,
                outcome=provider_error,
                details={
                    "client": kind,
                    "prompt": transaction["prompt"] or "default",
                    "frame": transaction["frame"],
                },
            )
            return {
                "success": False,
                "outcome": provider_error,
                "frame": transaction["frame"],
                "returnTo": transaction["returnTo"],
                "sessionId": cookie_session_id,
                "cookieMode": transaction["cookieMode"],
            }

        code = parameters.get("code", [None])[0]
        callback_issuer = parameters.get("iss", [None])[0]
        if (
            not code
            or not isinstance(callback_issuer, str)
            or not hmac.compare_digest(callback_issuer, profile.issuer)
        ):
            raise CustomerLabError("Authorization callback omitted its code or issuer binding.")
        credentials = base64.b64encode(
            f"{client['clientId']}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")
        internal_issuer = f"{self.keycloak_internal_url}/realms/{parse.quote(realm)}"
        tokens = self._request_json(
            f"{internal_issuer}/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": transaction["redirectUri"],
                "code_verifier": transaction["verifier"],
            },
            authorization=f"Basic {credentials}",
        )
        id_token = tokens.get("id_token") if isinstance(tokens, dict) else None
        access_token = tokens.get("access_token") if isinstance(tokens, dict) else None
        if not isinstance(id_token, str) or not isinstance(access_token, str):
            raise CustomerLabError("Provider token response was incomplete.")
        claims = self._verify_id_token(
            id_token,
            profile=profile,
            client_id=client["clientId"],
            nonce=transaction["nonce"],
        )
        if transaction["maxAge"] is not None:
            auth_time = claims.get("auth_time")
            if not isinstance(auth_time, int) or time.time() - auth_time > transaction["maxAge"] + 60:
                raise CustomerLabError("Provider did not satisfy the requested max_age.")
        userinfo = self._request_json(
            f"{internal_issuer}/protocol/openid-connect/userinfo",
            authorization=f"Bearer {access_token}",
        )
        if userinfo.get("sub") != claims.get("sub"):
            raise CustomerLabError("ID token and UserInfo subjects did not match.")

        with self._lock:
            self._purge()
            session_id = cookie_session_id or _base64url(secrets.token_bytes(32))
            session = self._sessions.get(session_id)
            if session is not None and session["issuer"] != profile.issuer:
                self._sessions.pop(session_id, None)
                session_id = _base64url(secrets.token_bytes(32))
                session = None
            if session is None:
                session = {
                    "createdAt": time.time(),
                    "lastSeen": time.time(),
                    "realm": realm,
                    "issuer": profile.issuer,
                    "username": claims.get("preferred_username", "unknown"),
                    "subject": claims.get("sub", ""),
                    "cookieMode": transaction["cookieMode"],
                    "clients": {},
                }
                self._sessions[session_id] = session
            session.update(
                {
                    "lastSeen": time.time(),
                    "username": claims.get("preferred_username", session["username"]),
                    "subject": claims.get("sub", session["subject"]),
                    "cookieMode": transaction["cookieMode"],
                    "providerTerminationRequested": False,
                }
            )
            session["clients"][kind] = {
                "clientId": client["clientId"],
                "idToken": id_token,
                "sid": claims.get("sid"),
                "authTime": claims.get("auth_time"),
            }
        self.evidence.add(
            "authorization-completed",
            realm=realm,
            outcome="authenticated",
            details={
                "client": kind,
                "prompt": transaction["prompt"] or "default",
                "frame": transaction["frame"],
                "cookieMode": transaction["cookieMode"],
                "loginHintSupplied": transaction["loginHintSupplied"],
                "maxAge": transaction["maxAge"],
            },
        )
        return {
            "success": True,
            "outcome": "authenticated",
            "frame": transaction["frame"],
            "returnTo": transaction["returnTo"],
            "sessionId": session_id,
            "cookieMode": transaction["cookieMode"],
        }

    def local_logout(self, session_id: str | None) -> None:
        session = self.session(session_id)
        with self._lock:
            if session_id:
                self._sessions.pop(session_id, None)
        self.evidence.add(
            "local-logout",
            realm=session["realm"] if session else None,
            outcome="rp-session-cleared-provider-session-unchanged",
        )

    def begin_rp_logout(self, session_id: str | None) -> str:
        session = self.session(session_id)
        if session is None:
            raise CustomerLabError("No local RP session is available to log out.")
        kind = "customer" if "customer" in session["clients"] else next(iter(session["clients"]))
        client_record = session["clients"][kind]
        profile = self.profile(realm=session["realm"])
        client = profile.client(kind)
        state = _base64url(secrets.token_bytes(24))
        with self._lock:
            self._logout_transactions[state] = {
                "createdAt": time.time(),
                "sessionId": session_id,
                "realm": session["realm"],
            }
        parameters = {
            "client_id": client["clientId"],
            "id_token_hint": client_record["idToken"],
            "post_logout_redirect_uri": client["postLogoutRedirectUri"],
            "state": state,
        }
        self.evidence.add(
            "rp-initiated-logout",
            realm=session["realm"],
            outcome="redirected-to-provider",
            details={"client": kind, "cookieMode": session["cookieMode"]},
        )
        return f"{profile.issuer}/protocol/openid-connect/logout?{parse.urlencode(parameters)}"

    def complete_rp_logout(self, realm: str, state: str | None, session_id: str | None) -> None:
        with self._lock:
            self._purge()
            transaction = self._logout_transactions.pop(state or "", None)
            if transaction is None or transaction["realm"] != realm:
                raise CustomerLabError("Logout callback state was missing, expired, or invalid.")
            if transaction["sessionId"] != session_id and session_id in self._sessions:
                raise CustomerLabError("Logout callback did not match the initiating RP session.")
            self._sessions.pop(transaction["sessionId"], None)
        self.evidence.add(
            "rp-initiated-logout",
            realm=realm,
            outcome="provider-returned-rp-session-cleared",
        )

    def frontchannel_logout(
        self,
        *,
        realm: str,
        kind: str,
        issuer: str | None,
        sid: str | None,
        session_id: str | None,
    ) -> tuple[str, bool]:
        profile = self.profile(realm=realm)
        profile.client(kind)
        session = self.session(session_id)
        if session is None:
            outcome = (
                "delivery-without-rp-session-cookie"
                if session_id is None
                else "delivery-without-local-session"
            )
            cleared = False
        elif issuer != profile.issuer or not sid:
            outcome = "rejected-missing-or-invalid-issuer-session-binding"
            cleared = False
        else:
            known_sids = {
                value.get("sid")
                for value in session["clients"].values()
                if value.get("sid")
            }
            if session["realm"] != realm or sid not in known_sids:
                outcome = "rejected-mismatched-rp-session"
                cleared = False
            else:
                with self._lock:
                    self._sessions.pop(session_id, None)
                outcome = "verified-session-cleared"
                cleared = True
        self.evidence.add(
            "front-channel-logout",
            realm=realm,
            outcome=outcome,
            details={
                "client": kind,
                "issPresent": bool(issuer),
                "sidPresent": bool(sid),
                "rpCookiePresent": bool(session_id),
            },
        )
        return outcome, cleared

    def provider_terminate(self, session_id: str | None) -> str:
        session = self.session(session_id)
        if session is None:
            raise CustomerLabError("No local RP session is available to terminate upstream.")
        admin_token = self._request_json(
            f"{self.keycloak_internal_url}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.admin_username,
                "password": self.admin_password,
            },
        )["access_token"]
        realm = parse.quote(session["realm"], safe="")
        username = parse.quote(session["username"], safe="")
        users = self._request_json(
            f"{self.keycloak_internal_url}/admin/realms/{realm}/users?"
            f"username={username}&exact=true",
            authorization=f"Bearer {admin_token}",
        )
        matching = [user for user in users if user.get("username") == session["username"]]
        if len(matching) != 1:
            raise CustomerLabError("Provider user could not be resolved exactly.")
        user_id = parse.quote(matching[0]["id"], safe="")
        self._request_json(
            f"{self.keycloak_internal_url}/admin/realms/{realm}/users/{user_id}/logout",
            data={},
            authorization=f"Bearer {admin_token}",
            method="POST",
            expected=(HTTPStatus.NO_CONTENT,),
        )
        with self._lock:
            current = self._sessions.get(session_id or "")
            if current is not None:
                current["providerTerminationRequested"] = True
        self.evidence.add(
            "provider-initiated-session-termination",
            realm=session["realm"],
            outcome="provider-session-ended-local-rp-session-retained",
            details={"frontChannelIframeExpected": False},
        )
        return session["realm"]

    def record_browser_observation(self, slot: str, outcome: str) -> dict[str, Any]:
        if outcome not in {"provider-frame-unavailable"}:
            raise CustomerLabError("Unsupported browser observation.")
        profile = self.profile(slot=slot)
        return self.evidence.add(
            "silent-iframe",
            realm=profile.realm,
            outcome=outcome,
            details={
                "classification": "expected-controlled-unavailability",
                "possibleCauses": [
                    "provider-frame-policy",
                    "browser-third-party-state-restriction",
                ],
            },
        )


def _cookie_value(header: str | None) -> str | None:
    for item in (header or "").split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == COOKIE_NAME:
            return value or None
    return None


def _session_cookie(session_id: str, mode: str, *, clear: bool = False) -> str:
    if mode not in COOKIE_MODES:
        mode = "Lax"
    value = "" if clear else session_id
    attributes = [
        f"{COOKIE_NAME}={value}",
        "Path=/customer/",
        "HttpOnly",
        "Secure",
        f"SameSite={mode}",
    ]
    if clear:
        attributes.extend(["Max-Age=0", "Expires=Thu, 01 Jan 1970 00:00:00 GMT"])
    return "; ".join(attributes)


class CustomerHandler(BaseHTTPRequestHandler):
    server_version = "NorthlakeCustomer/1.0"

    @property
    def application(self) -> CustomerLab:
        return self.server.application  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        print(f"customer-site: {self.address_string()} {format % args}")

    def _headers(
        self,
        status: int,
        content_type: str,
        *,
        length: int,
        cookie: str | None = None,
        frame_ancestor: str = "'self'",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            f"frame-src {self.application.provider_base_url}; frame-ancestors {frame_ancestor}; "
            "base-uri 'none'; object-src 'none'",
        )
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _json(self, status: int, payload: Any, *, cookie: str | None = None) -> None:
        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", length=len(body), cookie=cookie)
        self.wfile.write(body)

    def _text(
        self,
        status: int,
        value: str,
        content_type: str = "text/plain; charset=utf-8",
        *,
        cookie: str | None = None,
        frame_ancestor: str = "'self'",
    ) -> None:
        body = value.encode("utf-8")
        self._headers(
            status,
            content_type,
            length=len(body),
            cookie=cookie,
            frame_ancestor=frame_ancestor,
        )
        self.wfile.write(body)

    def _redirect(self, location: str, *, cookie: str | None = None) -> None:
        body = b""
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _static(self, name: str, content_type: str) -> None:
        path = Path(__file__).with_name(name)
        try:
            value = path.read_text(encoding="utf-8")
        except OSError:
            self._text(HTTPStatus.NOT_FOUND, "Not found")
            return
        self._text(HTTPStatus.OK, value, content_type)

    def _query(self) -> tuple[str, dict[str, list[str]]]:
        parsed = parse.urlsplit(self.path)
        return parsed.path.rstrip("/") or "/", parse.parse_qs(parsed.query, keep_blank_values=True)

    def _session_id(self) -> str | None:
        return _cookie_value(self.headers.get("Cookie"))

    def _authorization(self, path: str, query: dict[str, list[str]]) -> None:
        kind = "probe" if path in {"/customer/probe", "/customer/consent"} else "customer"
        prompt = query.get("prompt", ["none" if path == "/customer/probe" else ""])[0]
        if path == "/customer/consent":
            prompt = "consent"
        max_age_text = query.get("max_age", [None])[0]
        try:
            max_age = int(max_age_text) if max_age_text not in {None, ""} else None
        except ValueError as failure:
            raise CustomerLabError("max_age must be a whole number.") from failure
        location = self.application.begin_authorization(
            slot=query.get("slot", ["labA"])[0],
            kind=kind,
            prompt=prompt,
            login_hint=query.get("login_hint", [None])[0],
            max_age=max_age,
            return_to=query.get("returnTo", [None])[0],
            cookie_mode=query.get("cookieMode", ["Lax"])[0],
            frame=query.get("frame", ["false"])[0].lower() == "true",
            session_id=self._session_id(),
        )
        self._redirect(location)

    def do_GET(self) -> None:
        path, query = self._query()
        try:
            if path == "/customer/health":
                state = self.application.public_state(None)
                self._json(HTTPStatus.OK, {"status": "ok", "realmsReady": state["ready"]})
            elif path in {"/customer", "/customer/deep-link/reports/monthly"}:
                self._static("index.html", "text/html; charset=utf-8")
            elif path == "/customer/app.js":
                self._static("app.js", "text/javascript; charset=utf-8")
            elif path == "/customer/styles.css":
                self._static("styles.css", "text/css; charset=utf-8")
            elif path == "/customer/api/state":
                self._json(HTTPStatus.OK, self.application.public_state(self._session_id()))
            elif path == "/customer/api/evidence":
                self._json(
                    HTTPStatus.OK,
                    {"schemaVersion": 1, "events": self.application.evidence.read()},
                )
            elif path == "/customer/api/deep-link":
                requested = query.get("returnTo", [None])[0]
                self._json(
                    HTTPStatus.OK,
                    {"requested": requested, "accepted": safe_return_path(requested)},
                )
            elif path in {"/customer/login", "/customer/probe", "/customer/consent"}:
                self._authorization(path, query)
            elif path.startswith("/customer/oidc/callback/"):
                parts = path.split("/")
                if len(parts) != 6:
                    raise CustomerLabError("OIDC callback path is invalid.")
                result = self.application.complete_authorization(
                    realm=parts[4],
                    kind=parts[5],
                    parameters=query,
                    cookie_session_id=self._session_id(),
                )
                cookie = None
                if result["success"]:
                    cookie = _session_cookie(result["sessionId"], result["cookieMode"])
                if result["frame"]:
                    nonce = _base64url(secrets.token_bytes(18))
                    message = html.escape(json.dumps({
                        "type": "northlake-silent-result",
                        "outcome": result["outcome"],
                        "success": result["success"],
                    }))
                    document = (
                        "<!doctype html><html><body data-result='"
                        + message
                        + "'><p>Silent check completed.</p><script nonce='"
                        + nonce
                        + "'>window.parent.postMessage(JSON.parse(document.body.dataset.result), "
                        + "window.location.origin);</script></body></html>"
                    )
                    body = document.encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header(
                        "Content-Security-Policy",
                        f"default-src 'none'; script-src 'nonce-{nonce}'; frame-ancestors 'self'",
                    )
                    if cookie:
                        self.send_header("Set-Cookie", cookie)
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    separator = "&" if "?" in result["returnTo"] else "?"
                    self._redirect(
                        f"{result['returnTo']}{separator}oidcOutcome="
                        f"{parse.quote(result['outcome'])}",
                        cookie=cookie,
                    )
            elif path.startswith("/customer/signed-out/"):
                realm = path.split("/")[-1]
                self.application.complete_rp_logout(
                    realm,
                    query.get("state", [None])[0],
                    self._session_id(),
                )
                self._redirect(
                    "/customer/?oidcOutcome=rp-logout-complete",
                    cookie=_session_cookie("", "Lax", clear=True),
                )
            elif path.startswith("/customer/frontchannel-logout/"):
                parts = path.split("/")
                if len(parts) != 5:
                    raise CustomerLabError("Front-Channel Logout path is invalid.")
                outcome, cleared = self.application.frontchannel_logout(
                    realm=parts[3],
                    kind=parts[4],
                    issuer=query.get("iss", [None])[0],
                    sid=query.get("sid", [None])[0],
                    session_id=self._session_id(),
                )
                self._text(
                    HTTPStatus.OK,
                    f"Northlake Front-Channel Logout: {outcome}",
                    cookie=(
                        _session_cookie("", "None", clear=True) if cleared else None
                    ),
                    frame_ancestor=self.application.provider_base_url,
                )
            else:
                self._text(HTTPStatus.NOT_FOUND, "Not found")
        except CustomerLabError as failure:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(failure)})

    def _form(self) -> dict[str, list[str]]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as failure:
            raise CustomerLabError("Invalid request length.") from failure
        if length > 16_384:
            raise CustomerLabError("Request was too large.")
        return parse.parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)

    def do_POST(self) -> None:
        path, _ = self._query()
        try:
            form = self._form()
            if path == "/customer/browser-observation":
                event = self.application.record_browser_observation(
                    form.get("slot", [""])[0],
                    form.get("outcome", [""])[0],
                )
                self._json(HTTPStatus.OK, {"recorded": True, "event": event})
            elif path == "/customer/local-logout":
                self.application.local_logout(self._session_id())
                self._redirect(
                    "/customer/?oidcOutcome=local-logout-complete",
                    cookie=_session_cookie("", "Lax", clear=True),
                )
            elif path == "/customer/rp-logout":
                self._redirect(self.application.begin_rp_logout(self._session_id()))
            elif path == "/customer/provider-terminate":
                realm = self.application.provider_terminate(self._session_id())
                self._redirect(
                    f"/customer/?oidcOutcome=provider-session-ended&realm={parse.quote(realm)}"
                )
            elif path == "/customer/evidence/clear":
                self.application.evidence.clear()
                self._redirect("/customer/?oidcOutcome=evidence-cleared")
            else:
                self._text(HTTPStatus.NOT_FOUND, "Not found")
        except CustomerLabError as failure:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(failure)})


class CustomerServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], application: CustomerLab):
        super().__init__(address, CustomerHandler)
        self.application = application


def main() -> None:
    application = CustomerLab(
        runtime_directory=Path(os.environ.get("NORTHLAKE_RUNTIME_DIRECTORY", "/runtime")),
        public_base_url=os.environ.get(
            "NORTHLAKE_CUSTOMER_PUBLIC_BASE_URL",
            "https://customer.localtest.me:8443",
        ),
        provider_base_url=os.environ.get(
            "IDENTITY_PUBLIC_BASE_URL",
            "https://localhost:8443",
        ),
        keycloak_internal_url=os.environ.get(
            "NORTHLAKE_KEYCLOAK_INTERNAL_URL",
            "http://keycloak:8080",
        ),
        client_secret=os.environ["NORTHLAKE_CUSTOMER_CLIENT_SECRET"],
        admin_username=os.environ.get("KEYCLOAK_ADMIN", "admin"),
        admin_password=os.environ["KEYCLOAK_ADMIN_PASSWORD"],
    )
    server = CustomerServer(("0.0.0.0", 8082), application)
    print("Northlake synthetic customer site listening on http://0.0.0.0:8082/customer/")
    server.serve_forever()


if __name__ == "__main__":
    main()
