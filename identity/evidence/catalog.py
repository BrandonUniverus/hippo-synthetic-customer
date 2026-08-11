"""Validation helpers for the Phase 9 coverage and fault-fixture catalogs."""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


CLASSIFICATIONS = frozenset(
    {
        "supported-pass",
        "supported-controlled-failure",
        "unsupported-clean-rejection",
        "future-capability",
        "forbidden-security-downgrade",
    }
)
ENVIRONMENTS = frozenset(
    {
        "stable",
        "lab",
        "installed-eem",
        "external-conformance",
        "external-vendor",
        "customer-acceptance",
    }
)
FAULT_CLASSES = frozenset(
    {"malformed", "tampered", "replayed", "unavailable", "stale", "oversized"}
)
_SCENARIO_ID = re.compile(r"^[a-z][a-z0-9-]{2,95}$")
_CHECKPOINT_ID = re.compile(r"^[A-Z][A-Z0-9-]*\d+[A-Z]?$", re.ASCII)


class EvidenceCatalogError(ValueError):
    """Raised when checked-in Phase 9 evidence metadata is inconsistent."""


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        raise EvidenceCatalogError(f"Unable to read {path.name}: {failure}") from failure
    if not isinstance(value, dict):
        raise EvidenceCatalogError(f"{path.name} must contain one JSON object.")
    return value


def validate_coverage_catalog(catalog: Mapping[str, Any], repository_root: Path) -> None:
    if catalog.get("schemaVersion") != 1:
        raise EvidenceCatalogError("Coverage catalog schemaVersion must be 1.")
    scenario_version = catalog.get("scenarioVersion")
    if not isinstance(scenario_version, str) or not scenario_version.strip():
        raise EvidenceCatalogError("Coverage catalog scenarioVersion is required.")
    if catalog.get("classifications") != sorted(CLASSIFICATIONS):
        raise EvidenceCatalogError("Coverage catalog classifications do not match the fixed Phase 9 set.")
    stable_environment = catalog.get("stableEnvironment")
    if not isinstance(stable_environment, Mapping):
        raise EvidenceCatalogError("Coverage catalog stableEnvironment is required.")
    if (
        stable_environment.get("realmKey") != "northlake"
        or stable_environment.get("oidcProfile") != "Modern"
        or stable_environment.get("samlProfile") != "Standard"
        or stable_environment.get("faultControlsPermitted") is not False
    ):
        raise EvidenceCatalogError(
            "Stable environment must be the fault-free northlake Modern OIDC and Standard SAML baseline."
        )
    destructive_realms = stable_environment.get("destructiveScenarioRealms")
    if (
        not isinstance(destructive_realms, list)
        or len(destructive_realms) != 2
        or len(set(destructive_realms)) != 2
        or "northlake" in destructive_realms
        or any(not isinstance(realm, str) or not _SCENARIO_ID.fullmatch(realm) for realm in destructive_realms)
    ):
        raise EvidenceCatalogError("Stable environment must name two distinct non-stable lab realms.")
    sources = catalog.get("sources")
    required_sources = {
        "openidRpTesting": "https://openid.net/certification/connect_rp_testing/",
        "openidLogoutTesting": "https://openid.net/certification/connect_rp_logout_testing/",
        "openidConformanceSuite": "https://openid.net/certification/about-conformance-suite/",
    }
    if sources != required_sources:
        raise EvidenceCatalogError("Coverage catalog must retain the official OpenID conformance sources.")

    requirements = catalog.get("checkpointRequirements")
    if not isinstance(requirements, Mapping) or not requirements:
        raise EvidenceCatalogError("Coverage catalog checkpointRequirements are required.")
    required: set[tuple[str, str]] = set()
    for adr, checkpoints in requirements.items():
        if not isinstance(adr, str) or not re.fullmatch(r"ADR-0(21|22|26|27)", adr):
            raise EvidenceCatalogError(f"Unsupported ADR requirement: {adr!r}.")
        if not isinstance(checkpoints, list) or not checkpoints:
            raise EvidenceCatalogError(f"{adr} must declare at least one checkpoint.")
        if len(checkpoints) != len(set(checkpoints)):
            raise EvidenceCatalogError(f"{adr} checkpoint requirements contain duplicates.")
        for checkpoint in checkpoints:
            if not isinstance(checkpoint, str) or not _CHECKPOINT_ID.fullmatch(checkpoint):
                raise EvidenceCatalogError(f"Invalid checkpoint identifier: {checkpoint!r}.")
            required.add((adr, checkpoint))

    scenarios = catalog.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise EvidenceCatalogError("Coverage catalog scenarios are required.")
    identifiers: set[str] = set()
    covered: set[tuple[str, str]] = set()
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            raise EvidenceCatalogError("Every coverage scenario must be an object.")
        identifier = scenario.get("id")
        if not isinstance(identifier, str) or not _SCENARIO_ID.fullmatch(identifier):
            raise EvidenceCatalogError(f"Invalid scenario identifier: {identifier!r}.")
        if identifier in identifiers:
            raise EvidenceCatalogError(f"Duplicate scenario identifier: {identifier}.")
        identifiers.add(identifier)
        classification = scenario.get("expectedClassification")
        if classification not in CLASSIFICATIONS:
            raise EvidenceCatalogError(f"{identifier} uses an unknown classification.")
        environment = scenario.get("environment")
        if environment not in ENVIRONMENTS:
            raise EvidenceCatalogError(f"{identifier} uses an unknown environment.")
        if not isinstance(scenario.get("localRequired"), bool):
            raise EvidenceCatalogError(f"{identifier} must declare whether local evidence is required.")
        if environment == "stable" and classification != "supported-pass":
            raise EvidenceCatalogError(f"{identifier} would put a fault or future capability in stable.")
        if any(vendor in identifier for vendor in ("entra", "okta", "shibboleth")) and classification == "supported-pass":
            raise EvidenceCatalogError(f"{identifier} cannot claim vendor acceptance without vendor evidence.")

        adr_mappings = scenario.get("adrMappings")
        if not isinstance(adr_mappings, list) or not adr_mappings:
            raise EvidenceCatalogError(f"{identifier} must map to at least one ADR checkpoint.")
        for mapping in adr_mappings:
            if not isinstance(mapping, Mapping):
                raise EvidenceCatalogError(f"{identifier} has an invalid ADR mapping.")
            adr = mapping.get("adr")
            checkpoints = mapping.get("checkpoints")
            if not isinstance(adr, str) or not isinstance(checkpoints, list) or not checkpoints:
                raise EvidenceCatalogError(f"{identifier} has an incomplete ADR mapping.")
            for checkpoint in checkpoints:
                pair = (adr, checkpoint)
                if pair not in required:
                    raise EvidenceCatalogError(f"{identifier} maps unknown checkpoint {adr} {checkpoint}.")
                covered.add(pair)

        evidence = scenario.get("evidence")
        proof_gap = scenario.get("proofGap")
        if not isinstance(evidence, list):
            raise EvidenceCatalogError(f"{identifier} evidence must be a list.")
        if not evidence and not isinstance(proof_gap, Mapping):
            raise EvidenceCatalogError(f"{identifier} needs executable evidence or an explicit proof gap.")
        if scenario.get("localRequired") is True and not evidence:
            raise EvidenceCatalogError(f"{identifier} is locally required but has no executable evidence.")
        for item in evidence:
            _validate_evidence_reference(identifier, item, repository_root)
        if proof_gap is not None:
            if not isinstance(proof_gap, Mapping):
                raise EvidenceCatalogError(f"{identifier} proofGap must be an object.")
            if not _required_text(proof_gap, "code") or not _required_text(proof_gap, "reason"):
                raise EvidenceCatalogError(f"{identifier} proofGap requires code and reason.")

    missing = sorted(required - covered)
    if missing:
        formatted = ", ".join(f"{adr}/{checkpoint}" for adr, checkpoint in missing)
        raise EvidenceCatalogError(f"Coverage catalog omitted required checkpoints: {formatted}.")


def validate_fault_catalog(catalog: Mapping[str, Any]) -> None:
    if catalog.get("schemaVersion") != 1:
        raise EvidenceCatalogError("Fault catalog schemaVersion must be 1.")
    protocols = catalog.get("protocols")
    if not isinstance(protocols, Mapping) or set(protocols) != {"oidc", "saml"}:
        raise EvidenceCatalogError("Fault catalog must define exactly OIDC and SAML fixtures.")
    identifiers: set[str] = set()
    for protocol, fixtures in protocols.items():
        if not isinstance(fixtures, list):
            raise EvidenceCatalogError(f"{protocol} fault fixtures must be a list.")
        classes: set[str] = set()
        for fixture in fixtures:
            if not isinstance(fixture, Mapping):
                raise EvidenceCatalogError(f"{protocol} fault fixture must be an object.")
            identifier = fixture.get("id")
            fault_class = fixture.get("faultClass")
            if not isinstance(identifier, str) or not _SCENARIO_ID.fullmatch(identifier):
                raise EvidenceCatalogError(f"Invalid fault fixture identifier: {identifier!r}.")
            if identifier in identifiers:
                raise EvidenceCatalogError(f"Duplicate fault fixture identifier: {identifier}.")
            identifiers.add(identifier)
            if fault_class not in FAULT_CLASSES:
                raise EvidenceCatalogError(f"{identifier} has an unknown fault class.")
            if fault_class in classes:
                raise EvidenceCatalogError(f"{protocol} repeats the {fault_class} fault class.")
            classes.add(fault_class)
            if fixture.get("environment") != "lab-only":
                raise EvidenceCatalogError(f"{identifier} must remain lab-only.")
            recipe = fixture.get("recipe")
            if not isinstance(recipe, Mapping) or not recipe:
                raise EvidenceCatalogError(f"{identifier} requires a deterministic recipe.")
            if fixture.get("expectedClassification") != "supported-controlled-failure":
                raise EvidenceCatalogError(f"{identifier} must expect a controlled failure.")
        if classes != FAULT_CLASSES:
            missing = ", ".join(sorted(FAULT_CLASSES - classes))
            raise EvidenceCatalogError(f"{protocol} fault fixtures are incomplete: {missing}.")


def generate_pairwise_cases(parameters: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    """Return a deterministic greedy all-pairs matrix for small independent fields."""
    if len(parameters) < 2 or any(not values for values in parameters.values()):
        raise EvidenceCatalogError("Pairwise parameters need at least two non-empty fields.")
    names = list(parameters)
    candidates = [dict(zip(names, values, strict=True)) for values in itertools.product(*(parameters[name] for name in names))]
    uncovered: set[tuple[str, Any, str, Any]] = set()
    for left_index, left_name in enumerate(names):
        for right_name in names[left_index + 1 :]:
            for left_value in parameters[left_name]:
                for right_value in parameters[right_name]:
                    uncovered.add((left_name, left_value, right_name, right_value))
    selected: list[dict[str, Any]] = []
    while uncovered:
        scored = [(_covered_pairs(candidate, names) & uncovered, candidate) for candidate in candidates]
        coverage, best = max(scored, key=lambda item: (len(item[0]), _case_key(item[1], names)))
        if not coverage:
            raise EvidenceCatalogError("Unable to cover the requested pairwise matrix.")
        selected.append(best)
        uncovered -= coverage
        candidates.remove(best)
    return selected


def _validate_evidence_reference(identifier: str, item: Any, repository_root: Path) -> None:
    if not isinstance(item, Mapping):
        raise EvidenceCatalogError(f"{identifier} has an invalid evidence reference.")
    kind = item.get("kind")
    reference = item.get("reference")
    if kind not in {"command", "artifact", "restart"} or not isinstance(reference, str):
        raise EvidenceCatalogError(f"{identifier} has an unsupported evidence reference.")
    source_path = item.get("sourcePath")
    if source_path is not None:
        if (
            not isinstance(source_path, str)
            or "\\" in source_path
            or source_path.startswith("/")
            or ".." in Path(source_path).parts
            or not (repository_root / source_path).is_file()
        ):
            raise EvidenceCatalogError(f"{identifier} references a missing or unsafe source path.")


def _required_text(value: Mapping[str, Any], key: str) -> str | None:
    candidate = value.get(key)
    return candidate.strip() if isinstance(candidate, str) and candidate.strip() else None


def _covered_pairs(candidate: Mapping[str, Any], names: list[str]) -> set[tuple[str, Any, str, Any]]:
    return {
        (left_name, candidate[left_name], right_name, candidate[right_name])
        for left_index, left_name in enumerate(names)
        for right_name in names[left_index + 1 :]
    }


def _case_key(candidate: Mapping[str, Any], names: list[str]) -> tuple[str, ...]:
    return tuple(str(candidate[name]) for name in names)
