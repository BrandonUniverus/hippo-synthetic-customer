"""Build Northlake intake data and AcquiSuite files. Never connects to EEMSuite."""

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CUSTOMER = Path("customer-provided/northlake-university")


def read_yaml(root, filename):
    return yaml.safe_load((root / filename).read_text(encoding="utf-8"))


def table(headers, rows, description):
    return {"headers": headers, "rows": rows, "description": description}


def label(value):
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", str(value)).replace("_", " ").replace(".", " / ")


def rate_components(value, prefix=""):
    if isinstance(value, dict):
        if "rate" in value:
            yield prefix, value
        else:
            for key, item in value.items():
                yield from rate_components(item, f"{prefix}.{key}".strip("."))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from rate_components(item, f"{prefix}.{index + 1}")


def markdown_table(data):
    def cell(value):
        return str(value if value is not None else "").replace("|", "\\|").replace("\n", "<br>")
    rows = [data["headers"], ["---"] * len(data["headers"]), *data["rows"]]
    return "\n".join("| " + " | ".join(map(cell, row)) + " |" for row in rows)


def build_packet(root=ROOT):
    scenario = read_yaml(root, "scenarios/demo-university-v1.yaml")
    model = read_yaml(root, "eem/northlake-eem-metaworld-stage1b-v1.yaml")
    onboarding = read_yaml(root, "scenarios/northlake-onboarding-v1.yaml")
    people = {p["id"]: p for p in read_yaml(root, "security/northlake-eem-security-v1.yaml")["users"]}
    providers = {p["id"]: p for p in (read_yaml(root, f.relative_to(root)) for f in sorted((root / "providers").glob("*.yaml")))}
    companies = onboarding["companies"]
    sites = {s["id"]: s for s in scenario["sites"]}
    names = {loc["sourceBuildingId"]: loc["eemName"] for locs in model["canonicalLocationNames"].values() for loc in locs if "sourceBuildingId" in loc}
    accounts = {a["id"]: a for a in scenario["accounts"]}
    source_meters = {m["id"]: m for a in accounts.values() for m in a["meters"]}
    channels = {p["id"]: p for m in source_meters.values() for p in m["channels"]}
    channels.update({p["id"]: p for p in scenario["referenceChannels"]})
    profiles = {p["id"]: p for p in scenario["gatewayBindings"]["profiles"]}
    assert set(profiles) == set(onboarding["sources"]), "Every source profile needs a customer description"
    account_targets = {}
    for company, kinds in model["billingAccountTargets"].items():
        for kind, items in kinds.items():
            for item in items:
                account_targets[item["sourceAccountId"]] = company, kind, item
    assert set(account_targets) == set(accounts), "Source and UI account inventories differ"

    meters = []
    for company, group in model["meterPointTargets"].items():
        for location in group["locations"]:
            for meter in location.get("meters", []):
                meters.append(dict(meter, company=company, location=location["name"], site="cedar_row_apartments" if company == "cedar_row_apartments" else "northlake_main_campus"))
    for meter in model["weatherIndexTargets"]["weatherMeters"]:
        meters.append(dict(meter, company=model["weatherIndexTargets"]["ownerCompanyId"], location="Sacramento Weather Reference", site="Reference stations", hasBills=False))

    points = {}
    for meter in meters:
        for point in meter["points"]:
            key = point.get("sourceChannelId", point.get("derivedPointId"))
            assert key and key not in points, f"Repeated or unnamed point: {key}"
            points[key] = dict(point, meter=meter)
    assert set(channels) <= set(points), f"Source channels without UI destinations: {set(channels) - set(points)}"
    bindings = []
    point_sources = {}
    for profile in profiles.values():
        for node in profile.get("runtime", {}).get("nodes", []):
            for point in node.get("points", []):
                key = point["channelId"]
                assert key in points, f"Gateway measurement has no point: {key}"
                if "relatedReadingPoint" in point:
                    reading = points.get(point["relatedReadingPoint"])
                    assert reading and reading["pointType"] == "Accumulator", f"Missing handheld register: {key}"
                bindings.append((profile, node, point, points[key]))
                point_sources.setdefault(key, []).append(profile["id"])

    packet = {"version": onboarding["packetVersion"], "issuedOn": onboarding["issuedOn"], "sheets": {}}
    sheets = packet["sheets"]
    sheets["Instructions"] = table(["Topic", "What Northlake Should Provide", "Owner", "Status"], [
        ["Release", f"Northlake onboarding packet {onboarding['packetVersion']} dated {onboarding['issuedOn']}", "Facilities Operations", "Documented"],
        ["Customer workbook", "Data Collection is the single workbook; source systems and tenant requirements are included here.", "All reviewers", "Documented"],
        ["Company contacts", "Use Contacts for people, email and phone; Organization Units identifies each department's company and primary contact.", "Campus Operations", "Documented"],
        ["First handover", "Student Center electric meter, kWh and kW measurements, AcquiSuite source and one day of sample data.", "Facilities Operations", "Sample supplied"],
        ["Relationships", "Review the Related Measurements, Rollup Members and Weather Assignments tabs with the inventory.", "Facilities Operations", "Documented"],
        ["Scope", "Documented inventory is not evidence of installed setup or successful ingestion.", "Implementation team", "UI acceptance pending"],
        ["Customer revisions", "Return corrections against meter and measurement names; update the versioned sources before issuing the next packet.", "All reviewers", "Ongoing"],
    ], "Facilities and utility onboarding. All organizations, accounts and readings are fictional.")
    contacts = {}
    for contact in onboarding["contacts"]:
        key = contact.get("personId", contact.get("id"))
        assert key and key not in contacts, f"Repeated or unnamed contact: {key}"
        if "personId" in contact:
            assert key in people, f"Contact missing from the fictional roster: {key}"
            person = people[key]
            organization, name, role = companies[person["primaryCompanyId"]], person["displayName"], person["title"]
            email = contact.get("email", person["email"])
        else:
            organization, name, role = providers[contact["providerId"]]["displayName"], contact["name"], contact["role"]
            email = contact["email"]
        contacts[key] = [organization, name, role, email, contact["phone"], contact["appliesTo"], "Documented", contact.get("notes", "")]
    sheets["Contacts"] = table(["Organization", "Contact Name", "Role", "Email", "Phone", "Applies To", "Review Status", "Notes"], list(contacts.values()), "Company contacts and utility representatives. All details are fictional; shared contact mailboxes can differ from user login email.")
    organization_rows = []
    for unit in onboarding["organizationUnits"]:
        assert unit["contactId"] in contacts, f"Department has no contact: {unit['name']}"
        contact = contacts[unit["contactId"]]
        organization_rows.append([unit["name"], unit["purpose"], contact[1], contact[3], contact[4], "Documented", contact[7], contact[0]])
    sheets["Organization Units"] = table(["Unit Name", "Purpose / Responsibility", "Primary Contact", "Email", "Phone", "Review Status", "Notes", "Organization"], organization_rows, "Company ownership and primary contact for each department; email and phone come from the Contacts register.")
    # Retain the existing later-phase worksheets.
    sheets["Known Events"] = table(["Event Date", "Site / Building", "Event Type", "Affected Service", "Description", "Expected Treatment", "Review Status", "Notes"], onboarding["knownEvents"], "Only the January 15 interval sample is supplied; later events retain explicit fixture and acceptance gaps.")
    sheets["Sites"] = table(["Site Name", "Site Type", "Street Address", "City", "State / Province", "Country", "Primary Owner", "Review Status", "Notes"], [
        [s["displayName"], label(s["type"]), s["address"]["line1"], s["address"]["city"], s["address"]["state"], "USA", "Housing Operations" if s["id"] == "cedar_row_apartments" else "Facilities Operations", "Documented", "See building and service ownership; weather stations are external references."] for s in sites.values()
    ], "Physical properties. Company ownership is listed separately on accounts and meters.")
    buildings = []
    es = {p["ref"].get("buildingId"): p for p in scenario["energyStarProperties"] if "buildingId" in p["ref"]}
    for site in sites.values():
        for b in site["buildings"]:
            area = b.get("grossFloorAreaSqft", es.get(b["id"], {}).get("grossFloorArea", {}).get("value"))
            buildings.append([names[b["id"]], site["displayName"], label(b["useType"]), "Housing Operations" if site["id"] == "cedar_row_apartments" else "Facilities Operations", b["address"]["line1"], area, "sq ft", f"{b['units']} apartments" if "units" in b else label(b["useType"]), "Documented", "Included in the existing benchmarking boundary."])
    for b in onboarding["supportLocations"]:
        buildings.append([b["name"], sites[b["siteId"]]["displayName"], "Supporting facility", b["owner"], b["address"], b["grossFloorAreaSqft"], "sq ft", b["note"], "Documented", "See scope note; no automatic change to ENERGY STAR properties."])
    sheets["Buildings"] = table(["Building Name", "Site Name", "Building Type", "Primary Owner", "Service Address", "Gross Area", "Area Unit", "Occupancy / Use Notes", "Review Status", "Notes"], buildings, "Six benchmarked buildings plus the central plant and Common House supporting locations.")

    service_rows, rate_rows, component_rows = [], [], []
    for target in model["utilityProviderTargets"]:
        provider = providers[target["id"]]
        schedules = provider["rateSchedules"]
        service_rows.append([provider["displayName"], ", ".join(map(label, target["commoditySetup"])), provider["displayName"], ", ".join(companies[c] for c in target["companiesUsingProvider"]), ", ".join(r["id"] for r in schedules), ", ".join(dict.fromkeys(p["usageUnit"] for p in provider["supplies"] if "usageUnit" in p)), "Monthly", "Documented", "Tariff sheets and Rate Components provide the numeric charges."])
        for rate in schedules:
            rate_rows.append([provider["displayName"], rate["id"], label(rate["type"]), rate["effective"], ", ".join(label(k) for k in rate["components"])])
            for name, component in rate_components(rate["components"]):
                basis = component.get("basis", "")
                if "upToKgal" in component:
                    basis = f"Tier upper limit: {component['upToKgal']} kgal" if component["upToKgal"] is not None else "Remaining usage above the previous tier"
                component_rows.append([provider["displayName"], rate["id"], label(name), component["rate"], component["unit"], basis, rate["effective"]])
    sheets["Utility Services"] = table(["Service Name", "Service Category", "Provider / Counterparty", "Applies To Site", "Rate / Tariff", "Commodity Units", "Billing Frequency", "Review Status", "Notes"], service_rows, "Five counterparties. Source systems and file formats are a separate inventory.")
    sheets["Rate Schedules"] = table(["Provider", "Schedule", "Type", "Effective", "Key charges"], rate_rows, "Base contractual tariffs. Analysis-only rate models remain a separate implementation phase.")
    sheets["Rate Components"] = table(["Provider", "Schedule", "Charge", "Rate", "Unit", "Basis", "Effective"], component_rows, "Numeric charges from the provider tariff sources. Full schedules and tariff terms are also required for rate-engine acceptance.")

    account_rows = []
    for key, a in accounts.items():
        company, kind, target = account_targets[key]
        provider = providers[a["providerId"]]
        number = target.get("accountNumber", target.get("agreementId", target.get("costCenterId")))
        assert number in a.values(), f"Account identifier drift: {key}"
        account_rows.append([f"{target['location']} / {provider['shortName']}", provider["displayName"], label(kind), number, f"{companies[company]} / {target['location']}", target.get("costCenterId", ""), a.get("effectiveStart", scenario["dateRange"]["start"]), a.get("effectiveEnd", "Active"), "Finance and Accounts Payable", "Documented", ", ".join(target.get("rateScheduleIds", [target.get("rateScheduleId", "")]))])
    sheets["Accounts And Agreements"] = table(["Account / Agreement Name", "Provider / Counterparty", "Service Category", "Account Number", "Site / Building Scope", "Cost Center", "Start Date", "End Date", "Billing Contact", "Review Status", "Notes"], account_rows, "One row per source account, PPA agreement or internal cost center; several services may share an account.")

    meter_rows, point_rows, related_rows, mapping_rows = [], [], [], []
    for meter in meters:
        original = source_meters.get(meter["id"], {})
        tag = original.get("syntheticMeterNumber", meter.get("stationId", meter["id"].upper().replace("_", "-")))
        source_ids = list(dict.fromkeys(s for p in meter["points"] for s in point_sources.get(p.get("sourceChannelId"), [])))
        read_method = "; ".join(onboarding["sources"][s][0] for s in source_ids) or ("Bill / allocation statement" if meter.get("hasBills") else "Calculated or awaiting source setup")
        account = account_targets.get(meter.get("sourceAccountId"))
        account_number = next((account[2][k] for k in ["accountNumber", "agreementId", "costCenterId"] if k in account[2]), "") if account else ""
        notes = f"Company: {companies[meter['company']]}. Account: {account_number or 'No billing account'}."
        if original.get("effectiveStart"):
            notes += f" Service dates: {original['effectiveStart']} through {original.get('effectiveEnd') or 'active'}."
        if meter.get("replacesMeterId"):
            notes += f" Replaces {meter['replacesMeterId']}; keep histories separate."
        meter_rows.append([meter["name"], tag, meter["measureType"], sites.get(meter["site"], {}).get("displayName", meter["site"]), meter["location"], providers.get(meter.get("providerId"), {}).get("displayName", "Northlake / reference source"), meter["location"], companies[meter["company"]], read_method, "Documented", notes])
        for point in meter["points"]:
            key = point.get("sourceChannelId", point.get("derivedPointId"))
            interval = point.get("intervalMinutes")
            frequency = "Monthly / actual bill period" if interval is None else "Monthly route / actual reading dates" if interval == 43200 else f"{interval} minutes"
            point_rows.append([point["name"], meter["name"], label(point.get("role", "weather")), point["pointType"], point["unit"], frequency, "Exclude test signal" if "fake" in key else "Yes", "Documented", "Source: " + "; ".join(onboarding["sources"][s][0] for s in point_sources.get(key, [])) if key in point_sources else "From bill, related-point calculation or a later input path."])
            mapping_rows.append(["Point", key, companies[meter["company"]], meter["location"], meter["name"], point["name"], point["unit"], interval, "", "", "", "", "Not entered", ""])
            for related in point.get("createsRelatedPoints", []):
                related_rows.append([meter["name"], point["name"], meter["name"], related, "Heating degree days" if related.startswith("HDD") else "Cooling degree days", "Daily", "Create through the temperature index setting; verify base and calculation method in the UI."])
                mapping_rows.append(["Weather related point", f"{meter['id']}.{related}", companies[meter["company"]], meter["location"], meter["name"], related, "Degree days (F)", 1440, "", "", "", "", "Not entered", ""])
        registers = [p for p in meter["points"] if p["pointType"] == "Accumulator"]
        deltas = [p for p in meter["points"] if p["pointType"] == "AccumulatorDelta"]
        for register in registers:
            for delta in deltas:
                related_rows.append([meter["name"], register["name"], meter["name"], delta["name"], "Usage from register difference", "Actual reading dates", "Multiplier 1 for the initial case; capture the automatically created usage-point ID. Do not create an unrelated second usage point."])
    for baseline in model["baselineTargets"]:
        point = points[baseline["measuredPoint"]]
        related_rows.append([point["meter"]["name"], point["name"], point["meter"]["name"], baseline["baselinePointName"], "Measured versus baseline", f"{baseline['intervalMinutes']} minutes", "Baseline definition only; calculation and expected values are a later acceptance step."])
        mapping_rows.append(["Baseline point", baseline["id"], companies[baseline["companyId"]], point["meter"]["location"], point["meter"]["name"], baseline["baselinePointName"], baseline["unit"], baseline["intervalMinutes"], "", "", "", "", "Not entered", ""])
    sheets["Meters"] = table(["Meter Name", "Meter Number / Tag", "Service Category", "Site Name", "Building Name", "Provider / Counterparty", "Installation Location", "Ownership", "Read Method", "Review Status", "Notes"], meter_rows, "Physical meters, logical measurement groups and weather references; every planned gateway measurement has a destination.")
    sheets["Measured Points"] = table(["Point Name", "Meter Name", "Measurement", "Direction / Role", "Units", "Interval / Frequency", "Use In Reporting", "Review Status", "Notes"], point_rows, "Measured and explicitly specified point definitions. Related outputs and rollup members are listed on their own tabs.")
    sheets["Related Measurements"] = table(["Source Meter", "Source Measurement", "Related Meter", "Related Measurement", "Relationship", "Frequency", "Requirement"], related_rows, "Business relationships to create through the product's supported point/index settings.")
    rollups = []
    for aggregate in model["aggregateTargets"]:
        mapping_rows.append(["Aggregate point", aggregate["id"], companies[aggregate["companyId"]], aggregate["parentPath"], "", aggregate["aggregatePointName"], aggregate["unit"], aggregate["intervalMinutes"], "", "", "", "", "Not entered", ""])
        for member in aggregate["members"]:
            point = points[member["sourceChannelId"]]
            assert point["unit"] == aggregate["unit"] and point["intervalMinutes"] == aggregate["intervalMinutes"], "Incompatible aggregate member"
            rollups.append([aggregate["aggregatePointName"], point["meter"]["name"], point["name"], member["multiplier"], "Required" if member["required"] else "Optional", aggregate["unit"], aggregate["intervalMinutes"], "Science + Student only" if "Campus" in aggregate["aggregatePointName"] else "Delivered minus generated; an analysis series, not a supplier bill total"])
    sheets["Rollup Members"] = table(["Requested Total", "Member Meter", "Member Measurement", "Multiplier", "Availability", "Unit", "Interval Minutes", "Boundary"], rollups, "One row per member. Never add monthly bills to their interval representation or include the commissioning test signal.")
    sheets["Weather Assignments"] = table(["Organization", "Location", "Reference Station"], [[companies[a["companyId"]], a["location"], a["stationId"]] for a in model["weatherIndexTargets"]["stationAssignments"]], "Shared station ownership avoids duplicating weather measurements under every building.")
    sheets["Open Items"] = table(["Open Item", "Requested From", "Needed By", "Priority", "Current Status", "Resolution Notes"], [[item, "Implementation team", "Before the relevant acceptance run", "Normal", "Pending", ""] for item in onboarding["deferredAcceptance"]], "Documented boundaries and remaining acceptance work. Sample availability does not close these items.")

    source_rows, source_mapping_rows, coverage_rows = [], [], []
    for key, profile in profiles.items():
        name, owner, method, format_name, cadence, timestamps = onboarding["sources"][key]
        bound = [b for b in bindings if b[0]["id"] == key]
        references = ", ".join(dict.fromkeys(b[3]["meter"]["location"] for b in bound)) or "Neptune and MVRS reading events"
        sample = "Supplied: AcquiSuite complete, gap and backfill" if key == onboarding["acquiSuiteSample"]["profileId"] else "Sample / service not yet supplied"
        source_rows.append([name, method, format_name, owner, method, cadence, references, owner, "Documented", f"{timestamps}. {sample}."])
        for variant in profile.get("formatVariants", [profile["gatewayType"]]):
            coverage_rows.append([key, variant, references, len(bound), "Generated" if key == onboarding["acquiSuiteSample"]["profileId"] else "Planned", "Not run", "Not run"])
        for _, node, point, target in bound:
            values = point.get("values", {})
            selectors = "; ".join(f"{k}={v}" for k, v in values.items() if k not in {"PtID_Usage", "PtID_Reading", "MetaWorldID"})
            device = node.get("values", {}).get("Serial Number", node["name"])
            source_mapping_rows.append([name, target["meter"]["name"], target["name"], device, selectors, target["unit"], timestamps])
    for provider in providers.values():
        source_rows.append([f"{provider['displayName']} billing", "Billing statement", "Monthly utility / allocation / PPA statement", "Finance", "Statement and supported bill-import file", "Monthly", provider["shortName"], "Finance", "Documented", "Existing illustrated bills are examples; reconcile their values before rate or bill acceptance."])
    sheets["Data Sources"] = table(["Source Name", "Source Type", "Service Category", "Owner / Vendor", "Delivery Method", "Expected Cadence", "File / System Reference", "Credential Owner", "Review Status", "Notes"], source_rows, "Source ownership and delivery information. Credentials are exchanged separately and are never stored in the workbook.")
    sheets["Source Measurements"] = table(["Source System", "Meter", "Measurement", "Device / Station", "Channel / Source Fields", "Unit", "Timestamp Convention"], source_mapping_rows, "Vendor-side identifiers matched to the customer's measurement inventory; installed database IDs belong in the implementation record.")
    packet["coverage"] = table(["Profile", "Format", "Destinations", "Measurements", "Artifact status", "UI setup", "Ingestion acceptance"], coverage_rows, "Independent format cases; planned coverage is not a claim of supported installed behavior.")
    packet["instanceMapping"] = table(["Object kind", "Source reference", "Company", "Location", "Meter", "Point", "Unit", "Interval minutes", "Installed point ID", "Installed meter ID", "Installed gateway ID", "Installed node ID", "Status", "Evidence"], mapping_rows, "Copy before use. Capture real IDs after UI creation; never insert the illustrative IDs from a scenario into EEMSuite.")
    packet["decisions"] = onboarding["decisions"]
    packet["counts"] = {"sites": len(sites), "buildings": len(buildings), "providers": len(providers), "accounts": len(accounts), "meters": len(meters), "points": len(points), "relatedMeasurements": len(related_rows), "aggregates": len(model["aggregateTargets"]), "gatewayProfiles": len(profiles) - 1, "gatewayFormats": len(coverage_rows) - 1, "eventPublishers": 1, "baseRates": len(rate_rows), "contacts": len(contacts), "organizationUnits": len(organization_rows)}
    return packet


def sample_files(root=ROOT):
    onboarding = read_yaml(root, "scenarios/northlake-onboarding-v1.yaml")
    spec = onboarding["acquiSuiteSample"]
    scenario = read_yaml(root, "scenarios/demo-university-v1.yaml")
    profile = next(p for p in scenario["gatewayBindings"]["profiles"] if p["id"] == spec["profileId"])
    node = profile["runtime"]["nodes"][0]
    filename = f"{node['values']['Serial Number']}_{node['points'][0]['values']['DeviceID']}.log"
    start = datetime.fromisoformat(spec["localDate"]).replace(tzinfo=timezone(timedelta(hours=spec["utcOffsetHours"])))
    values = {}
    for segment in spec["segments"]:
        for index in range(segment["startInterval"], segment["startInterval"] + segment["count"]):
            assert index not in values, "Overlapping sample segments"
            values[index] = segment["demandKW"]
    assert set(values) == set(range(96)), "First sample must contain one ordinary 24-hour day"
    missing = set(range(spec["missingIntervals"]["start"], spec["missingIntervals"]["start"] + spec["missingIntervals"]["count"]))
    result = {}
    for case, indices in [("complete", range(96)), ("gap", sorted(set(values) - missing)), ("backfill", sorted(missing))]:
        content = "".join(f"'{(start + timedelta(minutes=15*i)).astimezone(timezone.utc):%Y-%m-%d %H:%M:%S}',{values[i]/4:.2f},{values[i]:.2f}\n" for i in indices)
        expected = spec["expected"][case]
        assert len(indices) == expected["intervalsPerPoint"] and len(indices)*2 == expected["readings"]
        assert sum(values[i]/4 for i in indices) == expected["energyKWh"] and max(values[i] for i in indices) == expected["peakKW"]
        result[case] = {"filename": filename, "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest(), **expected}
    return result


def write_packet(root=ROOT):
    packet = build_packet(root)
    output = root / "out/northlake-onboarding"
    output.mkdir(parents=True, exist_ok=True)
    (output / "packet.json").write_text(json.dumps(packet, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    register_sheets = ["Organization Units", "Contacts", "Buildings", "Accounts And Agreements", "Meters", "Measured Points", "Related Measurements", "Rollup Members", "Weather Assignments"]
    register = ["# Northlake Facilities and Meter Register", "", f"Packet {packet['version']} | Issued {packet['issuedOn']} | Fictional customer", "", "This register replaces the smaller Draft 0.1 inventory. It describes the requested setup; installation and ingestion acceptance are pending.", "", "## Customer decisions", ""]
    register += [f"- **{name}:** {text}" for name, text in packet["decisions"]]
    for name in register_sheets:
        register += ["", f"## {name}", "", packet["sheets"][name]["description"], "", markdown_table(packet["sheets"][name])]
    (root / CUSTOMER / "facilities-and-meter-register.md").write_text("\n".join(register) + "\n", encoding="utf-8", newline="\n")
    sources = ["# Northlake Source System Inventory", "", f"Packet {packet['version']} | Issued {packet['issuedOn']} | Facilities, IT and Finance", "", "Match each delivered measurement to the register. Only the AcquiSuite sample is supplied in this release; the remaining feeds require files, fixtures or services.", "", markdown_table(packet["sheets"]["Data Sources"]), "", "## Measurement mapping", "", markdown_table(packet["sheets"]["Source Measurements"])]
    (root / CUSTOMER / "source-system-inventory.md").write_text("\n".join(sources) + "\n", encoding="utf-8", newline="\n")
    coverage = ["# Northlake Gateway Setup Coverage", "", "Generated from the scenario profiles. Each format is a separate acceptance case. No installed setup or ingestion result has been recorded.", "", markdown_table(packet["coverage"]), "", "FIG variants reuse one point in separate restored runs. HMR publishes reading events rather than interval measurements. Catalog entries without a represented runnable component remain outside this list and must be reconciled against the installed product before claiming complete gateway coverage."]
    (root / "eem/northlake-gateway-coverage.md").write_text("\n".join(coverage) + "\n", encoding="utf-8", newline="\n")
    with (root / "eem/northlake-instance-mapping.template.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(packet["instanceMapping"]["headers"])
        writer.writerows(packet["instanceMapping"]["rows"])
    samples = sample_files(root)
    for case, sample in samples.items():
        directory = root / CUSTOMER / "sample-data/acquisuite" / case
        directory.mkdir(parents=True, exist_ok=True)
        (directory / sample["filename"]).write_bytes(sample["content"].encode())
    spec = read_yaml(root, "scenarios/northlake-onboarding-v1.yaml")["acquiSuiteSample"]
    expected = {"profile": spec["profileId"], "timestampConvention": spec["timestampConvention"], "localDate": spec["localDate"], "localTimeZone": "America/Los_Angeles", "installedAcceptance": "Not run", "cases": {case: {k: v for k, v in data.items() if k != "content"} for case, data in samples.items()}}
    (root / CUSTOMER / "sample-data/acquisuite/expected-results.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(packet["counts"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate sources and sample expectations without writing files")
    args = parser.parse_args()
    if args.check:
        packet = build_packet()
        sample_files()
        print(json.dumps(packet["counts"], indent=2))
    else:
        write_packet()
