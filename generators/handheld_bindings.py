"""Export checked Northlake pilot bindings without changing the database.

The actual HMR export and explicit opening readings are required. The simulator
validates the export against this manifest before accepting a reader round.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen

import yaml

from generators.stage_check_data import ROOT, UniqueLoader, load_handheld_expectations


PILOT_ROUTES = {
    "CRBMW": ("water_keyed", "neptune", "kgal", "crbmw-pilot"),
    "SCGAS": ("gas_keyed", "mvrs", "therm", "scgas-pilot"),
}


def pilot_expectations(routes):
    _, data = load_handheld_expectations()
    folder = ROOT / "implementation/stage-3-gateways-and-data"
    gateways = yaml.load((folder / "02-gateways.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
    gateway_names = {row["key"]: row["Gateway"]["Description"] for row in gateways["records"]}
    recipe = yaml.load((folder / "05-handheld-routes.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
    types = {row["key"]: row for row in recipe["readTypes"]}
    selected = []
    for route in routes:
        if route not in PILOT_ROUTES:
            raise ValueError(f"Unsupported pilot route: {route}")
        matches = [row for row in data["meters"] if row["Route"] == route]
        if len(matches) != 1:
            raise ValueError(f"Pilot route must resolve one canonical meter: {route}")
        type_key, format_name, unit, target = PILOT_ROUTES[route]
        selected.append(matches[0] | {"ReadTypeFields": types[type_key], "ReadTypeKey": type_key,
                                     "GatewayName": gateway_names[matches[0]["Gateway"]],
                                     "Format": format_name, "DisplayUnit": unit, "DeliveryTarget": target})
    return selected


def source_pin(catalog_url):
    with urlopen(catalog_url, timeout=20) as response:
        catalog = json.load(response)
    identity = catalog["identity"]
    contracts = [row for row in catalog["artifacts"] if row["path"] == "contracts/source-model.json"]
    if len(contracts) != 1:
        raise ValueError("Source catalog must contain one source-model contract")
    contract_url = urljoin(catalog_url, contracts[0]["url"])
    if urlsplit(contract_url).netloc != urlsplit(catalog_url).netloc:
        raise ValueError("Source contract must use the catalog's origin")
    with urlopen(contract_url, timeout=20) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != contracts[0]["sha256"]:
        raise ValueError("Source contract hash does not match the published catalog")
    contract = json.loads(content)
    if (contract["source_hash"] != identity["source_hash"] or contract["model_version"] != identity["version"]
            or contract["seed"] != identity["seed"]):
        raise ValueError("Source contract and catalog identify different releases")
    return {"release_id": identity["release_id"], "model_version": identity["version"],
            "source_hash": identity["source_hash"], "seed": identity["seed"],
            "assumptions_version": contract["assumptions"]["version"]}


def binding_query(expected):
    payload = json.dumps(expected, separators=(",", ":"), ensure_ascii=False).replace("'", "''")
    return """SET NOCOUNT ON;
IF DB_NAME()<>N'EEMSuite_Northlake' THROW 51000,'Use EEMSuite_Northlake only.',1;
DECLARE @Expected nvarchar(max)=N'""" + payload + """';
SELECT e.[Key] AS channel_key,p.PtID AS reading_pt_id,usage.PtID AS usage_pt_id,
    m.MetaWorldID AS meter_id,h.HMR_MeterID AS hmr_meter_id,r.HMR_ReadingID AS hmr_reading_id,
    h.CycleID AS cycle,h.RouteNumber AS route,h.ReadSequence AS sequence,h.active AS active,
    r.TextPrompt AS text_prompt,r.Channel AS channel,r.MeterConstant AS meter_constant,
    p.DeltaMultiplier AS delta_multiplier,inputUnit.UN_Units AS raw_unit,usageUnit.UN_Units AS usage_unit,
    rt.Description AS type_description,rt.ERTType AS ert_type,rt.NumDials AS num_dials,rt.NumDecimals AS num_decimals,
    rt.ReadTypeCode AS read_type_code,rt.ReadDirection AS read_direction,rt.DemandRead AS demand_read,
    rt.TruncationFactor AS truncation_factor,g.hSiERtDb AS gateway_id
FROM OPENJSON(@Expected) WITH
([Key] nvarchar(128),Company nvarchar(64),MeterNumber nvarchar(100),MeterDescription nvarchar(256),
 ReadingDescription nvarchar(64),GatewayName nvarchar(128)) e
LEFT JOIN dbo.Company_TBL c ON c.CompanyName=e.Company
LEFT JOIN dbo.MetaWorld_TBL mw ON mw.CompanyID=c.CompanyID AND mw.Description=e.MeterDescription AND ISNULL(mw.DeleteInd,0)=0
LEFT JOIN dbo.Meter m ON m.MetaWorldID=mw.MetaWorldID AND m.SM_Code=e.MeterNumber
LEFT JOIN dbo.MetaWorld_TBL pn ON pn.ParentID=m.MetaWorldID AND ISNULL(pn.DeleteInd,0)=0
    AND EXISTS(SELECT 1 FROM dbo.PointDef_TBL candidate WHERE candidate.MetaWorldID=pn.MetaWorldID
        AND candidate.Description=e.ReadingDescription AND candidate.PtType=3)
LEFT JOIN dbo.PointDef_TBL p ON p.MetaWorldID=pn.MetaWorldID AND p.Description=e.ReadingDescription AND p.PtType=3
LEFT JOIN dbo.PtRelatedData_TBL delta ON delta.PtID=p.PtID AND delta.ReasonType=N'D'
LEFT JOIN dbo.PointDef_TBL usage ON usage.PtID=delta.RelatedPtID AND usage.PtType=4
    AND EXISTS(SELECT 1 FROM dbo.MetaWorld_TBL usageNode WHERE usageNode.MetaWorldID=usage.MetaWorldID
        AND usageNode.ParentID=m.MetaWorldID AND ISNULL(usageNode.DeleteInd,0)=0)
LEFT JOIN dbo.Unit inputUnit ON inputUnit.UN_UnitID=p.UN_UnitID
LEFT JOIN dbo.Unit usageUnit ON usageUnit.UN_UnitID=usage.UN_UnitID
LEFT JOIN dbo.HMR_Meter h ON h.MetaWorldID=m.MetaWorldID
LEFT JOIN dbo.HMR_Reading r ON r.HMR_MeterID=h.HMR_MeterID AND r.Ptid_Reading=p.PtID AND r.Ptid_Usage=usage.PtID
LEFT JOIN dbo.HMR_ReadType rt ON rt.HMR_ReadTypeID=r.HMR_ReadTypeID
LEFT JOIN dbo.ObjectRegistry g ON g.Descriptor=e.GatewayName
FOR JSON PATH,INCLUDE_NULL_VALUES;
"""


def read_bindings(expected, server):
    env = os.environ.copy()
    for name in ("SQLCMDUSER", "SQLCMDPASSWORD"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="northlake-handheld-query-") as folder:
        path = Path(folder) / "bindings.sql"
        path.write_text(binding_query(expected), encoding="utf-8")
        result = subprocess.run(["sqlcmd", "-S", server, "-d", "EEMSuite_Northlake", "-E", "-C", "-b",
                                 "-f", "65001", "-y", "0", "-w", "65535", "-i", str(path)],
                                env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError("Read-only Northlake binding query failed: " + (result.stderr or result.stdout).strip())
    output = result.stdout.strip()
    start = output.find("[")
    if start < 0:
        raise ValueError("Northlake did not return a binding array")
    return json.loads(output[start:])


def make_manifest(expected, rows, *, export_bytes, source, openings, environment_id, verified_at):
    if not export_bytes or not environment_id.strip():
        raise ValueError("An actual export file and nonempty environment ID are required")
    if len(rows) != len(expected) or len({row["channel_key"] for row in rows}) != len(rows):
        raise ValueError("Northlake pilot bindings are missing or ambiguous")
    by_key = {row["channel_key"]: row for row in rows}
    channels = []
    for wanted in expected:
        row = by_key.get(wanted["Key"])
        if row is None:
            raise ValueError(f"Missing pilot channel {wanted['Key']}")
        missing = [field for field in ("meter_id", "reading_pt_id", "usage_pt_id", "hmr_meter_id", "hmr_reading_id", "gateway_id")
                   if type(row.get(field)) is not int or row[field] <= 0]
        if missing:
            raise ValueError(f"{wanted['Route']}: complete app setup first; missing {', '.join(missing)}")
        type_fields = wanted["ReadTypeFields"]
        required = {"cycle": wanted["Cycle"], "route": wanted["Route"], "sequence": wanted["Sequence"],
                    "text_prompt": wanted["Prompt"], "channel": wanted["Channel"], "active": True,
                    "type_description": wanted["ReadType"], "ert_type": None, "num_dials": type_fields["NumDials"],
                    "num_decimals": 0, "read_type_code": type_fields["ReadTypeCode"], "read_direction": type_fields["ReadDirection"],
                    "demand_read": "N", "truncation_factor": type_fields["TruncationFactor"], "raw_unit": "Reading"}
        mismatch = [field for field, value in required.items() if row.get(field) != value]
        if str(row.get("usage_unit", "")).lower() != wanted["DisplayUnit"]:
            mismatch.append("usage_unit")
        try:
            multipliers_match = Decimal(str(row.get("meter_constant"))) == Decimal(str(row.get("delta_multiplier"))) == 1
        except InvalidOperation:
            multipliers_match = False
        if not multipliers_match:
            mismatch.append("pilot multipliers (both must be 1)")
        if mismatch:
            raise ValueError(f"{wanted['Route']}: stored configuration differs from controlled pilot: {', '.join(mismatch)}")
        opening = openings[wanted["Route"]]
        if type(opening["value"]) is not int or not 0 <= opening["value"] < 10 ** type_fields["NumDials"]:
            raise ValueError(f"{wanted['Route']}: opening must fit the integer register format")
        observed = datetime.fromisoformat(opening["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or opening["basis"] != "controlled-pilot" or not opening["reason"].strip():
            raise ValueError(f"{wanted['Route']}: opening requires offset, controlled-pilot basis and reason")
        channels.append({"channel_key": wanted["Key"], "reading_channel_key": wanted["ReadingChannel"],
                         "company": wanted["Company"], "meter_number": wanted["MeterNumber"], "meter_description": wanted["MeterDescription"],
                         **{field: row[field] for field in ("meter_id", "reading_pt_id", "usage_pt_id", "hmr_meter_id", "hmr_reading_id", "cycle", "route", "sequence", "text_prompt", "gateway_id")},
                         "channel": f"{row['channel']:02d}",
                         "read_type": {"key": wanted["ReadTypeKey"], **{field: row[field] for field in ("num_dials", "num_decimals", "read_type_code", "read_direction", "demand_read", "truncation_factor")}},
                         "meter_constant": "1", "delta_multiplier": "1", "raw_unit": "Reading",
                         "display_unit": wanted["DisplayUnit"], "usage_unit": wanted["DisplayUnit"],
                         "gateway_profile": wanted["Gateway"], "return_format": wanted["Format"],
                         "delivery_target": wanted["DeliveryTarget"], "opening": dict(opening)})
    return {"schema": "northlake-handheld-bindings-v1", "environment_id": environment_id,
            "database": "EEMSuite_Northlake", "verified_at": verified_at,
            "export_sha256": hashlib.sha256(export_bytes).hexdigest(), "purpose": "controlled-pilot",
            "source": dict(source), "channels": channels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True, type=Path, help="Actual Northlake HMR route export")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--server", default="BVirtualPC")
    parser.add_argument("--environment-id", default="northlake-local")
    parser.add_argument("--source-catalog", default="http://localhost:18081/catalog.json")
    parser.add_argument("--route", action="append", choices=tuple(PILOT_ROUTES))
    parser.add_argument("--opening-water", type=int)
    parser.add_argument("--opening-gas", type=int)
    parser.add_argument("--opening-at", required=True, help="Explicit opening timestamp with UTC offset")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        expected = pilot_expectations(args.route or list(PILOT_ROUTES))
        values = {"CRBMW": args.opening_water, "SCGAS": args.opening_gas}
        if any(values[row["Route"]] is None for row in expected):
            raise ValueError("Supply the explicit opening value for each selected route")
        if args.output.exists() and not args.overwrite:
            raise ValueError("Output already exists; select a new file or use --overwrite")
        if args.output.resolve() == args.export.resolve():
            raise ValueError("The manifest output must not replace the original route export")
        openings = {row["Route"]: {"value": values[row["Route"]], "observed_at": args.opening_at,
                    "basis": "controlled-pilot", "reason": "Explicit controlled opening; not retained canonical history"} for row in expected}
        manifest = make_manifest(expected, read_bindings(expected, args.server), export_bytes=args.export.read_bytes(),
                                 source=source_pin(args.source_catalog), openings=openings,
                                 environment_id=args.environment_id, verified_at=datetime.now(timezone.utc).isoformat())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w" if args.overwrite else "x", encoding="utf-8") as output:
            output.write(json.dumps(manifest, indent=2) + "\n")
        print(f"Wrote {len(manifest['channels'])} checked pilot bindings to {args.output}; database unchanged.")
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
