"""Verify the public Phase 7 customer RP contract without using a user password."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib import error, parse, request


class BrowserLabVerificationError(ValueError):
    """Raised when the synthetic customer RP contract drifts."""


def _json(opener: request.OpenerDirector, url: str) -> Any:
    try:
        with opener.open(url, timeout=20) as response:
            return json.load(response)
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as failure:
        raise BrowserLabVerificationError(f"Unable to read {url}: {failure}.") from failure


def verify(connection_paths: list[Path], ca_path: Path) -> None:
    if len(connection_paths) != 2:
        raise BrowserLabVerificationError("Exactly two scenario connection profiles are required.")
    profiles = [json.loads(path.read_text(encoding="utf-8")) for path in connection_paths]
    customer_origins = {profile["customerSite"]["publicBaseUrl"] for profile in profiles}
    if len(customer_origins) != 1:
        raise BrowserLabVerificationError("The two realms did not share one customer RP origin.")
    customer_origin = customer_origins.pop()
    provider_origins = {
        f"{parsed.scheme}://{parsed.netloc}"
        for parsed in (parse.urlsplit(profile["issuer"]) for profile in profiles)
    }
    if len(provider_origins) != 1 or parse.urlsplit(customer_origin).hostname in {
        parse.urlsplit(origin).hostname for origin in provider_origins
    }:
        raise BrowserLabVerificationError("Customer and provider origins are not cross-site.")

    context = ssl.create_default_context(cafile=str(ca_path))
    cookie_jar = http.cookiejar.CookieJar()
    opener = request.build_opener(
        request.HTTPSHandler(context=context),
        request.HTTPCookieProcessor(cookie_jar),
    )
    state = _json(opener, f"{customer_origin}/customer/api/state")
    if not state.get("ready") or not state.get("crossSite"):
        raise BrowserLabVerificationError("Customer RP did not report the two-realm cross-site lab ready.")
    serialized_state = json.dumps(state).lower()
    if any(secret_word in serialized_state for secret_word in ("clientsecret", "id_token", "access_token")):
        raise BrowserLabVerificationError("Customer RP public state exposed secret or token fields.")
    if state.get("coverage", {}).get("backChannelLogoutClaimed"):
        raise BrowserLabVerificationError("Customer RP incorrectly claimed Back-Channel Logout.")

    safe = _json(
        opener,
        f"{customer_origin}/customer/api/deep-link?"
        + parse.urlencode({"returnTo": "https://attacker.example/customer/steal"}),
    )
    if safe.get("accepted") != "/customer/":
        raise BrowserLabVerificationError("Customer RP accepted an external deep-link destination.")

    for profile in profiles:
        slot = profile["scenario"]["slot"]
        probe = profile["customerSite"]["clients"]["probe"]
        url = f"{customer_origin}/customer/probe?" + parse.urlencode(
            {
                "slot": slot,
                "prompt": "none",
                "cookieMode": "Lax",
                "returnTo": "/customer/",
            }
        )
        try:
            with opener.open(url, timeout=30) as response:
                final_url = response.geturl()
                response.read()
        except (error.HTTPError, error.URLError, TimeoutError) as failure:
            raise BrowserLabVerificationError(
                f"{profile['realm']} prompt=none negative path failed: {failure}."
            ) from failure
        parsed_final = parse.urlsplit(final_url)
        outcome = parse.parse_qs(parsed_final.query).get("oidcOutcome")
        if (
            parsed_final.netloc != parse.urlsplit(customer_origin).netloc
            or outcome not in (["login_required"], ["consent_required"])
        ):
            raise BrowserLabVerificationError(
                f"{profile['realm']} prompt=none did not return a controlled interaction error."
            )
        if probe.get("consentRequired") is not True:
            raise BrowserLabVerificationError(
                f"{profile['realm']} probe client did not retain its consent boundary."
            )
        print(
            f"[OK] {profile['realm']} returned a controlled {outcome[0]} result for "
            "password-free prompt=none."
        )

    evidence = _json(opener, f"{customer_origin}/customer/api/evidence")
    outcomes = {event.get("outcome") for event in evidence.get("events", [])}
    if not outcomes & {"login_required", "consent_required"}:
        raise BrowserLabVerificationError("Customer RP did not retain redacted prompt evidence.")
    print("[OK] Customer RP rejects external deep links and exposes no browser-visible tokens or secrets.")
    print("[OK] Two cross-site realms and their separate primary/consent-probe clients are ready.")
    print(
        "[GAP] Interactive login, consent reuse, max_age, and iframe cookie outcomes require the "
        "real-browser run; installed EnergyHippo proof remains separate."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the Northlake browser lab contract.")
    parser.add_argument("--connection", action="append", required=True, type=Path)
    parser.add_argument("--ca-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        verify([path.resolve() for path in args.connection], args.ca_file.resolve())
    except (
        OSError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        BrowserLabVerificationError,
    ) as failure:
        print(f"[ERROR] {failure}", file=sys.stderr)
        return 1
    print("[OK] Northlake Phase 7 provider-side browser-lab verification completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
