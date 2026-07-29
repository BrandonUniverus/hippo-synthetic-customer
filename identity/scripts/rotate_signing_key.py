#!/usr/bin/env python3
"""Rotate the Northlake RS256 signing key through Keycloak's Admin REST API."""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RotationError(AssertionError):
    """Raised when Keycloak does not complete a safe signing-key rollover."""


def _request(
    url: str,
    context: ssl.SSLContext,
    *,
    method: str = "GET",
    form: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    bearer: str | None = None,
) -> tuple[int, Any, dict[str, str]]:
    body: bytes | None = None
    headers = {"Accept": "application/json"}
    if form is not None:
        body = urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, context=context, timeout=20) as response:
        raw_body = response.read()
        parsed = json.loads(raw_body) if raw_body else None
        return response.status, parsed, dict(response.headers)


def rotate(connection_path: Path, ca_path: Path, result_path: Path) -> dict[str, Any]:
    profile = json.loads(connection_path.read_text(encoding="utf-8"))
    context = ssl.create_default_context(cafile=str(ca_path))
    base_url = profile["baseUrl"]
    realm_name = profile["realm"]

    _, token_response, _ = _request(
        f"{base_url}/realms/master/protocol/openid-connect/token",
        context,
        method="POST",
        form={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": profile["admin"]["username"],
            "password": profile["admin"]["password"],
        },
    )
    admin_token = token_response["access_token"]

    _, realm, _ = _request(
        f"{base_url}/admin/realms/{realm_name}",
        context,
        bearer=admin_token,
    )
    _, components, _ = _request(
        (
            f"{base_url}/admin/realms/{realm_name}/components"
            f"?parent={realm['id']}&type=org.keycloak.keys.KeyProvider"
        ),
        context,
        bearer=admin_token,
    )
    _, keys_before, _ = _request(
        f"{base_url}/admin/realms/{realm_name}/keys",
        context,
        bearer=admin_token,
    )

    old_kid = keys_before["active"]["RS256"]
    retained_kids = {
        key["kid"]
        for key in keys_before["keys"]
        if key.get("algorithm") == "RS256" and key.get("use") == "SIG"
    }
    priorities = [
        int(component.get("config", {}).get("priority", ["0"])[0])
        for component in components
        if component.get("providerId") == "rsa-generated"
    ]
    new_priority = max(priorities, default=0) + 100
    rotation_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    component = {
        "name": f"synthetic-rsa-{rotation_id}",
        "providerId": "rsa-generated",
        "providerType": "org.keycloak.keys.KeyProvider",
        "parentId": realm["id"],
        "config": {
            "priority": [str(new_priority)],
            "algorithm": ["RS256"],
            "keySize": ["2048"],
            "active": ["true"],
            "enabled": ["true"],
        },
    }
    status, _, response_headers = _request(
        f"{base_url}/admin/realms/{realm_name}/components",
        context,
        method="POST",
        payload=component,
        bearer=admin_token,
    )
    if status != 201:
        raise RotationError(f"Key provider creation returned HTTP {status}; expected 201.")

    keys_after: dict[str, Any] | None = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        _, candidate, _ = _request(
            f"{base_url}/admin/realms/{realm_name}/keys",
            context,
            bearer=admin_token,
        )
        if candidate["active"].get("RS256") != old_kid:
            keys_after = candidate
            break
        time.sleep(1)
    if keys_after is None:
        raise RotationError("New RS256 key did not become active within 30 seconds.")

    new_kid = keys_after["active"]["RS256"]
    new_key = next(
        (
            key
            for key in keys_after["keys"]
            if key.get("kid") == new_kid and key.get("algorithm") == "RS256"
        ),
        None,
    )
    if new_key is None:
        raise RotationError("Active RS256 key was not present in the key inventory.")
    new_provider_id = new_key["providerId"]

    for existing_component in components:
        if (
            existing_component.get("providerId") != "rsa-generated"
            or existing_component.get("id") == new_provider_id
        ):
            continue
        updated_component = {
            **existing_component,
            "config": {
                **existing_component.get("config", {}),
                "active": ["false"],
                "enabled": ["true"],
            },
        }
        update_status, _, _ = _request(
            (
                f"{base_url}/admin/realms/{realm_name}/components/"
                f"{existing_component['id']}"
            ),
            context,
            method="PUT",
            payload=updated_component,
            bearer=admin_token,
        )
        if update_status != 204:
            raise RotationError(
                f"Previous key provider update returned HTTP {update_status}; expected 204."
            )

    _, keys_after, _ = _request(
        f"{base_url}/admin/realms/{realm_name}/keys",
        context,
        bearer=admin_token,
    )
    by_kid = {key.get("kid"): key for key in keys_after["keys"]}
    if not retained_kids.issubset(by_kid) or new_kid not in by_kid:
        raise RotationError("Previous and new signing keys were not all retained after rotation.")
    non_passive = [
        kid
        for kid in retained_kids
        if by_kid[kid].get("status") != "PASSIVE"
    ]
    if non_passive:
        raise RotationError(
            f"Previous signing keys did not become passive: {', '.join(non_passive)}."
        )
    if by_kid[new_kid].get("status") != "ACTIVE":
        raise RotationError("New signing key did not become active.")

    _, jwks, _ = _request(profile["jwksEndpoint"], context)
    published_kids = {key.get("kid") for key in jwks.get("keys", [])}
    if not (retained_kids | {new_kid}).issubset(published_kids):
        raise RotationError("JWKS did not publish every passive and active signing key.")

    result = {
        "realm": realm_name,
        "rotatedAtUtc": rotation_id,
        "oldKid": old_kid,
        "retainedKids": sorted(retained_kids),
        "newKid": new_kid,
        "newPriority": new_priority,
        "componentLocation": response_headers.get("Location", ""),
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rotate the Northlake RS256 signing key.")
    parser.add_argument("--connection", required=True, type=Path)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = rotate(
            args.connection.resolve(),
            args.ca_file.resolve(),
            args.result.resolve(),
        )
    except (OSError, HTTPError, URLError, RotationError, KeyError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print(
        f"[OK] Rotated RS256 signing key: {result['oldKid']} -> {result['newKid']} "
        f"(priority {result['newPriority']})."
    )
    print("[OK] Previous key is passive; both keys remain published in JWKS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
