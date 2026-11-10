"""Refresh embedded YAML expectations in the standalone stage checkers.

Run: python -m generators.stage_check_data
Verify that the SQL snapshots are current: python -m generators.stage_check_data --check
SQL queries outside the marked data block are hand-maintained. No database connection is used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "-- BEGIN YAML EXPECTATIONS\n"
END = "-- END YAML EXPECTATIONS"
WORKFLOW_BEGIN = "-- BEGIN WORKFLOW EXPECTATIONS\n"
WORKFLOW_END = "-- END WORKFLOW EXPECTATIONS"
HANDHELD_BEGIN = "-- BEGIN HANDHELD EXPECTATIONS\n"
HANDHELD_END = "-- END HANDHELD EXPECTATIONS"
HANDHELD_PASTE = "05-handheld-meters.csv"
# The paste's first row: column names Handheld Meter Setup recognises (handheldSetupPaste.ts PASTE_COLUMN_NAMES); the
# page ignores Starting Reading and Starting Date, which are for its Starting readings view.
HANDHELD_PASTE_COLUMNS = ("Meter #", "Meter", "Cycle", "Route", "Sequence", "Enabled", "Bill Code", "Meter Text", "Prompt",
                          "Read Type", "Constant", "Channel", "Tamper Code", "High Warning", "Low Warning", "Reading Point",
                          "Consumption Point", "Starting Reading", "Starting Date")
# The Starting readings view takes one value per line; one file per starting date, named by that date.
HANDHELD_STARTING = "05-handheld-starting-readings-{}.txt"
HANDHELD_OPERATIONS_BEGIN = "-- BEGIN HANDHELD OPERATIONS\n"
HANDHELD_OPERATIONS_END = "-- END HANDHELD OPERATIONS"
PACIFIC = "(GMT-08:00) Pacific Time (US & Canada); Tijuana"


class UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate YAML key at line {node.start_mark.line + 1}")
        return super().construct_mapping(node, deep=deep)


def load_stage(number):
    folder = ROOT / "implementation" / ("stage-1-foundation" if number == 1 else "stage-2-hierarchy")
    return folder, {path.name: yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
                    for path in sorted(folder.glob("*.yaml"))}


def item(*parts):
    return " | ".join(map(str, parts))


def company(value):
    return "Common" if value.startswith("Common (") else value


def fields(values):
    return {key.replace(" ", ""): str(value) if isinstance(value, date) else None if value == "" else value
            for key, value in values.items()}


ADDRESS_KEYS = ("Address", "Address 2", "City", "Region", "Postal Code", "Country", "Latitude", "Longitude")
CONTACT_KEYS = ("First Name", "Last Name", "Title", "Phone", "Cell", "Email")


def address(values):
    """Every address field, so a value typed where the YAML has none is reported too."""
    return {key: (values or {}).get(key) for key in ADDRESS_KEYS}


def contact(values):
    return {key: (values or {}).get(key) for key in CONTACT_KEYS}


def degree_day_unit(kind, parent_unit):
    scale = "C" if "(degC)" in parent_unit else "F"
    name = "Heating" if kind == "H" else "Cooling"
    return f"{name} Degree({scale}) Days - ({kind}DD({scale}))"


def expectations(number, files):
    rows = []

    def add(check, identity, values):
        rows.append({"check": check, "item": identity, "fields": fields(values)})

    if number == 1:
        for record in files["01-companies.yaml"]["records"]:
            definition = record["Definitions"]
            name = definition["Company Name"]
            add("01 Companies", name, {key: definition[key] for key in ("Archive Interval", "Time Zone", "Country")})
            add("01 Company addresses", name, record["Company Address"])
            add("01 Company contacts", name, record["Company Contact"])
            for level in record["Levels"]:
                add("01 Hierarchy levels", item(name, level["Level"]), {key: value for key, value in level.items() if key != "Level"} |
                    {"InternalLevelNbr": {"Site": 1, "Location": 2, "Meter": 4, "Point": 5}[level["Type"]],
                     "MetaType": "System" if level["Type"] == "Meter" else level["Type"]})
            for analog in definition["Alarm Settings"]["Analog"]:
                add("01 Alarm settings", item(name, "Analog", analog["Severity"]), {"Text": analog["Text"], "Color": analog["Color"]})
            for digital in definition["Alarm Settings"]["Digital"]:
                add("01 Alarm settings", item(name, "Digital", digital["State"]), {"Color": digital["Color"]})
            for scenario in record["Bill Scenarios"]["Used"]:
                add("01 Bill scenarios", item(name, scenario), {"Present": True})
        for record in files["02-utility-providers.yaml"]["records"]:
            definition = record["Definitions"]
            name = definition["Name"]
            add("02 Providers", name, {key: value for key, value in definition.items() if key != "Name"})
            add("02 Provider addresses", name, record["Provider Address"])
            add("02 Provider contacts", name, record["Provider Contact"])
            for remit in record["Remit Addresses"]:
                add("02 Remit addresses", item(name, remit["Address"]), remit)
            for cycle in record["Bill Cycles"]:
                for period in cycle["Periods"]:
                    add("02 Bill cycles", item(name, cycle["Cycle"], period["Year"], period["Period"]),
                        {key: value for key, value in period.items() if key not in ("Year", "Period")})
            for association in record["Associated Companies"]:
                add("02 Vendor associations", item(name, association["Company"]),
                    {key: value for key, value in association.items() if key != "Company"})
        for record in files["03-company-calendars.yaml"]["records"]:
            for period in record["Periods"]:
                add("03 Company calendars", item(record["Company"], period["Year"], period["Period"]),
                    {"CalendarTypeID": 1, **{key: value for key, value in period.items() if key not in ("Year", "Period")}})
        groups = files["04-groups.yaml"]
        for record in groups["records"]:
            identity = item(company(record["Company"]), record["Group ID"])
            add("04 Groups", identity, {"Name": record["Name"], "Shared": record["Shared"]})
            for section, permissions in record["Permissions"].items():
                if section == "Report Groups":
                    grants = [(category["Type"], key, category["Level"], None)
                              for category in permissions.values()
                              for key in (["*"] if category["Reports"] == "All" else [r["Key"] for r in category["Reports"]])]
                elif section == "Points":
                    grants = [("D", permissions["Key"], permissions["Level"], permissions["MetaCompanyID"])]
                else:
                    grants = [(groups["permissionTypes"][section], grant["Key"], grant["Level"], None) for grant in permissions]
                for kind, key, level, target in grants:
                    add("04 Permissions", item(identity, kind, key),
                        {"Type": kind, "Key": key, "Level": level, "MetaCompanyID": target, "Effective": 1, "PermissionParentID": None})
        scoped = set()
        for record in groups["records"]:
            scope = record["Permissions"].get("Points")
            if scope and scope["Key"] != "*" and scope["Key"] not in scoped:   # the node named last in its Node Scope path
                scoped.add(scope["Key"])   # two groups may scope the same node (the Ridgeline Wind Site)
                add("04 Scoped hierarchy", scope["Key"], {"CompanyID": scope["MetaCompanyID"], "Description": scope["Node Scope"].split(" > ")[-1]})
        for record in files["05-users.yaml"]["records"]:
            name = record["User Name"]
            add("05 Users", name, {"Company": company(record["Company"]), **{key: record[key] for key in
                ("Display Name", "Email", "IsAdmin", "Principal Type", "Authentication Policy", "Time Zone", "Inactive")}})
            for home, assignments in record["Groups"].items():
                for group in assignments:
                    add("05 Memberships", item(company(home), group, name), {"HomeCompany": company(record["Company"])})
    else:
        _, foundation = load_stage(1)
        labels = {record["Definitions"]["Company Name"]: {level["Type"]: level["Description"] for level in record["Levels"]}
                  for record in foundation["01-companies.yaml"]["records"]}
        account_by_key = {r["key"]: r for r in files["01-billing-accounts.yaml"]["records"]}
        account_by_number = {r["Definitions"]["Account Number"]: r for r in account_by_key.values()}
        nodes = {r["Definitions"]["Description"]: r for r in files["02-sites-and-buildings.yaml"]["records"]}
        meters = {r["key"]: r for r in files["03-meters.yaml"]["records"]}
        meters_by_number = {r["Meter Definition"]["Meter Number"]: r for r in meters.values()}
        points = {r["key"]: r for r in files["04-points.yaml"]["records"]}
        point_identities = {}   # (meter number, point description) -> checker identity

        def meter_named(reference, where):
            """A meter as the YAML names it: its Meter Number, with the Description the tree shows."""
            meter = meters_by_number.get(reference["Meter Number"])
            if meter is None or meter["Meter Definition"]["Description"] != reference["Description"]:
                raise ValueError(f"{where}: no meter {reference['Description']} ({reference['Meter Number']})")
            return meter
        for record in files["00-units.yaml"]["records"]:
            definition = record["Definitions"]
            name = definition["Unit Name"]
            if not record.get("Existing"):
                add("00 Units", name, {key: value for key, value in definition.items() if key != "Unit Name"})
            for association in record.get("Measure Types", []):
                add("00 Unit measure types", item(name, association["Measure Type"]), {"IsCommodity": association["Is Commodity"]})
            for conversion in record.get("Conversions", []):   # the row the definition writes: Reference from this unit
                add("00 Unit conversions", item(conversion["Reference"], name),
                    {"Multiply": conversion["Multiplier"], "Offset": conversion["Offset"]})
        for record in account_by_key.values():
            definition = record["Definitions"]
            identity = item(record["Company"], definition["Utility Provider"], definition["Account Number"])
            add("01 Billing accounts", identity, {"Previous Account Number": None} | {key: value for key, value in definition.items()
                if key not in ("Utility Provider", "Account Number", "Remit Address")} | {"Status": 1})
            add("01 Service addresses", identity, address(record["Service Address"]))
            add("01 Account addresses", identity, address(record["Account Address"]))
            add("01 Account contacts", identity, contact(record.get("Account Contact")))
            provider = next(r for r in foundation["02-utility-providers.yaml"]["records"] if r["Definitions"]["Name"] == definition["Utility Provider"])
            assert len(provider["Remit Addresses"]) == 1
            add("01 Account remit", identity, address(provider["Remit Addresses"][0]))
            # The first save writes its own Active row dated that day; the backdated row must be the earliest.
            history = sorted(record.get("Status", []), key=lambda entry: entry["As of Date"])
            active = [entry["As of Date"] for entry in history if entry["Status"] == "Active Billing Account"]
            add("01 Account status", identity, {"First Active": min(active) if active else None,
                "Current Status": history[-1]["Status"] if history else "Active Billing Account"})
            for note in record.get("Notes", []):
                add("01 Account notes", item(identity, note["Note"]), {"Present": True})
        for record in nodes.values():
            if record["key"] in ("sacramento_executive_airport", "sacramento_international_airport"):
                continue  # Explicitly optional legacy airport nodes in the recipe.
            name = record["Definitions"]["Description"]
            identity = item(record["Company"], name)
            level = record["Level"]
            is_building = level["Type"] == "Location"
            if is_building != ("Parent" in record) or level["Description"] != labels[record["Company"]][level["Type"]]:
                raise ValueError(f"{name}: Level {level} does not match its parent or the company's Stage 1 levels")
            add("02 Sites and buildings", identity, {"Parent": record.get("Parent"), "Level": level["Level"],
                "LevelLabel": level["Description"], "TimeZone": record["Definitions"]["Time Zone"],
                "Code": record["Definitions"]["Building Code" if is_building else "Site Code"], "SameCompanyAsParent": True})
            add("02 Node addresses", identity, address(record.get("Node Address")))
            for keyword in record["Keywords"]:
                if keyword["Type"] == "Department":
                    add("02 Department keywords", identity, {"Department": keyword["Attribute"]})
                else:
                    add("02 Node keywords", item(identity, keyword["Type"]), {"Value": keyword["Attribute"]})
            for keyword in record.get("Inherited Keywords", []):   # what the building shows; assigned on its parent
                source = nodes[keyword["From"]]
                if keyword["From"] != record.get("Parent") or {"Type": keyword["Type"], "Attribute": keyword["Attribute"]} not in source["Keywords"]:
                    raise ValueError(f"{name}: inherited {keyword['Type']} is not assigned on its parent {keyword['From']}")
                if keyword["Type"] == "Department":
                    add("02 Department keywords", identity, {"Department": keyword["Attribute"]})
            for history in (record["Area"] or {}).get("History", []):
                add("02 Floor areas", item(identity, history["Date"]), {"Area": history["Area"], "Unit": record["Area"]["Area Unit"]})
            for entry in record.get("Status", []):
                add("02 Building status", item(identity, entry["As of Date"]), {"Status": entry["Status"]})
            if record["Notes"]:
                add("02 Node notes", item(identity, record["Notes"]), {"Present": True})
        for record in meters.values():
            definition = record["Meter Definition"]
            parent = nodes[record["Building"]]
            identity = item(parent["Company"], definition["Meter Number"])
            account = account_by_number.get(definition["Billing Account"]) if definition["Billing Account"] else None
            if definition["Billing Account"] and account is None:
                raise ValueError(f"Meter {definition['Meter Number']}: no billing account {definition['Billing Account']}")
            add("03 Meters", identity, {"Parent": record["Building"], "SameCompanyAsParent": True, "Level": 4,
                "LevelLabel": labels[parent["Company"]]["Meter"], "TimeZone": PACIFIC,
                "AccountNumber": account["Definitions"]["Account Number"] if account else None,
                "AccountCompany": account["Company"] if account else None,
                **{key: value for key, value in definition.items() if key not in ("Meter Number", "Billing Account")},
                # The meter's current status is its latest SM row: Open unless the YAML's history ends otherwise.
                "Meter Multiplier": definition["Meter Multiplier"] or 1,
                "Status": max(record["Status"], key=lambda entry: entry["As of Date"])["Status"] if record.get("Status") else "Open"})
            # Keywords other than Department: the meter's own, or what it inherits from its building or site.
            ancestors = [parent] + ([nodes[parent["Parent"]]] if "Parent" in parent else [])
            inherited = {}
            for ancestor in reversed(ancestors):
                inherited |= {k["Type"]: k["Attribute"] for k in ancestor.get("Keywords", []) if k["Type"] != "Department"}
            direct = {k["Type"]: k["Attribute"] for k in record.get("Keywords", [])}
            for kind in sorted(set(inherited) | set(direct)):
                add("03 Meter keywords", item(identity, kind), {"Value": direct.get(kind, inherited.get(kind)), "Inherited": kind not in direct})
            for entry in record.get("Status", []):
                add("03 Meter status", item(identity, entry["As of Date"]), {"Status": entry["Status"]})
            if record.get("Notes"):
                add("03 Meter notes", item(identity, record["Notes"]), {"Present": True})
        add("03 Meter integrity", "All meters", {"BrokenMeterLinks": 0, "NodesWithoutMeter": 0})
        for key, record in points.items():
            definition = record["Point Definition"]
            if "Meter" in record:
                meter = meter_named(record["Meter"], f"Point {key}")
                owner, meter_number = nodes[meter["Building"]]["Company"], meter["Meter Definition"]["Meter Number"]
            else:  # a point placed directly under a building or site
                owner, meter_number = nodes[record["Parent"]]["Company"], ""
            identity = item(owner, meter_number, definition["Description"])
            point_identities[(meter_number, definition["Description"])] = identity
            expected = {key: value for key, value in definition.items() if key != "Description"}
            accumulator = definition["Reading Type"] == "Accumulator"
            if accumulator:
                expected["Unit"] = "Reading - (Reading)"  # the register; the unit typed on a new accumulator goes to its Delta
            add("04 Points", identity, expected | {"Level": 5, "LevelLabel": labels[owner]["Point"], "TimeZone": PACIFIC, "NodeLinkValid": True})
            if accumulator:
                add("04 Generated children", item(identity, "D"), {"Count": 1, "ValidCount": 1, "Unit": definition["Unit"]})
            if definition["Index"] == "Degree Days":
                for reason in ("H", "C"):
                    add("04 Generated children", item(identity, reason),
                        {"Count": 1, "ValidCount": 1, "Unit": degree_day_unit(reason, definition["Unit"])})
        add("04 Point integrity", "All points", {"OrphanChildren": 0, "BrokenNodeLinks": 0, "NodesWithoutPoint": 0, "UnexpectedROC": 0})
        for record in files["05-weather-stations.yaml"]["records"]:
            for assignment in record["Associate with Selected"]:
                station = next(m for m in meters.values() if m["Meter Definition"]["Description"] == assignment["Station"])
                add("05 Weather stations", item(record["Company"], assignment["Location"]),
                    {"AssignmentCompany": record["Company"], "StationCompany": nodes[station["Building"]]["Company"], "StationMeterNumber": station["Meter Definition"]["Meter Number"]})
        meter_buildings = {m["Meter Definition"]["Description"]: m["Building"] for m in meters.values()}
        for record in files["06-aggregates.yaml"]["records"]:
            definition = record["Create Aggregate Point"]
            parent = definition["Parent"]   # a site or building, or a billing meter (Ridgeline's farm transfer meter)
            owner = nodes[parent if parent in nodes else meter_buildings[parent]]["Company"]
            identity = item(owner, definition["Name"])
            add("06 Aggregates", identity, {key: value for key, value in definition.items() if key != "Name"} |
                {"ReadingType": "Analog", "TimeZone": PACIFIC, "Level": 5, "LevelLabel": labels[owner]["Point"], "Gateway": "Aggregation Gateway"})
            for member in record["Members"]:
                meter_named({"Meter Number": member["Meter Number"], "Description": member["Meter"]}, definition["Name"])
                member_identity = point_identities.get((member["Meter Number"], member["Point"]))
                if member_identity is None:
                    raise ValueError(f"{definition['Name']}: no point {member['Point']} under {member['Meter']}")
                add("06 Aggregate members", item(identity, member_identity),
                    {"Required": member["Required"], "Multiplier": member["Multiplier"]})
        # Baselines moved to Stage 3 (stage-3-gateways-and-data/06-baselines.yaml): Baseline For needs a gateway.
    identities = [(row["check"], row["item"]) for row in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate expected checker identity")
    return rows


def render_data(number):
    folder, files = load_stage(number)
    rows = expectations(number, files)
    hashes = [f"-- {name}: SHA256 {hashlib.sha256((folder / name).read_bytes()).hexdigest()}" for name in files]
    if number == 2:
        foundation = ROOT / "implementation" / "stage-1-foundation"
        hashes.extend(f"-- ../stage-1-foundation/{name}: SHA256 {hashlib.sha256((foundation / name).read_bytes()).hexdigest()}"
                      for name in ("01-companies.yaml", "02-utility-providers.yaml"))
    # One expected record per line keeps the SQL snapshot reviewable.
    payload = "[\n" + ",\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n]"
    result = BEGIN + "\n".join(hashes) + "\nDECLARE @ExpectedJson nvarchar(max) = N'" + payload.replace("'", "''") + "';\n"
    if number == 1:
        groups = files["04-groups.yaml"]
        deferred = {"groups": [item(company(r["Company"]), r["Group ID"]) for r in groups["laterLocalGroups"]],
                    "permissions": [{"GroupID": r["Group ID"], "Type": p["Type"]}
                                    for r in groups["laterPermissions"] for p in r["Deferred Permissions"]]}
        result += "DECLARE @DeferredJson nvarchar(max) = N'" + json.dumps(deferred, separators=(",", ":")).replace("'", "''") + "';\n"
    return result + END


def handheld_gateway_keys(gateways):
    """The gateway records on the parameterless handheld type (gatewayTypes key type_handheld). They have no nodes
    or points: Neptune and MVRS read their meters from HMR configuration, listed in 05-handheld-routes.yaml."""
    name = next(entry["Name"] for entry in gateways["gatewayTypes"] if entry["key"] == "type_handheld")
    keys = {record["key"] for record in gateways["records"] if record["Gateway"]["Vendor"] == name}
    for record in gateways["records"]:
        if record["key"] in keys and (record.get("Nodes") or record.get("Points")):
            raise ValueError(f"A handheld gateway has no nodes or points: {record['key']}")
    return keys


def render_gateway_types():
    """Stage 3's gateway-type expectations: every parameter of every type in 02-gateways.yaml gatewayTypes, and the
    names of the types otherGatewayTypes keeps or retires."""
    folder = ROOT / "implementation" / "stage-3-gateways-and-data"
    gateways = yaml.load((folder / "02-gateways.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
    handheld = handheld_gateway_keys(gateways)
    types = []
    for gateway_type in gateways["gatewayTypes"]:
        params = []
        for level, key in (("node", "Node Parameters"), ("point", "Point Parameters")):
            for parameter in gateway_type.get(key) or []:
                values = sorted((str(value), str(description)) for value, description in (parameter.get("Values") or {}).items())
                params.append({"Level": level, "Column": parameter["Column"], "Label": parameter["Label"], "Type": parameter["Type"],
                               "ValuesText": "; ".join(f"{v}={d}" for v, d in values) or None})
        types.append({"Name": gateway_type["Name"], "Params": params})
    others = gateways["otherGatewayTypes"]
    # Handheld gateways have no nodes, but they still need their own (parameterless) type.
    profiles = [{"Name": record["Gateway"]["Description"], "Vendor": record["Gateway"]["Vendor"], "Required": True}
                for record in gateways["records"]
                if record.get("Nodes") or record["key"] in handheld]
    profiles.extend({"Name": record["Description"], "Vendor": record["Vendor"], "Required": False}
                    for record in gateways.get("transitionGateways", []))
    definitions = {entry["Name"]: entry for entry in gateways["gatewayTypes"]}
    nodes = []
    for record in gateways["records"]:
        definition = definitions.get(record["Gateway"]["Vendor"])
        if definition is None:
            continue
        columns = {parameter["Label"]: parameter["Column"] for parameter in definition.get("Node Parameters", [])
                   if not str(parameter.get("Reads", "")).lower().startswith("not read")}
        for node in record.get("Nodes", []):
            values = {name: value for name, value in node.get("Node Parameters", {}).items() if name in columns}
            if "IsEnabled" in columns:
                values.setdefault("IsEnabled", 1)
            nodes.append({"Gateway": record["Gateway"]["Description"], "Name": node["Description"],
                          "Params": [{"Column": columns[name], "Label": name, "Value": str(value) if value is not None else ""}
                                     for name, value in values.items()]})
    data = {"types": types, "profiles": profiles, "nodes": nodes,
            "retired": [{"Name": o["Name"]} for o in others if o["Outcome"] in ("Deleted", "Renamed")],
            "listed": [{"Name": t["Name"]} for t in types] + [{"Name": o["Name"]} for o in others]}
    digest = hashlib.sha256((folder / "02-gateways.yaml").read_bytes()).hexdigest()
    return (BEGIN + f"-- 02-gateways.yaml: SHA256 {digest}\nDECLARE @GatewayTypesJson nvarchar(max) = N'"
            + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("'", "''") + "';\n" + END)


def workflow_expectations(gateways, recipe):
    """Keep reusable task defaults separate from each schedule's effective parameters."""
    profiles = {record["key"]: record for record in gateways["records"]}
    workflows = []
    for definition in recipe["builtInWorkflows"] + recipe["customWorkflows"]:
        components = definition["Components"]
        if "IntervalDataPublish" not in components:
            raise ValueError(f"Workflow has no interval publisher: {definition['Name']}")
        collector = components[0]
        links = [{"FromComponent": collector, "FromField": "Out", "ToComponent": "IntervalDataPublish", "ToField": "In"}]
        for output, parameter in (("IntervalDataFilePath", "InputFilePath"), ("ResolvedGatewayId", "GatewayId"),
                                  ("ResolvedGatewayName", "GatewayName"), ("ResolvedGatewayGuid", "GatewayGuid"),
                                  ("GatewayType", "GatewayType")):
            links.append({"FromComponent": collector, "FromField": output,
                          "ToComponent": "IntervalDataPublish", "ToField": parameter})
        if "HmrEventsPublish" in components:
            links.append({"FromComponent": "IntervalDataPublish", "FromField": "Out", "ToComponent": "HmrEventsPublish", "ToField": "In"})
            for output, parameter in (("EventsFilePath", "InputFilePath"), ("ResolvedGatewayId", "GatewayId"),
                                      ("ResolvedGatewayName", "GatewayName"), ("ResolvedGatewayGuid", "GatewayGuid"),
                                      ("GatewayType", "GatewayType")):
                links.append({"FromComponent": collector, "FromField": output,
                              "ToComponent": "HmrEventsPublish", "ToField": parameter})
        if "Nodes" in definition:
            nodes = {node["Id"]: node["Component"] for node in definition["Nodes"]}
            configured_links = []
            for link in definition["Links"]:
                source, output = link["From"].split(".", 1)
                target, parameter = link["To"].split(".", 1)
                configured_links.append({"FromComponent": nodes[source], "FromField": output,
                                         "ToComponent": nodes[target], "ToField": parameter})
            if any(link not in configured_links for link in links):
                raise ValueError(f"Custom workflow is missing publication links: {definition['Name']}")
            links = configured_links
        bindings = [{"Component": node["Component"], "Field": name, "Value": value}
                    for node in definition.get("Nodes", []) for name, value in node["Values"].items()]
        workflows.append({"Name": definition["Name"], "DocumentId": definition.get("Document ID"),
                          "ProfileName": definition.get("Execution profile", "Gateway"), "Components": components,
                          "Links": links, "Bindings": bindings,
                          "Parameters": [{"Name": name, "Kind": value["Type"], "Required": value.get("Required", False)}
                                         for name, value in definition.get("Parameters", {}).items()]})
    by_name = {workflow["Name"]: workflow for workflow in workflows}
    if len(by_name) != len(workflows):
        raise ValueError("Duplicate workflow definition")
    def parameters(values, definitions, overrides=()):
        values = dict(values)
        for name in ("InputDirectory", "WorkingDirectory", "ArchiveDirectory", "ErrorDirectory", "OutputDirectory"):
            if name in definitions and not definitions[name]["Required"]:
                values.setdefault(name, "")
        if unknown := set(values) - definitions.keys():
            raise ValueError(f"Unknown workflow parameters: {sorted(unknown)}")
        result = []
        for name, value in values.items():
            kind = definitions[name]["Kind"]
            if kind not in ("Integer", "Boolean", "DateTime"):
                kind = "String"
            text = str(value).lower() if isinstance(value, bool) else str(value) if value is not None else ""
            result.append({"Name": name, "Value": text, "Kind": kind, "Required": definitions[name]["Required"],
                           "Override": name in overrides})
        return result

    tasks = []
    tasks_by_key = {}
    used_workflows = set()
    for record in recipe["tasks"]:
        if record["Workflow"] not in by_name:
            raise ValueError(f"Unknown task workflow: {record['Workflow']}")
        if record["key"] in tasks_by_key or record["Workflow"] in used_workflows:
            raise ValueError("Each workflow must have one reusable task")
        workflow = by_name[record["Workflow"]]
        definitions = {parameter["Name"]: parameter for parameter in workflow["Parameters"]}
        defaults = record["Default parameters"]
        if defaults.get("GatewayId") not in (None, ""):
            raise ValueError("Reusable task GatewayId default must be blank")
        target = record["Execution target"]
        tasks.append({"Key": record["key"], "Name": record["Task name"], "Workflow": record["Workflow"],
                      "Parameters": parameters(defaults, definitions), "Machine": target["Machine"],
                      "TaskGroup": recipe["taskDefinitionDefaults"]["Task group"],
                      "MinIntervalSeconds": recipe["taskDefinitionDefaults"]["Minimum interval seconds"]})
        tasks_by_key[record["key"]] = record
        used_workflows.add(record["Workflow"])
    if len({task["Name"] for task in tasks}) != len(tasks):
        raise ValueError("Duplicate task name")

    schedules = []
    for record in recipe["schedules"]:
        if record["Task"] not in tasks_by_key:
            raise ValueError(f"Unknown schedule task: {record['Task']}")
        if record["Gateway"] not in profiles:
            raise ValueError(f"Unknown schedule gateway: {record['Gateway']}")
        task = tasks_by_key[record["Task"]]
        profile = profiles[record["Gateway"]]
        definitions = {parameter["Name"]: parameter for parameter in by_name[task["Workflow"]]["Parameters"]}
        overrides = record.get("Parameters", {})
        if "GatewayId" not in overrides:
            raise ValueError("Each schedule must select its GatewayId")
        values = task["Default parameters"] | overrides
        missing = {name for name, parameter in definitions.items() if parameter["Required"]
                   and name != "GatewayId" and values.get(name) in (None, "")}
        if missing:
            raise ValueError(f"Missing required schedule parameters: {sorted(missing)}")
        expected_parameters = parameters(values, definitions, overrides)
        for parameter in expected_parameters:
            if parameter["Name"] == "GatewayId":
                parameter["Value"] = None  # Resolve the named gateway in the target database.
        kind = {"Runs once": 0, "Interval": 1, "Cron": 2}[record["Schedule kind"]]
        if kind == 1 and record["Interval seconds"] < 300:
            raise ValueError(f"Interval below 300 seconds: {record['key']}")
        if kind == 2 and len(record["Cron expression"].split()) != 6:
            raise ValueError(f"Cron requires six fields: {record['key']}")
        schedules.append({"Key": record["key"], "Name": record["Schedule name"], "Task": task["Task name"],
                      "Workflow": task["Workflow"],
                      "Gateway": profile["Gateway"]["Description"], "ScheduleKind": kind,
                      "IntervalSeconds": record.get("Interval seconds"), "CronExpression": record.get("Cron expression"),
                      "TimeZoneId": record["Time zone ID"], "Active": record["Enabled"],
                      "Parameters": expected_parameters, "RootDirectory": values.get("RootDirectory")})
    if len({schedule["Name"] for schedule in schedules}) != len(schedules):
        raise ValueError("Duplicate schedule name")
    if len({schedule["Key"] for schedule in schedules}) != len(schedules):
        raise ValueError("Duplicate schedule key")
    return {"workflows": workflows, "tasks": tasks, "schedules": schedules,
            "retiredTasks": recipe["retiredTaskNames"]}


def render_workflows():
    folder = ROOT / "implementation" / "stage-3-gateways-and-data"
    paths = [folder / name for name in ("02-gateways.yaml", "03-workflows-and-tasks.yaml")]
    data = workflow_expectations(*(yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader) for path in paths))
    hashes = "\n".join(f"-- {path.name}: SHA256 {hashlib.sha256(path.read_bytes()).hexdigest()}" for path in paths)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("'", "''")
    return WORKFLOW_BEGIN + hashes + "\nDECLARE @WorkflowJson nvarchar(max) = N'" + payload + "';\n" + WORKFLOW_END


HANDHELD_METER_FIELDS = ("Cycle", "Route Number", "Enabled", "Bill Code", "Meter Text")
# Handheld Meter Setup saves these meter-text characters as "_" (handheldSetupRows.ts sanitizeMeterText, as the
# old report did), so a recipe text holding one would never match what is stored.
HANDHELD_METER_TEXT_REPLACED = re.compile(r"[|&;$%@'\"<>()+,\\/]")
HANDHELD_READING_FIELDS = ("Read Type", "Meter Constant", "Text Prompt", "Channel", "ERT Id", "Tamper Code",
                           "High Warning", "Low Warning")


def _whole_number(value):
    return isinstance(value, int) and not isinstance(value, bool)


def handheld_expectations(gateways, recipe, points):
    """Resolve HMR routes to existing physical meters, their registers and their demand points.

    A route meter has one register (the record's HMR_Reading, with the meter's Reading Point and Consumption Point) or
    a Registers list of its own. A register is an accumulator read through its Stage 2 register and that register's
    generated Delta, or a demand read (DemandRead Y) straight into an Analog point with no Reading Point. A meter may
    override the record's route fields (HMR_Meter) and register fields; its sequence follows its place in the record.
    """
    from generators.gateway_assignments import expand_points

    types = {row["key"]: row for row in recipe["readTypes"]}
    if len(types) != len(recipe["readTypes"]) or len({t["Description"] for t in types.values()}) != len(types):
        raise ValueError("Duplicate handheld read type")
    for read_type in types.values():
        if (not 1 <= read_type["NumDials"] <= 10 or not 0 <= read_type["NumDecimals"] <= read_type["NumDials"]
                or len(read_type["ReadTypeCode"]) != 2 or read_type["ReadDirection"] not in ("L", "R")
                or read_type["DemandRead"] not in ("N", "Y") or len(read_type["Description"]) > 50):
            raise ValueError(f"Invalid handheld read type: {read_type['key']}")
    source_points = {row["key"]: row for row in points["records"]}
    handheld_gateways = handheld_gateway_keys(gateways)
    default_date = date.fromisoformat(str(recipe["startingReadings"]["Read date"])).isoformat()
    covered, meter_keys, positions, rows = set(), set(), set(), []
    for record in recipe["records"]:
        if record["Gateway"] not in handheld_gateways:
            raise ValueError(f"A handheld route must name a gateway on the handheld type: {record['key']}")
        covered.add(record["Gateway"])
        bindings = list(expand_points(record["Meters"]))
        if len(bindings) != record["count"]:
            raise ValueError(f"Handheld count does not match its meters: {record['key']}")
        starting_date = date.fromisoformat(str(record.get("Starting date", default_date))).isoformat()
        # One number for a single meter, or First and Step along the route in sequence order. A meter with its own
        # Registers gives each accumulator register its own number instead.
        start = record.get("Starting reading")
        if start is not None and (isinstance(start, bool) or not isinstance(start, (int, dict)) or (isinstance(start, dict) and (
                set(start) != {"First", "Step"} or not all(_whole_number(value) for value in start.values())))):
            raise ValueError(f"Starting reading must be a whole number or First and Step: {record['key']}")
        for index, binding in enumerate(bindings):
            overrides = binding.get("HMR_Meter", {})
            if set(overrides) - set(HANDHELD_METER_FIELDS):
                raise ValueError(f"A meter may override only its route fields: {binding.get('channel', record['key'])}")
            meter = {**record["HMR_Meter"], **overrides}
            if (not isinstance(meter["Cycle"], str) or not 1 <= len(meter["Cycle"]) <= 2
                    or meter["Cycle"] == "99" or not 1 <= len(meter["Route Number"]) <= 6
                    or len(meter["Bill Code"]) != 1 or len(meter["Meter Text"]) > 100
                    or meter["First Read Sequence"] <= 0 or meter["Read Sequence Increment"] <= 0
                    or not isinstance(meter["Enabled"], bool)):
                raise ValueError(f"Invalid handheld cycle, route or sequence: {record['key']}")
            if HANDHELD_METER_TEXT_REPLACED.search(meter["Meter Text"]):
                raise ValueError(f"Meter text holds a character Handheld Meter Setup saves as _: {record['key']}")
            meter_key = binding["Company"], binding["Meter"]["Meter Number"]
            sequence = meter["First Read Sequence"] + index * meter["Read Sequence Increment"]
            position = meter["Cycle"], meter["Route Number"], sequence
            if meter_key in meter_keys or position in positions:
                raise ValueError(f"Duplicate handheld meter or route position: {binding['Meter']['Meter Number']}")
            meter_keys.add(meter_key)
            positions.add(position)
            if "Registers" in binding:
                registers = binding["Registers"]
                if not registers or any(field in binding for field in ("Reading Point", "Consumption Point")):
                    raise ValueError(f"A meter lists its points once, on the meter or on each register: {binding['Meter']['Meter Number']}")
            else:
                if start is None:
                    raise ValueError(f"Starting reading must be a whole number or First and Step: {record['key']}")
                registers = [{**{field: binding[field] for field in ("channel", "relatedReadingChannel", "Reading Point",
                                                                     "Consumption Point") if field in binding},
                              **{field: binding[field] for field in HANDHELD_READING_FIELDS if field in binding},
                              "Starting reading": start if isinstance(start, int) else start["First"] + index * start["Step"]}]
            prompts, used = set(), set()
            for register in registers:
                reading = {**record["HMR_Reading"], **{field: register[field] for field in HANDHELD_READING_FIELDS if field in register}}
                if (reading["Channel"] not in range(1, 100) or not str(reading["Text Prompt"]).isalnum()
                        or len(reading["Text Prompt"]) > 4 or reading["Meter Constant"] <= 0
                        or len(reading["Tamper Code"]) != 2):
                    raise ValueError(f"Invalid handheld channel: {register['channel']}")
                if reading["Text Prompt"].upper() in prompts:
                    raise ValueError(f"A prompt is used once per meter: {register['channel']}")
                prompts.add(reading["Text Prompt"].upper())
                read_type = types[reading["Read Type"]]
                if register.get("Reading Point") is not None:
                    if read_type["DemandRead"] != "N":
                        raise ValueError(f"A register with a Reading Point needs a non-demand read type: {register['channel']}")
                    register_point = source_points[register["relatedReadingChannel"]]
                    description = register_point["Point Definition"]["Description"]
                    if "usageChannel" in register:
                        # An Analog register: the read goes to it and the difference to its own Analog usage point
                        # (for a unit Point_Save will not take for an Accumulator, such as run hours in Hour).
                        source = source_points[register["usageChannel"]]
                        if (register_point["Point Definition"]["Reading Type"] != "Analog"
                                or source["Point Definition"]["Reading Type"] != "Analog"
                                or register_point["Meter"] != binding["Meter"] or source["Meter"] != binding["Meter"]
                                or source["key"] == register_point["key"]):
                            raise ValueError(f"An Analog register needs its own Analog usage point on the meter: {register['channel']}")
                        if (register["Reading Point"] != description
                                or register["Consumption Point"] != source["Point Definition"]["Description"]):
                            raise ValueError(f"Handheld points must be the Stage 2 register and its usage point: {register['channel']}")
                        kind, usage_description, points_used = "Analog", source["Point Definition"]["Description"], (register_point["key"], source["key"])
                    else:
                        if register_point["Point Definition"]["Reading Type"] != "Accumulator" or register_point["Meter"] != binding["Meter"]:
                            raise ValueError(f"Handheld mapping must resolve an existing accumulator: {register['channel']}")
                        # Point_Save names the usage point it generates behind a register "<register> Delta".
                        if register["Reading Point"] != description or register["Consumption Point"] != description + " Delta":
                            raise ValueError(f"Handheld points must be the Stage 2 register and its delta: {register['channel']}")
                        # The Delta carries the register's usage unit.
                        source, kind, usage_description, points_used = register_point, "Accumulator", description + " Delta", (register_point["key"],)
                    starting = register.get("Starting reading")
                    if not _whole_number(starting) or not 0 <= starting < 10 ** read_type["NumDials"]:
                        raise ValueError(f"Starting reading does not fit the read type's dials: {register['channel']}")
                    reading_description = description
                else:
                    # A demand read is stored as read on its own Analog point: no register, no Delta, no starting value.
                    if read_type["DemandRead"] != "Y" or "Starting reading" in register:
                        raise ValueError(f"A register with no Reading Point is a demand read with no starting value: {register['channel']}")
                    source = source_points[register["usageChannel"]]
                    if source["Point Definition"]["Reading Type"] != "Analog" or source["Meter"] != binding["Meter"]:
                        raise ValueError(f"A demand read must resolve an existing Analog point: {register['channel']}")
                    description = source["Point Definition"]["Description"]
                    if register["Consumption Point"] != description:
                        raise ValueError(f"A demand read's Consumption Point is its Analog point: {register['channel']}")
                    starting, reading_description, usage_description = None, None, description
                    kind, points_used = "Demand", (source["key"],)
                for point_key in points_used:
                    if point_key in used:
                        raise ValueError(f"A point serves one register: {register['channel']}")
                    used.add(point_key)
                rows.append({"Key": register["channel"], "RegisterKind": kind,
                             "ReadingChannel": register.get("relatedReadingChannel"),
                             "UsageChannel": register.get("usageChannel"),
                             "Gateway": record["Gateway"], "Company": binding["Company"],
                             "MeterNumber": binding["Meter"]["Meter Number"], "MeterDescription": binding["Meter"]["Description"],
                             "ReadingDescription": reading_description, "UsageDescription": usage_description,
                             "UsageUnit": source["Point Definition"]["Unit"], "Cycle": meter["Cycle"],
                             "Route": meter["Route Number"], "Sequence": sequence, "Active": meter["Enabled"],
                             "BillCode": meter["Bill Code"], "MeterText": meter["Meter Text"],
                             "ReadType": read_type["Description"], "Constant": reading["Meter Constant"],
                             "Prompt": reading["Text Prompt"], "Channel": reading["Channel"],
                             "ERTID": reading["ERT Id"], "TamperCode": reading["Tamper Code"],
                             "HighWarning": reading["High Warning"], "LowWarning": reading["Low Warning"],
                             "StartingReading": starting, "StartingDate": starting_date if starting is not None else None})
    if covered != handheld_gateways:
        raise ValueError("Every handheld gateway needs its meters in 05-handheld-routes.yaml")
    if len({row["Key"] for row in rows}) != len(rows):
        raise ValueError("Duplicate handheld register key")
    if (len(meter_keys) != recipe["export"]["Expected permanent meters"]
            or len(rows) != recipe["export"]["Expected permanent reading channels"]):
        raise ValueError("Handheld export totals do not match the resolved routes")
    temporary = recipe["acceptanceOnly"]["directDemand"]
    direct = source_points[temporary["Point"]["Channel"]]
    if (direct["Meter"] != temporary["Meter"] or direct["Point Definition"]["Description"] != temporary["Point"]["Description"]
            or direct["Point Definition"]["Reading Type"] != "Analog" or temporary["Reading Point"] is not None
            or types[temporary["Read Type"]]["DemandRead"] != "Y"):
        raise ValueError("Temporary demand exercise must use the declared analog point without a register")
    return {"readTypes": [{k: v for k, v in row.items() if k != "key"} for row in types.values()], "meters": rows}


def load_handheld_expectations():
    folder = ROOT / "implementation" / "stage-3-gateways-and-data"
    paths = [folder / name for name in ("02-gateways.yaml", "05-handheld-routes.yaml")]
    paths.append(ROOT / "implementation/stage-2-hierarchy/04-points.yaml")
    data = handheld_expectations(*(yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader) for path in paths))
    return paths, data


def render_handheld():
    paths, data = load_handheld_expectations()
    hashes = "\n".join(f"-- {path.relative_to(ROOT).as_posix()}: SHA256 {hashlib.sha256(path.read_bytes()).hexdigest()}" for path in paths)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("'", "''")
    return HANDHELD_BEGIN + hashes + "\nDECLARE @HandheldJson nvarchar(max) = N'" + payload + "';\n" + HANDHELD_END


def render_handheld_paste():
    """The rows to paste into Handheld Meter Setup, one per register, in the page's own order (cycle, route, sequence,
    prompt), so the Starting Reading column also pastes straight into its Starting readings view."""
    _, data = load_handheld_expectations()
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HANDHELD_PASTE_COLUMNS)
    for row in sorted(data["meters"], key=lambda row: (row["Cycle"], row["Route"], row["Sequence"], row["Prompt"])):
        # A demand read has no Reading Point and no starting value, and a register may have no warnings: those cells
        # stay empty.
        writer.writerow([row["MeterNumber"], row["MeterDescription"], row["Cycle"], row["Route"], row["Sequence"],
                         "Yes" if row["Active"] else "No", row["BillCode"], row["MeterText"], row["Prompt"], row["ReadType"],
                         row["Constant"], row["Channel"], row["TamperCode"],
                         "" if row["HighWarning"] is None else row["HighWarning"],
                         "" if row["LowWarning"] is None else row["LowWarning"], row["ReadingDescription"] or "",
                         row["UsageDescription"], "" if row["StartingReading"] is None else row["StartingReading"],
                         row["StartingDate"] or ""])
    return buffer.getvalue()


def render_handheld_starting_readings():
    """One file per starting-reading date: the values to paste into the Starting readings view, one per line, in the
    order that view lists the registers still waiting for one (cycle, route, sequence, prompt). Demand reads have none."""
    _, data = load_handheld_expectations()
    files = {}
    for row in sorted(data["meters"], key=lambda row: (row["Cycle"], row["Route"], row["Sequence"], row["Prompt"])):
        if row["StartingReading"] is not None:
            files.setdefault(row["StartingDate"], []).append(str(row["StartingReading"]))
    return {HANDHELD_STARTING.format(day): "\n".join(values) + "\n" for day, values in sorted(files.items())}


def render_handheld_operations():
    """One entry per route meter (its registers counted) and one per route, for the Stage 9 round checks."""
    paths, data = load_handheld_expectations()
    meters, routes = {}, {}
    for row in data["meters"]:
        meter = meters.setdefault((row["Company"], row["MeterNumber"]), {
            **{key: row[key] for key in ("Key", "Company", "MeterNumber", "MeterDescription", "Gateway", "Cycle", "Route", "Active")},
            "ExpectedChannels": 0})
        meter["ExpectedChannels"] += 1
    for meter in meters.values():
        route = routes.setdefault((meter["Cycle"], meter["Route"]), {"Cycle": meter["Cycle"], "Route": meter["Route"],
                                                                      "ExpectedMeters": 0, "ExpectedChannels": 0})
        route["ExpectedMeters"] += 1
        route["ExpectedChannels"] += meter["ExpectedChannels"]
    payload = {"routes": [routes[key] for key in sorted(routes)], "meters": list(meters.values())}
    hashes = "\n".join(f"-- {path.relative_to(ROOT).as_posix()}: SHA256 {hashlib.sha256(path.read_bytes()).hexdigest()}" for path in paths)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("'", "''")
    return HANDHELD_OPERATIONS_BEGIN + hashes + "\nDECLARE @HmrOperationsJson nvarchar(max) = N'" + text + "';\n" + HANDHELD_OPERATIONS_END


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    targets = [(load_stage(number)[0] / "checks.sql", lambda number=number: render_data(number), BEGIN, END) for number in (1, 2)]
    stage3 = ROOT / "implementation" / "stage-3-gateways-and-data" / "checks.sql"
    targets.extend(((stage3, render_gateway_types, BEGIN, END), (stage3, render_workflows, WORKFLOW_BEGIN, WORKFLOW_END)))
    targets.append((stage3, render_handheld, HANDHELD_BEGIN, HANDHELD_END))
    stage9 = ROOT / "implementation/stage-9-operations/checks.sql"
    targets.append((stage9, render_handheld_operations, HANDHELD_OPERATIONS_BEGIN, HANDHELD_OPERATIONS_END))
    for path, render, begin, end_marker in targets:
        original = path.read_text(encoding="utf-8")
        start, end = original.index(begin), original.index(end_marker) + len(end_marker)
        current = original[:start] + render() + original[end:]
        if current != original:
            relative = str(path.relative_to(ROOT))
            if relative not in stale:
                stale.append(relative)
            if not args.check:
                path.write_text(current, encoding="utf-8", newline="\n")
    generated = {HANDHELD_PASTE: render_handheld_paste(), **render_handheld_starting_readings()}
    for name, text in generated.items():
        target = stage3.parent / name
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            stale.append(str(target.relative_to(ROOT)))
            if not args.check:
                target.write_text(text, encoding="utf-8", newline="\n")
    for leftover in sorted(stage3.parent.glob(HANDHELD_STARTING.format("*"))):
        if leftover.name not in generated:
            stale.append(str(leftover.relative_to(ROOT)))
            if not args.check:
                leftover.unlink()
    if args.check and stale:
        parser.exit(1, "Stale checker data; run python -m generators.stage_check_data:\n" + "\n".join(stale) + "\n")
    print("Checker snapshots match the YAML." if args.check else "Refreshed checker expectations: " + (", ".join(stale) or "already current"))


if __name__ == "__main__":
    main()
