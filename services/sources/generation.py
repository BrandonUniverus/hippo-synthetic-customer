"""Streaming orchestration; importing generators does not rewrite the repository."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import yaml

from . import MODEL_VERSION
from .billing import generate_billing_artifacts
from .gateways import acceptance_samples, encode_compatibility, encode_partition
from .model import PACIFIC, SourceModel
from .tariffs import generate_tariff_artifacts


@lru_cache(maxsize=64)
def _canonical_yaml(raw):
    return json.dumps(yaml.safe_load(raw), sort_keys=True, default=str).encode()


@lru_cache(maxsize=8)
def _binding_contract(root, points, gateways):
    from .gateways import gateway_bindings
    bindings = [{k: v for k, v in b.items() if k not in {"description", "company"}} for b in gateway_bindings(root)]
    if ((root / "implementation/stage-2-hierarchy/04-points.yaml").read_bytes() != points
            or (root / "implementation/stage-3-gateways-and-data/02-gateways.yaml").read_bytes() != gateways):
        raise ValueError("Gateway source configuration changed while resolving its contract")
    return json.dumps(bindings, sort_keys=True, default=str).encode()


def source_fingerprint(source_root):
    root = Path(source_root)
    paths = set()
    for folder, pattern in (("data/providers", "*.yaml"), ("data/bills", "*.yaml"), ("services/sources", "*.py"), ("services/sources", "*.json"), ("generators", "*.py"), ("generators/documents", "*.py"), ("generators/documents/fonts", "*.ttf")):
        paths.update((root / folder).glob(pattern))
    paths.add(root / "data/scenarios/demo-university-v1.yaml")
    paths.update((root / "documents/intake-package/sample-data/acquisuite").rglob("*.log"))
    paths.add(root / "documents/intake-package/sample-data/acquisuite/expected-results.json")
    digest = hashlib.sha256()
    for path in sorted(paths):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        if path.suffix == ".yaml":
            digest.update(_canonical_yaml(path.read_bytes()))
        else:
            digest.update(path.read_bytes())
        digest.update(b"\0")
    # Hash the resolved consumer contract, not hand-maintained installed IDs,
    # progress notes or YAML comments that change during the user's stage work.
    digest.update(_binding_contract(root, (root / "implementation/stage-2-hierarchy/04-points.yaml").read_bytes(),
                                    (root / "implementation/stage-3-gateways-and-data/02-gateways.yaml").read_bytes()))
    return digest.hexdigest()


def create_model(source_root, seed=104729):
    model = SourceModel(source_root, seed)
    model.validate_anchors()
    return model


def iter_artifacts(*, start: datetime, through: datetime, seed: int, source_root: Path, include_acceptance=False, model=None):
    if start.tzinfo is None or through.tzinfo is None or through <= start:
        raise ValueError("Generation needs aware timestamps and a nonempty (start, through] window")
    model = model or create_model(source_root, seed)
    yield from encode_partition(model, start, through)
    start_day, through_day = start.astimezone(PACIFIC).date(), through.astimezone(PACIFIC).date()
    if through_day > start_day:
        yield from generate_billing_artifacts(model, through_day, since_date=start_day)
    if include_acceptance:
        yield from generate_tariff_artifacts(through_day, source_root)
    elif through_day.year > start_day.year:
        yield from generate_tariff_artifacts(through_day, source_root, since_date=start_day)
    if include_acceptance:
        yield from acceptance_samples(source_root)
        from datetime import timezone
        yield from encode_compatibility(model, datetime(2024, 1, 15, 8, tzinfo=timezone.utc), datetime(2024, 1, 16, 8, tzinfo=timezone.utc))
        contract = {
            "model_version": MODEL_VERSION, "seed": seed, "source_hash": source_fingerprint(source_root),
            "source_points": len(model.bindings), "assumptions": model.assumptions,
            "gateway_bindings": model.bindings,
            "provider_pages": {key: {"fictional_website": provider.get("website"), "relative_path": "providers/" + key.replace("_", "-") + "/"} for key, provider in model.providers.items()},
            "required_settings": {"MDEF": {"TimeStampType": "Utc"}, "MV9": {"TimeStampType": "Utc"}, "FIG": {"TimeStampType": "Utc"}, "FIXEDNETWORKS": {"TimeStampType": "Utc"}, "Ridgeline": {"TimeStampType": "Utc", "OffsetTimeMinutes": 480}},
            "boundaries": ["Source files and bills do not establish installed acceptance.", "Estimates remain source evidence; no structured EEM estimate flag is introduced.", "Bill images require the supported upload/association path."]}
        nodes = {(b["profile"], b["node"]): b for b in model.bindings if "RecorderID" in b["params"]}
        contract["configuration_deltas"] = [{"profile": profile, "node": node, "parameter": "TimeStampType", "current_recipe": b["node_params"].get("TimeStampType", "Local"), "required": "Utc", "point_time_zone": "unchanged (Pacific)"} for (profile, node), b in sorted(nodes.items())]
        yield {"path": "contracts/source-model.json", "content": json.dumps(contract, indent=2, sort_keys=True).encode(), "media_type": "application/json", "metadata": {"kind": "schema", "source": "source-model", "provider": "northlake", "ordinary_delivery": False}}
