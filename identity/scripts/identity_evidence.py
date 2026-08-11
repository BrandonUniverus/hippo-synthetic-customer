#!/usr/bin/env python3
"""Capture and export redacted ADR-002b Phase 9 identity evidence."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import ssl
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib import request

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from identity.evidence.catalog import (
    EvidenceCatalogError,
    load_json_object,
    validate_coverage_catalog,
    validate_fault_catalog,
)


MAX_PUBLIC_RESPONSE_BYTES = 4 * 1024 * 1024
ARTIFACT_FILES = {
    "oidc-verification": "oidc-verification.json",
    "saml-verification": "saml-verification.json",
    "scenario-verification": "scenario-verification.json",
    "browser-evidence": "browser-evidence.json",
    "scim-verification": "scim-verification.json",
    "scim-lifecycle": "scim-lifecycle.json",
    "key-rotation": "last-key-rotation.json",
    "stable-promotion": "evidence/stable-promotion.json",
    "restart-stability": "evidence/restart-stability.json",
}
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "clientsecret",
        "secret",
        "credential",
        "credentials",
        "authorization",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "tokenresponse",
    }
)


class IdentityEvidenceError(RuntimeError):
    """Raised when evidence cannot be captured without weakening its contract."""


def capture_stable_snapshot(
    connection_path: Path,
    ca_path: Path,
    catalog_path: Path,
    compose_path: Path,
) -> dict[str, Any]:
    profile = load_json_object(connection_path)
    catalog = load_json_object(catalog_path)
    validate_coverage_catalog(catalog, catalog_path.parents[2])
    stable = catalog.get("stableEnvironment")
    if not isinstance(stable, Mapping):
        raise IdentityEvidenceError("Coverage catalog stableEnvironment is missing.")
    expected_realm = stable.get("realmKey")
    if profile.get("realm") != expected_realm:
        raise IdentityEvidenceError("Stable evidence can be captured only for the northlake realm.")

    clients = profile.get("clients")
    if not isinstance(clients, Mapping):
        raise IdentityEvidenceError("Connection profile client inventory is missing.")
    stable_clients = sorted(key for key, value in clients.items() if isinstance(value, Mapping))
    if stable_clients != ["modern", "saml"]:
        raise IdentityEvidenceError(
            "Stable promotion requires exactly the Modern OIDC and Standard SAML registrations."
        )

    context = ssl.create_default_context(cafile=str(ca_path))
    discovery = _get_json(profile["discoveryEndpoint"], context)
    if discovery.get("issuer") != profile.get("issuer"):
        raise IdentityEvidenceError("Live discovery issuer does not match the stable connection profile.")
    jwks = _get_json(profile["jwksEndpoint"], context)
    signing_keys = _safe_signing_keys(jwks)
    if not signing_keys:
        raise IdentityEvidenceError("The stable realm published no RS256 signing keys.")
    metadata = _get_bytes(profile["samlMetadataEndpoint"], context)
    saml_metadata = _saml_metadata_fingerprint(metadata)
    expected_entity = profile.get("issuer")
    if saml_metadata["entityId"] != expected_entity:
        raise IdentityEvidenceError("Live SAML metadata entity ID does not match the stable provider issuer.")

    subject_fingerprints = _subject_fingerprints(profile)
    configuration_hash = _stable_configuration_hash(profile, connection_path.parents[1])
    keycloak_image = _keycloak_image(compose_path)
    return {
        "schemaVersion": 1,
        "capturedAtUtc": datetime.now(UTC).isoformat(),
        "realm": expected_realm,
        "issuer": discovery["issuer"],
        "discoveryEndpoint": profile["discoveryEndpoint"],
        "stableClients": stable_clients,
        "subjectFingerprints": subject_fingerprints,
        "oidcSigningKeys": signing_keys,
        "samlMetadata": saml_metadata,
        "configurationHash": configuration_hash,
        "keycloakImage": keycloak_image,
        "redacted": True,
    }


def compare_stable_snapshots(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    outage_observed: bool,
) -> dict[str, Any]:
    checks = {
        "outageObserved": outage_observed,
        "realmUnchanged": before.get("realm") == after.get("realm"),
        "issuerUnchanged": before.get("issuer") == after.get("issuer"),
        "stableClientsUnchanged": before.get("stableClients") == after.get("stableClients"),
        "subjectsUnchanged": before.get("subjectFingerprints") == after.get("subjectFingerprints"),
        "oidcKeysUnchanged": before.get("oidcSigningKeys") == after.get("oidcSigningKeys"),
        "samlMetadataUnchanged": before.get("samlMetadata") == after.get("samlMetadata"),
        "configurationUnchanged": before.get("configurationHash") == after.get("configurationHash"),
        "imageUnchanged": before.get("keycloakImage") == after.get("keycloakImage"),
    }
    return {
        "schemaVersion": 1,
        "checkedAtUtc": datetime.now(UTC).isoformat(),
        "passed": all(checks.values()),
        "classification": "restart-stability-passed" if all(checks.values()) else "restart-stability-break",
        "checks": checks,
        "beforeCapturedAtUtc": before.get("capturedAtUtc"),
        "afterCapturedAtUtc": after.get("capturedAtUtc"),
        "configurationHash": after.get("configurationHash"),
        "issuer": after.get("issuer"),
        "stableClients": after.get("stableClients"),
        "keycloakImage": after.get("keycloakImage"),
        "redacted": True,
    }


def export_evidence(
    repository_root: Path,
    eem_repository_root: Path,
    catalog_path: Path,
    fault_path: Path,
    runtime_directory: Path,
    command_results_path: Path,
    restart_result_path: Path,
) -> dict[str, Any]:
    catalog = load_json_object(catalog_path)
    faults = load_json_object(fault_path)
    validate_coverage_catalog(catalog, repository_root)
    validate_fault_catalog(faults)
    command_document = load_json_object(command_results_path)
    commands = _command_results(command_document)
    artifacts = {
        identifier: _artifact_status(runtime_directory / relative_path, identifier)
        for identifier, relative_path in ARTIFACT_FILES.items()
    }
    restart = load_json_object(restart_result_path) if restart_result_path.is_file() else None
    scenarios = []
    proof_gaps = []
    local_failures = []
    for scenario in catalog["scenarios"]:
        evidence_results = [
            _resolve_evidence(item, commands, artifacts, restart)
            for item in scenario["evidence"]
        ]
        evidence_passed = bool(evidence_results) and all(item["passed"] for item in evidence_results)
        proof_gap = scenario.get("proofGap")
        if evidence_passed and proof_gap:
            status = "passed-with-gap"
        elif evidence_passed:
            status = "passed"
        elif proof_gap:
            status = "gap"
        else:
            status = "failed"
        if scenario.get("localRequired") is True and not evidence_passed:
            local_failures.append(scenario["id"])
        scenarios.append(
            {
                "id": scenario["id"],
                "expectedClassification": scenario["expectedClassification"],
                "environment": scenario["environment"],
                "status": status,
                "evidence": evidence_results,
                "adrMappings": scenario["adrMappings"],
            }
        )
        if proof_gap:
            proof_gaps.append(
                {
                    "scenarioId": scenario["id"],
                    "code": proof_gap["code"],
                    "reason": proof_gap["reason"],
                }
            )

    stable_snapshot_path = runtime_directory / "evidence" / "stable-after.json"
    stable_snapshot = load_json_object(stable_snapshot_path) if stable_snapshot_path.is_file() else {}
    northlake_revision = _git_revision(repository_root)
    eem_revision = _git_revision(eem_repository_root)
    passed = not local_failures
    classification = (
        "northlake-local-evidence-passed-with-explicit-external-gaps"
        if passed
        else "northlake-local-evidence-failed"
    )
    manifest = {
        "schemaVersion": 1,
        "passed": passed,
        "generatedAtUtc": datetime.now(UTC).isoformat(),
        "scenarioVersion": catalog["scenarioVersion"],
        "sourceRevisions": {
            "northlake": northlake_revision,
            "energyHippo": eem_revision,
        },
        "keycloakImage": stable_snapshot.get("keycloakImage") or _keycloak_image(repository_root / "identity" / "compose.yml"),
        "configuration": {
            "hash": stable_snapshot.get("configurationHash"),
            "issuer": stable_snapshot.get("issuer"),
            "stableClients": stable_snapshot.get("stableClients"),
            "faultFixtureVersion": faults.get("fixtureVersion"),
        },
        "commands": list(commands.values()),
        "artifacts": artifacts,
        "coverage": {
            "totalScenarios": len(scenarios),
            "passed": sum(item["status"] == "passed" for item in scenarios),
            "passedWithGap": sum(item["status"] == "passed-with-gap" for item in scenarios),
            "gaps": sum(item["status"] == "gap" for item in scenarios),
            "failed": sum(item["status"] == "failed" for item in scenarios),
            "scenarios": scenarios,
        },
        "proofGaps": proof_gaps,
        "result": {
            "passed": passed,
            "classification": classification,
            "localFailures": local_failures,
            "explicitProofGapCount": len(proof_gaps),
        },
        "redacted": True,
    }
    _assert_redacted(manifest)
    return manifest


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    _assert_redacted(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _get_json(url: str, context: ssl.SSLContext) -> dict[str, Any]:
    payload = json.loads(_get_bytes(url, context))
    if not isinstance(payload, dict):
        raise IdentityEvidenceError(f"{url} did not return one JSON object.")
    return payload


def _get_bytes(url: str, context: ssl.SSLContext) -> bytes:
    http_request = request.Request(url, headers={"Accept": "application/json, application/xml, text/xml"})
    with request.urlopen(http_request, context=context, timeout=20) as response:
        payload = response.read(MAX_PUBLIC_RESPONSE_BYTES + 1)
    if len(payload) > MAX_PUBLIC_RESPONSE_BYTES:
        raise IdentityEvidenceError(f"{url} exceeded the public evidence response limit.")
    return payload


def _safe_signing_keys(jwks: Mapping[str, Any]) -> list[dict[str, Any]]:
    values = jwks.get("keys")
    if not isinstance(values, list):
        raise IdentityEvidenceError("JWKS omitted its keys array.")
    result = []
    for key in values:
        if not isinstance(key, Mapping) or key.get("kty") != "RSA" or key.get("use") != "sig":
            continue
        kid = key.get("kid")
        if not isinstance(kid, str) or not kid:
            raise IdentityEvidenceError("JWKS contains a signing key without a kid.")
        certificates = key.get("x5c")
        certificate_sha256 = None
        if isinstance(certificates, list) and certificates and isinstance(certificates[0], str):
            certificate_sha256 = hashlib.sha256(base64.b64decode(certificates[0])).hexdigest()
        result.append(
            {
                "kid": kid,
                "algorithm": key.get("alg"),
                "certificateSha256": certificate_sha256,
            }
        )
    return sorted(result, key=lambda item: item["kid"])


def _saml_metadata_fingerprint(payload: bytes) -> dict[str, Any]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as failure:
        raise IdentityEvidenceError("SAML metadata is not valid XML.") from failure
    entity_id = root.attrib.get("entityID")
    if not entity_id:
        raise IdentityEvidenceError("SAML metadata omitted entityID.")
    certificates = []
    for value in root.findall(".//{http://www.w3.org/2000/09/xmldsig#}X509Certificate"):
        if value.text and value.text.strip():
            certificates.append(hashlib.sha256(base64.b64decode("".join(value.text.split()))).hexdigest())
    if not certificates:
        raise IdentityEvidenceError("SAML metadata published no X.509 certificates.")
    return {
        "entityId": entity_id,
        "certificateSha256": sorted(set(certificates)),
        "documentSha256": hashlib.sha256(payload).hexdigest(),
    }


def _subject_fingerprints(profile: Mapping[str, Any]) -> dict[str, str]:
    users = profile.get("testUsers")
    if not isinstance(users, Mapping):
        raise IdentityEvidenceError("Connection profile testUsers are missing.")
    result = {}
    for role in ("active", "disabled"):
        user = users.get(role)
        if not isinstance(user, Mapping):
            raise IdentityEvidenceError(f"Connection profile {role} user is missing.")
        for field in ("subject", "samlNameId"):
            value = user.get(field)
            if not isinstance(value, str) or not value:
                raise IdentityEvidenceError(f"Connection profile {role} {field} is missing.")
            result[f"{role}.{field}"] = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return result


def _stable_configuration_hash(profile: Mapping[str, Any], identity_root: Path) -> str:
    safe_profile = {
        "realm": profile.get("realm"),
        "subjectNamespace": profile.get("subjectNamespace"),
        "realmSource": profile.get("realmSource"),
        "userInventory": profile.get("userInventory"),
        "groupInventory": profile.get("groupInventory"),
        "issuer": profile.get("issuer"),
        "clients": _without_sensitive_values(profile.get("clients")),
        "subjectFingerprints": _subject_fingerprints(profile),
    }
    source_hashes = {}
    for relative_path in (
        "../security/northlake-eem-security-v1.yaml",
        "realm/generate_realm.py",
        ".runtime/configuration.json",
        ".runtime/oidc.json",
        ".runtime/saml.json",
    ):
        path = (identity_root / relative_path).resolve()
        if path.is_file():
            source_hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    canonical = json.dumps(
        {"profile": safe_profile, "sourceHashes": source_hashes},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _without_sensitive_values(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: "[excluded]" if _is_sensitive_key(key) else _without_sensitive_values(child)
            for key, child in sorted(value.items())
        }
    if isinstance(value, list):
        return [_without_sensitive_values(child) for child in value]
    return value


def _keycloak_image(compose_path: Path) -> dict[str, str]:
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    try:
        pinned = compose["services"]["keycloak"]["image"]
    except (KeyError, TypeError) as failure:
        raise IdentityEvidenceError("Compose does not define the Keycloak image.") from failure
    if not isinstance(pinned, str) or "@sha256:" not in pinned:
        raise IdentityEvidenceError("Keycloak image must be pinned by digest.")
    command = [
        "docker",
        "ps",
        "--filter",
        "label=com.docker.compose.project=hippo-synthetic-identity",
        "--filter",
        "label=com.docker.compose.service=keycloak",
        "--format",
        "{{.ID}}",
    ]
    container_ids = _run(command).splitlines()
    if len(container_ids) != 1:
        raise IdentityEvidenceError("Exactly one Northlake Keycloak container must be running.")
    running_image_id = _run(["docker", "inspect", container_ids[0], "--format", "{{.Image}}"])
    return {
        "pinnedReference": pinned,
        "pinnedDigest": pinned.rsplit("@", 1)[1],
        "runningImageId": running_image_id,
    }


def _git_revision(repository_root: Path) -> dict[str, Any]:
    revision = _run(["git", "-C", str(repository_root), "rev-parse", "HEAD"])
    status = _run(["git", "-C", str(repository_root), "status", "--porcelain"])
    changed_count = len(status.splitlines()) if status else 0
    return {
        "commit": revision,
        "workingTreeDirty": changed_count > 0,
        "changedPathCount": changed_count,
    }


def _run(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise IdentityEvidenceError(f"Command failed: {command[0]} {command[1] if len(command) > 1 else ''}.")
    return completed.stdout.strip()


def _command_results(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    values = document.get("commands")
    if document.get("schemaVersion") != 1 or not isinstance(values, list):
        raise IdentityEvidenceError("Command evidence document is invalid.")
    result = {}
    for item in values:
        if not isinstance(item, Mapping):
            raise IdentityEvidenceError("Command evidence item is invalid.")
        identifier = item.get("id")
        passed = item.get("passed")
        if not isinstance(identifier, str) or not isinstance(passed, bool):
            raise IdentityEvidenceError("Command evidence item omitted id or passed.")
        if identifier in result:
            raise IdentityEvidenceError(f"Duplicate command evidence: {identifier}.")
        result[identifier] = {
            "id": identifier,
            "passed": passed,
            "exitCode": item.get("exitCode"),
            "durationMilliseconds": item.get("durationMilliseconds"),
        }
    return result


def _artifact_status(path: Path, identifier: str) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "passed": False}
    payload = load_json_object(path)
    passed = payload.get("passed") is True
    if identifier == "key-rotation":
        old_kid = payload.get("oldKid")
        new_kid = payload.get("newKid")
        retained = payload.get("retainedKids")
        passed = (
            isinstance(old_kid, str)
            and isinstance(new_kid, str)
            and old_kid != new_kid
            and isinstance(retained, list)
            and old_kid in retained
            and payload.get("postVerificationPassed") is True
            and payload.get("samlMetadataOldCertificatesRetained") is True
        )
    elif identifier == "browser-evidence":
        events = payload.get("events")
        passed = payload.get("schemaVersion") == 1 and isinstance(events, list) and bool(events)
    result = {
        "present": True,
        "passed": passed,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    for key in ("classification", "checkedAtUtc", "rotatedAtUtc"):
        if isinstance(payload.get(key), str):
            result[key] = payload[key]
    return result


def _resolve_evidence(
    item: Mapping[str, Any],
    commands: Mapping[str, Mapping[str, Any]],
    artifacts: Mapping[str, Mapping[str, Any]],
    restart: Mapping[str, Any] | None,
) -> dict[str, Any]:
    kind = item["kind"]
    reference = item["reference"]
    if kind == "command":
        source = commands.get(reference, {"passed": False})
    elif kind == "artifact":
        source = artifacts.get(reference, {"passed": False})
    else:
        source = restart if reference == "restart-stability" and restart is not None else {"passed": False}
    return {"kind": kind, "reference": reference, "passed": source.get("passed") is True}


def _assert_redacted(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if _is_sensitive_key(key):
                raise IdentityEvidenceError(f"Refusing to export sensitive evidence key at {path}.{key}.")
            _assert_redacted(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_redacted(child, f"{path}[{index}]")
    elif isinstance(value, str) and "bearer " in value.casefold():
        raise IdentityEvidenceError(f"Refusing to export possible bearer material at {path}.")


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    normalized = re_alphanumeric(key)
    return normalized in SENSITIVE_KEYS or normalized.endswith("password") or normalized.endswith("secret")


def re_alphanumeric(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture redacted Northlake identity evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--repository-root", required=True, type=Path)
    validate.add_argument("--catalog", required=True, type=Path)
    validate.add_argument("--faults", required=True, type=Path)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--connection", required=True, type=Path)
    snapshot.add_argument("--ca-file", required=True, type=Path)
    snapshot.add_argument("--catalog", required=True, type=Path)
    snapshot.add_argument("--compose", required=True, type=Path)
    snapshot.add_argument("--output", required=True, type=Path)

    compare = subparsers.add_parser("compare")
    compare.add_argument("--before", required=True, type=Path)
    compare.add_argument("--after", required=True, type=Path)
    compare.add_argument("--outage-observed", action="store_true")
    compare.add_argument("--output", required=True, type=Path)

    export = subparsers.add_parser("export")
    export.add_argument("--repository-root", required=True, type=Path)
    export.add_argument("--eem-repository-root", required=True, type=Path)
    export.add_argument("--catalog", required=True, type=Path)
    export.add_argument("--faults", required=True, type=Path)
    export.add_argument("--runtime", required=True, type=Path)
    export.add_argument("--commands", required=True, type=Path)
    export.add_argument("--restart", required=True, type=Path)
    export.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "validate":
            catalog = load_json_object(args.catalog.resolve())
            faults = load_json_object(args.faults.resolve())
            validate_coverage_catalog(catalog, args.repository_root.resolve())
            validate_fault_catalog(faults)
            print("[OK] Coverage and deterministic fault catalogs are complete.")
            return 0
        if args.command == "snapshot":
            value = capture_stable_snapshot(
                args.connection.resolve(),
                args.ca_file.resolve(),
                args.catalog.resolve(),
                args.compose.resolve(),
            )
        elif args.command == "compare":
            value = compare_stable_snapshots(
                load_json_object(args.before.resolve()),
                load_json_object(args.after.resolve()),
                outage_observed=args.outage_observed,
            )
        else:
            value = export_evidence(
                args.repository_root.resolve(),
                args.eem_repository_root.resolve(),
                args.catalog.resolve(),
                args.faults.resolve(),
                args.runtime.resolve(),
                args.commands.resolve(),
                args.restart.resolve(),
            )
        write_json(args.output.resolve(), value)
        print(f"[OK] Wrote redacted identity evidence to {args.output}.")
        return 0 if value.get("passed", True) else 1
    except (
        OSError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
        ssl.SSLError,
        ElementTree.ParseError,
        EvidenceCatalogError,
        IdentityEvidenceError,
    ) as failure:
        print(f"[ERROR] {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
