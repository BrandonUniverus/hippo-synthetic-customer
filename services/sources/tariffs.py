"""Versioned synthetic tariff extensions. Historical provider manifests stay read-only."""
from __future__ import annotations

import copy
import io
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

CENT = Decimal("0.01")
RATE_PRECISION = Decimal("0.000001")


def decimal(value):
    return Decimal(str(value))


def money(value):
    return decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def annual_factor(provider_id, component_path, year):
    """Only currency rates escalate; tax/physical constants are never passed here."""
    if provider_id == "helios_onsite_solar":
        return Decimal("1.02") ** max(0, year - 2024) if component_path == "ppaEnergy" else Decimal(1)
    if provider_id == "ridgeline_wind":
        return Decimal(1)
    return Decimal("1.03") ** max(0, year - 2025)


def tariff_for(provider, schedule_id, year):
    # The ordinary general-service tariff's actual 2025 step remains authoritative.
    wanted = "VED-TOU-GS-FY25" if schedule_id == "VED-TOU-GS" and year >= 2025 else schedule_id
    source = next(schedule for schedule in provider["rateSchedules"] if schedule["id"] == wanted)
    result = copy.deepcopy(source)
    pending = [(result["components"], "")]
    while pending:
        node, path = pending.pop()
        if isinstance(node, list):
            pending.extend((child, f"{path}.{index}") for index, child in enumerate(node))
        elif isinstance(node, dict):
            if "rate" in node and str(node.get("unit", "")).startswith("$"):
                rate = decimal(node["rate"]) * annual_factor(provider["id"], path, year)
                node["rate"] = rate.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)
            pending.extend((child, f"{path}.{key}".strip(".")) for key, child in node.items() if isinstance(child, (dict, list)))
    result["sourceScheduleId"] = source["id"]
    result["id"] = f"{source['id']}-SYN-{year}" if year >= 2026 else source["id"]
    first = date(year, 1, 1)
    if year <= 2025:
        first = max(first, date.fromisoformat(source["effective"].split("..")[0]))
    result["effective"] = f"{first}..{year}-12-31"
    result["syntheticExtension"] = year >= 2026 or year == 2023
    return result


def tariff_rate(provider, schedule_id, component_path, year):
    node = tariff_for(provider, schedule_id, year)["components"]
    for key in component_path.split("."):
        node = node[int(key)] if isinstance(node, list) else node[key]
    return decimal(node["rate"])


def json_bytes(value):
    return (json.dumps(value, default=lambda item: str(item) if isinstance(item, Decimal) else item.isoformat(),
                       sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def generate_tariff_artifacts(as_of_date, source_root, since_date=None):
    """Yield immutable annual JSON/PDF schedules, never write the source documents."""
    from generators.documents.render_northlake_pdf import render_markdown
    root = Path(source_root)
    providers = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted((root / "data/providers").glob("*.yaml"))]
    for year in range(2024, as_of_date.year + 1):
        if since_date and year < since_date.year:
            continue
        for provider in providers:
            schedules = [tariff_for(provider, item["id"], year) for item in provider["rateSchedules"]
                         if not (item["id"] == "VED-TOU-GS-FY25" and year == 2024)
                         and not (item["id"] == "VED-TOU-GS" and year >= 2025)]
            document = {"provider": provider["id"], "year": year, "synthetic": True,
                        "policy": "Historical values preserved; from 2026 currency charges +3% annually; Helios PPA +2% from 2024, export credit fixed; Ridgeline fixed terms. VED general-service periods split on rate-year boundaries; other annual versions use the billing-period end year.",
                        "schedules": schedules}
            stem = f"tariffs/{provider['id']}/{year}"
            metadata = {"kind": "tariff", "provider": provider["id"], "source": provider["id"],
                        "period_start": f"{year}-01-01", "period_end": f"{year}-12-31", "ordinary_delivery": False}
            yield {"path": stem + ".json", "content": json_bytes(document), "media_type": "application/json", "metadata": dict(metadata, artifact="json")}
            lines = [f"# {provider['displayName']} - {year}", "", document["policy"], "",
                     "Every rate is fictional. This annual publication does not install a rate in EEMSuite.", ""]
            for schedule in schedules:
                lines.extend([f"## {schedule['id']}", "", "| Component | Unit | Rate |", "| --- | --- | ---: |"])
                pending = [(schedule["components"], "")]
                while pending:
                    node, path = pending.pop(0)
                    if isinstance(node, list):
                        pending.extend((child, f"{path}.{index}") for index, child in enumerate(node))
                    elif isinstance(node, dict):
                        if "rate" in node:
                            lines.append(f"| {path} | {node.get('unit', '')} | {node['rate']} |")
                        pending.extend((child, f"{path}.{key}".strip(".")) for key, child in node.items() if isinstance(child, (dict, list)))
                lines.append("")
            output = io.BytesIO()
            render_markdown("\n".join(lines), output, {"title": f"{provider['displayName']} - {year}", "date": f"January 1, {year}",
                                                       "prepared_by": provider["displayName"], "document_type": "Synthetic annual tariff"})
            yield {"path": stem + ".pdf", "content": output.getvalue(), "media_type": "application/pdf", "metadata": dict(metadata, artifact="pdf")}
