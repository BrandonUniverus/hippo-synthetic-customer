"""Generate the preview-first Northlake Stage 3 point-binding script.

The hand-maintained Stage 2 point identities and Stage 3 gateway recipe own the
data. No database connection is used. Run python -m generators.gateway_assignments
or add --check to verify the committed SQL without rewriting it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml

from generators.stage_check_data import UniqueLoader

ROOT = Path(__file__).resolve().parents[1]
STAGE2 = Path("implementation/stage-2-hierarchy")
STAGE3 = Path("implementation/stage-3-gateways-and-data")
SOURCES = [STAGE2 / name for name in ("02-sites-and-buildings.yaml", "03-meters.yaml", "04-points.yaml")]
SOURCES.append(STAGE3 / "02-gateways.yaml")
SOURCES.append(STAGE3 / "02-weather-binding-migration.yaml")
OUTPUT = STAGE3 / "02-gateway-point-assignments.sql"
NOAA_GATEWAY_TYPE = "NOAA / ECCC Weather Gateway"


def expand_points(entries):
    """Expand the recipe's explicit, bounded apartment and turbine ranges."""
    for entry in entries:
        if not entry.get("pointTemplate"):
            yield entry
            continue
        match = re.fullmatch(r"(.+) for (\w+) in ((?:\d+\.\.\d+)(?:,\d+\.\.\d+)*)", entry["channelPattern"])
        if not match:
            raise ValueError(f"Unsupported channel pattern: {entry['channelPattern']}")
        pattern, variable, ranges = match.groups()
        numbers = []
        for span in ranges.split(","):
            first, last = span.split("..")
            numbers.extend(str(n).zfill(len(first)) if first.startswith("0") else str(n)
                           for n in range(int(first), int(last) + 1))
        if len(numbers) != entry["count"]:
            raise ValueError(f"Template count does not match its range: {pattern}")
        if len(numbers) != len(set(numbers)):
            raise ValueError(f"Overlapping template ranges: {pattern}")
        for number in numbers:
            replacement = {variable: number}
            params = {}
            for field in entry.get("Point Parameters pattern", "").split(", "):
                if field:
                    label, field_value = field.split(": ", 1)
                    params[label] = field_value.format(**replacement)
            expanded = {"channel": pattern.format(**replacement), "Point Parameters": params}
            for field in ("Description", "Reading Point", "Consumption Point", "Company", "Parent"):
                if field in entry:
                    expanded[field] = entry[field].format(**replacement)
            if "Meter pattern" in entry:
                expanded["Meter"] = {field: value.format(**replacement)
                                     for field, value in entry["Meter pattern"].items()}
            if "relatedReadingChannelPattern" in entry:
                expanded["relatedReadingChannel"] = entry["relatedReadingChannelPattern"].format(**replacement)
            yield expanded


def parameter_values(parameters, supplied):
    """Resolve labels to physical columns and explicitly enable readable inputs."""
    definitions = {p["Label"]: p for p in parameters}
    columns = [p["Column"] for p in parameters]
    if len(definitions) != len(parameters) or len(columns) != len(set(columns)) or any(not 1 <= n <= 15 for n in columns):
        raise ValueError("Duplicate label or invalid parameter column")
    values = dict(supplied)
    enabled = definitions.get("IsEnabled")
    if enabled and not enabled["Reads"].lower().startswith("not read"):
        values.setdefault("IsEnabled", "1")
    if "Disabled" in definitions:
        values.setdefault("Disabled", "0")
    result = [None] * 15
    for label, value in values.items():
        if label not in definitions:
            raise ValueError(f"Unknown parameter: {label}")
        definition = definitions[label]
        column = definition["Column"]
        text = None if value is None or value == "" else str(value)
        if text is not None and len(text) > 255:
            raise ValueError(f"Parameter exceeds SQL column length: {label}")
        result[column - 1] = text
    return result


def build_data(documents):
    hierarchy, meter_doc, point_doc, gateway_doc, migration_doc = documents
    previous_bindings = {record["channel"]: record["Existing binding"] for record in migration_doc["records"]}
    if len(previous_bindings) != len(migration_doc["records"]):
        raise ValueError("Duplicate weather migration channel")
    owners = {r["Definitions"]["Description"]: r["Company"] for r in hierarchy["records"]}
    meters = {r["Meter Definition"]["Meter Number"]: r for r in meter_doc["records"]}
    points = {r["key"]: r for r in point_doc["records"]}
    if len(points) != len(point_doc["records"]):
        raise ValueError("Duplicate Stage 2 point key")
    types = {r["Name"]: r for r in gateway_doc["gatewayTypes"]}
    rows, profiles, nodes, metadata = [], [], [], []
    assigned = set()
    identities = set()
    for gateway in gateway_doc["records"]:
        if not gateway.get("Nodes"):
            # The handheld gateways have no nodes or points: their meters are HMR configuration (Step 5,
            # 05-handheld-routes.yaml), and Stage 3 checks.sql checks their parameterless type.
            continue
        profile_key = gateway["key"]
        vendor = gateway["Gateway"]["Vendor"]
        if profile_key == "gw_noaa_ksac_observations" and vendor != NOAA_GATEWAY_TYPE:
            raise ValueError("The NOAA profile must use its separate NOAA gateway type")
        definition = types[vendor]
        profiles.append({"Key": profile_key, "Name": gateway["Gateway"]["Description"], "Vendor": vendor})
        for node in gateway["Nodes"]:
            nodes.append({"Profile": profile_key, "Key": node["key"], "Name": node["Description"],
                          "Params": parameter_values(definition.get("Node Parameters", []), node.get("Node Parameters", {}))})
            for binding in expand_points(node.get("Points", [])):
                channel = binding["channel"]
                if channel in assigned:
                    raise ValueError(f"Point assigned more than once: {channel}")
                assigned.add(channel)
                target = binding.get("Gateway binding")
                if profile_key == "gw_noaa_ksac_observations" or target is not None:
                    if target != {"Gateway": gateway["Gateway"]["Description"], "Node": node["Description"]}:
                        raise ValueError(f"Gateway binding does not match its parent gateway and node: {channel}")
                point = points[channel]  # A missing Stage 2 point is an error, never a fuzzy match.
                point_def = point["Point Definition"]
                if "Meter" in point:
                    number = point["Meter"]["Meter Number"]
                    meter = meters[number]
                    if point["Meter"]["Description"] != meter["Meter Definition"]["Description"]:
                        raise ValueError(f"Stage 2 meter identity mismatch: {channel}")
                    owner, parent = owners[meter["Building"]], meter["Meter Definition"]["Description"]
                    if binding.get("Meter") != point["Meter"]:
                        raise ValueError(f"Gateway point lookup does not match the Stage 2 meter: {channel}")
                else:
                    number, parent = "", point["Parent"]
                    owner = owners[parent]
                    if binding.get("Parent") != parent:
                        raise ValueError(f"Gateway point lookup does not match the Stage 2 parent: {channel}")
                if binding.get("Description") != point_def["Description"] or binding.get("Company") != owner:
                    raise ValueError(f"Gateway point lookup does not match the Stage 2 identity: {channel}")
                identity = (owner, number, parent, point_def["Description"])
                if identity in identities:
                    raise ValueError(f"Ambiguous Stage 2 point identity: {identity}")
                identities.add(identity)
                row = {"Channel": channel, "Profile": profile_key, "Node": node["key"],
                             "Company": owner, "Meter": number, "Parent": parent,
                             "Point": point_def["Description"], "ReadingType": point_def["Reading Type"],
                             "Interval": point_def["Archive Interval"],
                             "Params": parameter_values(definition.get("Point Parameters", []), binding.get("Point Parameters", {}))}
                if channel in previous_bindings:
                    legacy = previous_bindings[channel]
                    names = legacy.get("GatewayNames")
                    params = legacy.get("Params")
                    if (vendor != NOAA_GATEWAY_TYPE or profile_key != "gw_noaa_ksac_observations"
                            or not isinstance(names, list) or not names
                            or not all(isinstance(name, str) and name.strip() for name in names)
                            or not isinstance(legacy.get("Node"), str) or not legacy["Node"].strip()
                            or not isinstance(params, list) or not 1 <= len(params) <= 15
                            or not all(value is None or isinstance(value, str) and len(value) <= 255 for value in params)):
                        raise ValueError(f"Invalid legacy weather binding: {channel}")
                    row["Legacy"] = {"GatewayNames": names, "Node": legacy["Node"],
                                     "Params": params + [None] * (15 - len(params))}
                rows.append(row)
    if previous_bindings.keys() - {row["Channel"] for row in rows}:
        raise ValueError("Weather migration channel does not identify a direct point binding")
    for vendor in sorted({p["Vendor"] for p in profiles}):
        for kind, sign in (("Node Parameters", -1), ("Point Parameters", 1)):
            for param in types[vendor].get(kind, []):
                metadata.append({"Vendor": vendor, "Column": sign * param["Column"], "Label": param["Label"],
                                 "Type": param["Type"]})
    return {"Profiles": profiles, "Nodes": nodes, "Metadata": metadata, "Points": rows}


def render(root=ROOT):
    documents = [yaml.load((root / path).read_text(encoding="utf-8"), Loader=UniqueLoader) for path in SOURCES]
    data = build_data(documents)
    fingerprints = "\n".join(f"-- {path.as_posix()}: SHA256 {hashlib.sha256((root / path).read_bytes()).hexdigest()}" for path in SOURCES)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("'", "''")
    template = (root / "generators/gateway_assignments.sql").read_text(encoding="utf-8")
    return template.replace("-- SOURCE HASHES", fingerprints).replace("__EXPECTED_JSON__", payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    path = ROOT / OUTPUT
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            raise SystemExit(f"Stale SQL: {OUTPUT}. Run python -m generators.gateway_assignments")
        print(f"Current: {OUTPUT}")
    else:
        path.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
