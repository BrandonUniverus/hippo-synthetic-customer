"""Build Northlake intake data and AcquiSuite files. Never connects to EEMSuite.

The scenario manifest owns the physical inventory (companies, sites, buildings,
accounts, meters, channels); the Stage 1 and Stage 1B manifests own the EEM
level names and mapping rules; the onboarding manifest owns decisions, contacts
and source descriptions. This module joins them into the register and
source-system inventory PDFs, the workbook tables, the gateway coverage PDF and
the instance-mapping template.
"""

import argparse
import copy
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generators.documents.build_documents import defaults_for  # noqa: E402
from generators.documents.render_northlake_pdf import render_markdown  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
INTAKE = Path("documents/intake-package")
SAMPLES = INTAKE / "sample-data/acquisuite"
KIND_LABELS = {
    "utility": "Utility meter",
    "unit_submeter": "Apartment submeter",
    "house_submeter": "House submeter",
    "deduct_submeter": "Sewer-deduct submeter",
    "production_meter": "Production meter",
    "sensor_group": "Sensor group",
    "plant_controller": "Plant controller",
    "logical_source": "Logical source",
    "weather_station": "Weather station",
}
ACCOUNT_KIND_LABELS = {"externalUtilityAccounts": "External utility account", "internalCostCenters": "Internal cost center", "ppaAgreements": "PPA agreement"}
ACRONYMS = {"btu": "BTU", "chw": "CHW", "dc": "DC", "dx": "DX", "eru": "ERU", "ev": "EV", "hvac": "HVAC", "kw": "kW", "modbus": "Modbus", "ppa": "PPA", "pv": "PV", "sql": "SQL", "tou": "TOU"}
MANUAL_ROLES = {"manual_register_reading", "manual_usage_delta"}


def read_yaml(root, filename):
    return yaml.safe_load((root / filename).read_text(encoding="utf-8"))


def identifier_pattern(number_format):
    """SYN-VED-A-####### becomes a regular expression with one digit per #."""
    return re.compile("".join(r"\d" if ch == "#" else re.escape(ch) for ch in number_format))


def table(headers, rows, description):
    return {"headers": headers, "rows": rows, "description": description}


def label(value):
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", str(value)).replace("_", " ").replace(".", " / ")


def sentence(*values):
    """Readable text from identifier values: acronyms restored, first letter capitalised, lists comma-joined."""
    text = ", ".join(" ".join(ACRONYMS.get(word.lower(), word.lower()) for word in label(value).split(" ")) for value in values if value)
    return text[:1].upper() + text[1:]


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


def unit_numbers(building):
    """Apartment numbers are floor * 100 + position: 101..120, 201..220, ..."""
    numbering = building["unitNumbering"]
    numbers = [f"{floor}{position:02d}" for floor in range(1, numbering["floors"] + 1) for position in range(1, numbering["unitsPerFloor"] + 1)]
    assert len(numbers) == building["units"], f"Unit numbering does not match the unit count: {building['id']}"
    return numbers


def fill(value, replacements):
    """Deep copy with {placeholder} substitution in every string."""
    if isinstance(value, str):
        for key, replacement in replacements.items():
            value = value.replace("{" + key + "}", str(replacement))
        return value
    if isinstance(value, dict):
        return {key: fill(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [fill(item, replacements) for item in value]
    return value


def expand_owned_meters(scenario, buildings):
    meters = []
    for entry in scenario["ownedMeters"]:
        building = buildings[entry["buildingId"]]
        if entry.get("perUnit"):
            for unit in unit_numbers(building):
                meter = fill(copy.deepcopy(entry), {"unit": unit})
                meter.update(unit=unit, floor=int(unit[:-2]), templateId=entry["id"])
                meters.append(meter)
        else:
            meters.append(copy.deepcopy(entry))
    return meters


def expand_gateway_points(node, buildings):
    points = [dict(point) for point in node.get("points", [])]
    for template in node.get("pointTemplates", []):
        paired = "relatedReadingChannelTemplate" in template
        for index, unit in enumerate(unit_numbers(buildings[template["perUnitOf"]])):
            pt_id = template["ptIdBase"] + index * (2 if paired else 1)
            replacements = {"unit": unit, "ptId": pt_id, "readingPtId": pt_id + 1}
            point = {key: fill(value, replacements) for key, value in template.items() if key not in {"perUnitOf", "channelTemplate", "relatedReadingChannelTemplate", "ptIdBase"}}
            point["ptId"] = pt_id
            point["channelId"] = fill(template["channelTemplate"], replacements)
            if paired:
                point["relatedReadingPoint"] = fill(template["relatedReadingChannelTemplate"], replacements)
            points.append(point)
    return points


def format_address(address):
    return f"{address['line1']}, {address['city']}, {address['state']} {address['postalCode']}"


def account_setup(accounts, buildings, providers, people, onboarding, model, financials, bill_entry):
    """Resolve, per account, every Billing Account editor value that is not the account's own.

    Addresses, representative and invoice template follow the Stage 1B rules; the entry
    method comes from the Phase 1 bill plan; the upload flag, GL defaults and validation
    overrides come from the Phase 3 AP/GL plan.
    """
    rules = model["billingAccountSetup"]
    entry_codes = {key: value for key, value in rules["billEntryTypeCodes"].items() if key != "unusedCodes"}
    representatives = {contact["providerId"]: contact for contact in onboarding["contacts"] if "providerId" in contact}
    internal_reps = rules["accountRepresentative"]["internalProviders"]
    assert set(representatives) | set(internal_reps) == set(providers), "Every provider needs an account representative"
    assert set(internal_reps.values()) <= set(people), "An internal account representative is not in the people register"

    methods = {}
    for rule in bill_entry["bills"]["preferredEntry"]:
        method = rule["method"].split(" (")[0]
        assert method in entry_codes, f"Bill entry method has no Global_Type_Code 'BA2' mapping: {method}"
        for provider_id in rule.get("providers", []):
            methods[provider_id] = method
        if rule.get("scope"):
            methods[rule["scope"]] = method
    assert set(providers) <= set(methods), "Every provider needs a bill entry method"

    gl_chart = {entry["code"] for entry in financials["glChart"]}
    gl_defaults = financials["glAccountDefaults"]
    expense_accounts = gl_defaults["expenseByProvider"]
    assert set(expense_accounts) == set(providers), "Every provider needs a default expense account"
    assert {gl_defaults["apAccount"], *expense_accounts.values()} <= gl_chart, "A default GL account is missing from the chart"

    upload = financials["accountUploadFlags"]
    for rule in upload["rules"]:
        match = rule["match"]
        assert set(match) <= {"providerId", "companyId", "accountId"}, f"Unknown upload-flag match: {match}"
        assert "accountId" not in match or match["accountId"] in accounts, f"Upload flag names an unknown account: {match}"
        assert "providerId" not in match or match["providerId"] in providers, f"Upload flag names an unknown provider: {match}"

    families = {entry["family"] for entry in financials["billValidationRules"]["entries"]}
    overrides = {}
    for override in financials["billValidationRules"]["accountOverrides"]:
        assert override["accountId"] in accounts, f"Validation override names an unknown account: {override['accountId']}"
        assert override["family"] in families, f"Validation override names an unknown test family: {override['family']}"
        threshold = override.get("percent") and f"{override['percent']}%" or override.get("absolute", "")
        overrides.setdefault(override["accountId"], []).append(dict(override, threshold=threshold))

    resolved = {}
    for account in accounts.values():
        building = buildings[account["buildingId"]]
        provider = providers[account["providerId"]]
        representative = representatives.get(provider["id"])
        method = methods.get(building["companyId"], methods[provider["id"]])   # a company scope beats the provider default
        service_type = next((rule["value"] for rule in upload["rules"]
                             if all(value in (account["id"], provider["id"], building["companyId"]) for value in rule["match"].values())), upload["default"])
        resolved[account["id"]] = {
            "serviceAddress": format_address(building["address"]),
            "remitAddress": format_address(provider["billing"]["remitAddress"]),
            "representative": representative["name"] if representative else people[internal_reps[provider["id"]]]["displayName"],
            "representativeContact": (representative or people[internal_reps[provider["id"]]])["email"],
            "representativeAddress": format_address(provider["billing"]["businessAddress"]),
            "invoiceTemplate": rules["invoiceTemplate"],
            "billEntryType": entry_codes[method],
            "billServiceType": service_type,
            "apAccount": gl_defaults["apAccount"],
            "expenseAccount": expense_accounts[provider["id"]],
            "overrides": overrides.get(account["id"], []),
        }
    assert {setup["billServiceType"] for setup in resolved.values()} == {"AP", "AP and GL", "GL", "No Upload"}, "Every bill service type should be exercised"
    return resolved


def point_name(channel, rules):
    if channel.get("pointName"):
        return channel["pointName"]
    template = rules["pointNameByRole"][channel["role"]]
    unit = rules["unitLabels"].get(channel["unit"], channel["unit"])
    interval = rules["intervalLabels"].get(channel.get("intervalMinutes"), "")
    return template.format(unit=unit, interval=interval).strip()


def build_packet(root=ROOT):
    scenario = read_yaml(root, "data/scenarios/demo-university-v1.yaml")
    setup = read_yaml(root, "data/eem/northlake-eem-stage1-setup-v1.yaml")
    model = read_yaml(root, "data/eem/northlake-eem-metaworld-stage1b-v1.yaml")
    onboarding = read_yaml(root, "data/scenarios/northlake-onboarding-v1.yaml")
    security = read_yaml(root, "data/security/northlake-eem-security-v1.yaml")
    financials = read_yaml(root, "data/eem/northlake-ap-gl-v1.yaml")
    bill_entry = read_yaml(root, "data/eem/northlake-bill-entry-v1.yaml")
    people = {p["id"]: p for p in security["users"]}
    providers = {p["id"]: p for p in (read_yaml(root, f.relative_to(root)) for f in sorted((root / "data/providers").glob("*.yaml")))}
    assert {p["id"] for p in scenario["providers"]} == set(providers), "Scenario providers differ from data/providers/*.yaml"
    rules = model["pointRules"]
    measure_types = model["measureTypes"]

    companies = {c["id"]: c["displayName"] for c in scenario["companies"]}
    company_department = {c["id"]: c["responsibleDepartment"] for c in scenario["companies"]}
    assert companies == onboarding["companies"], "Onboarding company names differ from the scenario"
    assert [c["id"] for c in setup["companiesToCreate"]] == list(companies), "Stage 1 companies differ from the scenario"
    sites = {s["id"]: s for s in scenario["sites"]}
    buildings = {}
    for site in sites.values():
        assert site["ownerCompanyId"] in companies, f"Site owner is not a company: {site['id']}"
        for building in site["buildings"]:
            assert building["id"] not in buildings, f"Building listed twice: {building['id']}"
            buildings[building["id"]] = dict(building, siteId=site["id"], companyId=site["ownerCompanyId"])
    assert [c["id"] for c in security["companies"]] == list(companies), "Security manifest companies differ from the scenario"
    for company in security["companies"]:
        owned_sites = sorted(s["id"] for s in sites.values() if s["ownerCompanyId"] == company["id"])
        owned_buildings = sorted(b["id"] for b in buildings.values() if b["companyId"] == company["id"])
        assert sorted(company["scope"]["sites"]) == owned_sites, f"Security scope sites differ from scenario ownership: {company['id']}"
        assert sorted(company["scope"]["buildings"]) == owned_buildings, f"Security scope buildings differ from scenario ownership: {company['id']}"
        for group in company["groups"]:
            assert set(group.get("nodeScope", [])) <= set(owned_buildings), f"Group node scope names a building outside its company: {group['id']}"
    accounts = {a["id"]: a for a in scenario["accounts"]}
    profiles = {p["id"]: p for p in scenario["gatewayBindings"]["profiles"]}
    assert set(profiles) == set(onboarding["sources"]), "Every source profile needs a customer description"

    # Every meter: utility meters from accounts, owned meters (expanded), weather stations.
    meters = []
    for account in accounts.values():
        building = buildings[account["buildingId"]]
        assert building["siteId"] == account["siteId"], f"Account site differs from its building: {account['id']}"
        provider = providers[account["providerId"]]
        assert identifier_pattern(provider["accountModel"]["numberFormat"]).fullmatch(account["syntheticAccountNumber"]), f"Account identifier drift: {account['id']}"
        for meter in account["meters"]:
            assert identifier_pattern(provider["meterModel"]["numberFormat"]).fullmatch(meter["syntheticMeterNumber"]), f"Meter identifier drift: {meter['id']}"
            meters.append(dict(meter, kind="utility", buildingId=account["buildingId"], accountId=account["id"], providerId=account["providerId"], hasBills=True))
    for meter in expand_owned_meters(scenario, buildings):
        meters.append(dict(meter, providerId=None, accountId=None, hasBills=False))
    weather_path = model["weatherIndexTargets"]["hierarchyPath"]
    for station in model["weatherIndexTargets"]["weatherMeters"]:
        channels = [dict(point, id=point["sourceChannelId"], role="weather_forecast" if "Forecast" in point["name"] else "weather_observation", pointName=point["name"]) for point in station["points"]]
        meters.append(dict(id=station["id"], displayName=station["name"], syntheticMeterNumber=station["stationId"], kind="weather_station", buildingId=None,
                           companyId=model["weatherIndexTargets"]["ownerCompanyId"], siteName=weather_path.rsplit(" / ", 1)[-1], parentPath=weather_path,
                           channels=channels, providerId=None, accountId=None, hasBills=False, measureType=station["measureType"], weatherPoints=station["points"]))
    seen = set()
    for meter in meters:
        assert meter["id"] not in seen, f"Meter listed twice: {meter['id']}"
        seen.add(meter["id"])
        if meter["kind"] != "weather_station":
            building = buildings[meter["buildingId"]]
            site = sites[building["siteId"]]
            meter["companyId"] = building["companyId"]
            meter["siteName"] = site["displayName"]
            meter["buildingName"] = building["displayName"]
            meter["parentPath"] = f"System / {companies[building['companyId']]} / {site['displayName']} / {building['displayName']}"
            commodity = meter["channels"][0]["commodity"] if meter["channels"] else None
            meter["measureType"] = measure_types["byMeterType"].get(meter.get("meterType")) or measure_types["byCommodity"][commodity]
        else:
            meter["buildingName"] = meter["siteName"]

    # Points: channels that are not bill facts, plus the weather station points.
    points = {}
    for meter in meters:
        for channel in meter["channels"]:
            if meter["kind"] == "weather_station":
                point = dict(channel, key=channel["id"], name=channel["pointName"], pointType=channel["pointType"], meter=meter)
            elif channel["role"] in rules["billOnlyRoles"]:
                continue
            else:
                assert channel["role"] in rules["pointTypeByRole"], f"Channel role has no point rule: {channel['id']} ({channel['role']})"
                point = dict(channel, key=channel["id"], name=point_name(channel, rules), pointType=rules["pointTypeByRole"][channel["role"]], meter=meter)
            assert point["key"] not in points, f"Repeated channel: {point['key']}"
            points[point["key"]] = point
    bill_channels = {c["id"] for m in meters for c in m["channels"] if c.get("role") in rules["billOnlyRoles"]}
    assert not bill_channels & set(points)

    # Gateway bindings, with per-unit templates expanded.
    bindings, point_sources = [], {}
    for profile in profiles.values():
        for node in profile.get("runtime", {}).get("nodes", []):
            for point in expand_gateway_points(node, buildings):
                key = point["channelId"]
                assert key in points, f"Gateway measurement has no point: {key}"
                if "relatedReadingPoint" in point:
                    reading = points.get(point["relatedReadingPoint"])
                    assert reading and reading["pointType"] == "Accumulator", f"Missing handheld register: {key}"
                bindings.append((profile, node, point, points[key]))
                point_sources.setdefault(key, []).append(profile["id"])
    node_ids = [node["gwNodeId"] for profile in profiles.values() for node in profile.get("runtime", {}).get("nodes", []) if "gwNodeId" in node]
    assert len(node_ids) == len(set(node_ids)), "Gateway node ids must be unique across profiles"
    point_ids = [point["ptId"] for _, _, point, _ in bindings]
    assert len(point_ids) == len(set(point_ids)), "Gateway point ids must be unique across profiles"
    for meter in meters:
        for profile_id in meter.get("gatewayProfiles", []):
            assert any(profile_id in point_sources.get(c["id"], []) for c in meter["channels"]), f"Meter names a gateway profile that binds none of its channels: {meter['id']} / {profile_id}"

    # Hierarchy: company, sites and buildings, from the scenario; weather site from Stage 1B.
    levels = {level["type"]: level for level in setup["companyDefaults"]["levels"]}
    hierarchy = {}
    for company in setup["companiesToCreate"]:
        assert company["dbadminSections"]["levels"] == {"useDefaultsFrom": "companyDefaults.levels"}, f"Company levels must use the shared list: {company['id']}"
        company_name = companies[company["id"]]
        assert company_name == company["companyName"], f"Company name drift: {company['id']}"
        company_path = f"System / {company_name}"
        hierarchy[company_path] = [company_name, company_name, "System", "Company", "Company", "System", "Separate EEM company."]
        owned = [s["id"] for s in sites.values() if s["ownerCompanyId"] == company["id"]]
        assert sorted(owned) == sorted(company["hierarchySitesFromScenario"]), f"Stage 1 sites differ from scenario ownership: {company['id']}"
        for site_id in company["hierarchySitesFromScenario"]:
            site = sites[site_id]
            site_path = f"{company_path} / {site['displayName']}"
            hierarchy[site_path] = [company_name, site["displayName"], company_name, levels["Site"]["description"], "Site", company_path, f"{label(site['type']).capitalize()} grouping. Aggregate points may sit here."]
            for building in site["buildings"]:
                path = f"{site_path} / {building['displayName']}"
                assert path not in hierarchy, f"Duplicate building path: {path}"
                hierarchy[path] = [company_name, building["displayName"], site["displayName"], levels["Location"]["description"], "Location", site_path, "Meter parent. See Meters." if building["kind"] == "building" else "Outdoor service area; meter parent. See Meters."]
        for extra in company.get("additionalSites", []):
            path = f"{company_path} / {extra['name']}"
            hierarchy[path] = [company_name, extra["name"], company_name, levels["Site"]["description"], "Site", company_path, extra["purpose"]]
    assert weather_path in hierarchy, "Weather Reference site must be declared in Stage 1"
    for meter in meters:
        assert meter["parentPath"] in hierarchy, f"Meter has no hierarchy parent: {meter['id']}"
        assert hierarchy[meter["parentPath"]][0] == companies[meter["companyId"]], f"Meter company differs from parent: {meter['id']}"
    building_names = {b["displayName"] for b in buildings.values()}
    assert len(building_names) == len(buildings), "Building display names must be unique across the estate"

    packet = {"version": onboarding["packetVersion"], "issuedOn": onboarding["issuedOn"], "sheets": {}}
    sheets = packet["sheets"]
    sheets["Instructions"] = table(["Topic", "What Northlake Should Provide", "Owner", "Status"], [
        ["Release", f"Northlake onboarding packet {onboarding['packetVersion']} dated {onboarding['issuedOn']}", "Facilities Operations", "Documented"],
        ["Customer workbook", "Data Collection is the single workbook; source systems and tenant requirements are included here.", "All reviewers", "Documented"],
        ["Company contacts", "Use Contacts for people, email and phone. Departments & Responsibilities lists each department's organization and primary contact.", "Campus Operations", "Documented"],
        ["Node hierarchy", "Every company uses Site, Building, Meter and Point levels. Hierarchy lists company, site and building nodes; Meters supplies each meter's full Parent Path; Measured Points lists its children.", "Implementation team", "Documented"],
        ["One building, once", "A physical building appears once, in the company that owns its site, and holds every meter that serves it whatever the provider or commodity. Service Profiles explains why each meter exists.", "Facilities Operations", "Documented"],
        ["Apartments", "Cedar Row is master-metered by building with an owned electric and water submeter in every apartment; Units and Submeters lists them.", "Housing Operations", "Documented"],
        ["First handover", "Student Center electric meter, kWh and kW measurements, AcquiSuite source and one day of sample data.", "Facilities Operations", "Sample supplied"],
        ["Relationships", "Review the Related Measurements, Rollup Members and Weather Assignments tabs with the inventory.", "Facilities Operations", "Documented"],
        ["Scope", "Documented inventory is not evidence of installed setup or successful ingestion.", "Implementation team", "UI acceptance pending"],
        ["Customer revisions", "Return corrections against meter and measurement names; update the versioned sources before issuing the next packet.", "All reviewers", "Ongoing"],
    ], "Facilities and utility onboarding. All organizations, accounts and readings are fictional.")
    sheets["Hierarchy"] = table(["Company", "Node Name", "Parent Node", "Level", "EEM Type", "Parent Path", "Notes"], list(hierarchy.values()), "Company, site and building nodes. Every company uses the same four levels (Site, Building, Meter, Point); a building appears once. Continue with Meters and Measured Points. UI setup remains pending.")
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
        organization_rows.append([contact[0], unit["name"], unit["purpose"], contact[1], contact[3], contact[4], "Documented", contact[7]])
    sheets["Departments & Responsibilities"] = table(["Organization", "Department", "Purpose / Responsibility", "Primary Contact", "Email", "Phone", "Review Status", "Notes"], organization_rows, "Departments and their contacts. Departments describe responsibility only; they never create hierarchy nodes.")
    sheets["Known Events"] = table(["Event Date", "Site / Building", "Event Type", "Affected Service", "Description", "Expected Treatment", "Review Status", "Notes"], onboarding["knownEvents"], "Only the January 15 interval sample is supplied; later events retain explicit fixture and acceptance gaps.")
    sheets["Sites"] = table(["Site Name", "Site Type", "Street Address", "City", "State / Province", "Country", "Responsible Department", "Owning Company", "Review Status", "Notes"], [
        [s["displayName"], sentence(s["type"]), s["address"]["line1"], s["address"]["city"], s["address"]["state"], "USA", company_department[s["ownerCompanyId"]], companies[s["ownerCompanyId"]], "Documented", "See building and service ownership; weather stations are external references."] for s in sites.values()
    ], "Physical properties, the department responsible and the EEM company that owns each. Use Hierarchy for node types and parentage.")
    building_rows, profile_rows = [], []
    es = {p["ref"].get("buildingId"): p for p in scenario["energyStarProperties"] if "buildingId" in p["ref"]}
    for building in buildings.values():
        site = sites[building["siteId"]]
        area = building.get("grossFloorAreaSqft", building.get("parkingAreaSqft", es.get(building["id"], {}).get("grossFloorArea", {}).get("value", "")))
        use = f"{building['units']} apartments" if "units" in building else f"{building['beds']} beds" if "beds" in building else sentence(building["useType"])
        benchmark = es.get(building["id"])
        assert building["kind"] == "grounds" or benchmark, f"Building has no ENERGY STAR property entry: {building['id']}"
        parent = sites[benchmark["parentSiteId"]]["displayName"] if benchmark and benchmark.get("parentSiteId") else ""
        note = {
            None: "Outdoor service area with no floor area; not benchmarked.",
            "child_property": f"ENERGY STAR child property of {parent}" + ("; parking area excluded from the campus floor area." if "parkingAreaSqft" in building else "."),
            "building_within_property": f"Building within the {parent} ENERGY STAR property.",
            "standalone_property": "Benchmarked as its own ENERGY STAR property, outside the campus boundary.",
        }[benchmark["role"] if benchmark else None]
        building_rows.append([building["displayName"], site["displayName"], sentence(building["useType"]), company_department[building["companyId"]], building["address"]["line1"], area, "sq ft" if area != "" else "", use, "Documented", note])
        profile = building.get("serviceProfile", {})
        profile_rows.append([building["displayName"], sentence(profile.get("heating")), sentence(profile.get("cooling")), sentence(profile.get("domesticHotWater")), sentence(profile.get("kitchen"), *profile.get("processLoads", [])), sentence(profile.get("onsiteGeneration")), sentence(profile.get("fireProtection")), sentence(*profile.get("submetering", []), *profile.get("irrigation", []), *profile.get("production", [])), profile.get("notes", "")])
    sheets["Buildings"] = table(["Building Name", "Site Name", "Building Type", "Responsible Department", "Service Address", "Gross Area", "Area Unit", "Occupancy / Use Notes", "Review Status", "Notes"], building_rows, "Physical building inventory and responsible departments. Each building appears once; use Hierarchy for EEM parents and Service Profiles for why its meters exist.")
    sheets["Service Profiles"] = table(["Building", "Heating", "Cooling", "Domestic Hot Water", "Kitchen / Process Loads", "On-site Generation", "Fire Protection", "Submetering / Irrigation / Production", "Notes"], profile_rows, "The physical services each building needs. Every meter on the Meters tab traces back to one of these services.")

    service_rows, rate_rows, component_rows = [], [], []
    unit_labels = dict(rules["unitLabels"], eru="ERU")
    for target in model["utilityProviderTargets"]:
        provider = providers[target["id"]]
        schedules = provider["rateSchedules"]
        assert set(target["rateSchedules"]) == {r["id"] for r in schedules}, f"Stage 1B rate schedules differ from the provider file: {target['id']}"
        usage_units = dict.fromkeys(unit_labels.get(p["usageUnit"], p["usageUnit"]) for p in provider["supplies"] if "usageUnit" in p)
        service_rows.append([provider["displayName"], sentence(*target["commoditySetup"]), provider["displayName"], ", ".join(companies[c] for c in target["companiesUsingProvider"]), ", ".join(r["id"] for r in schedules), ", ".join(usage_units), "Monthly", "Documented", "Tariff sheets and Rate Components provide the numeric charges."])
        for rate in schedules:
            rate_rows.append([provider["displayName"], rate["id"], sentence(rate["type"]), rate["effective"], sentence(*rate["components"])])
            for name, component in rate_components(rate["components"]):
                basis = component.get("basis", "")
                if "upToKgal" in component:
                    basis = f"Tier upper limit: {component['upToKgal']} kgal" if component["upToKgal"] is not None else "Remaining usage above the previous tier"
                component_rows.append([provider["displayName"], rate["id"], sentence(name), component["rate"], component["unit"], basis, rate["effective"]])
    sheets["Utility Services"] = table(["Service Name", "Service Category", "Provider / Counterparty", "Applies To Site", "Rate / Tariff", "Commodity Units", "Billing Frequency", "Review Status", "Notes"], service_rows, "Five counterparties. Source systems and file formats are a separate inventory.")
    sheets["Rate Schedules"] = table(["Provider", "Schedule", "Type", "Effective", "Key charges"], rate_rows, "Base contractual tariffs. Analysis-only rate models remain a separate implementation phase.")
    sheets["Rate Components"] = table(["Provider", "Schedule", "Charge", "Rate", "Unit", "Basis", "Effective"], component_rows, "Numeric charges from the provider tariff sources. Full schedules and tariff terms are also required for rate-engine acceptance.")

    account_rows, detail_rows, setup_rows, override_rows = [], [], [], []
    setups = account_setup(accounts, buildings, providers, people, onboarding, model, financials, bill_entry)
    account_kinds = model["billingAccountKinds"]
    for account in accounts.values():
        provider = providers[account["providerId"]]
        kind = account_kinds[provider["billingModel"]]
        building = buildings[account["buildingId"]]
        rates = account.get("rateScheduleIds", [account.get("rateScheduleId")])
        schedules_by_id = {s["id"]: s for s in provider["rateSchedules"]}
        assert all(r in schedules_by_id for r in rates), f"Unknown rate schedule on {account['id']}"
        for rate_id in rates:
            for charge in schedules_by_id[rate_id]["components"].values():
                if isinstance(charge, dict) and charge and all(re.fullmatch(r"\d+(?:\.\d+)?in", size) for size in charge):
                    for meter in account["meters"]:
                        assert meter.get("meterSize") in charge, f"{rate_id} has no charge for meter size {meter.get('meterSize')}: {meter['id']}"
        name = f"{building['displayName']} / {provider['shortName']}"
        setup = setups[account["id"]]
        account_rows.append([name, provider["displayName"], ACCOUNT_KIND_LABELS[kind], account["syntheticAccountNumber"], f"{companies[building['companyId']]} / {building['displayName']}", account["syntheticAccountNumber"] if kind == "internalCostCenters" else "", account.get("effectiveStart", scenario["dateRange"]["start"]), account.get("effectiveEnd", "Active"), "Finance and Accounts Payable", "Documented", ", ".join(rates)])
        detail_rows.append([account["syntheticAccountNumber"], name, setup["serviceAddress"], setup["remitAddress"], setup["representative"], setup["representativeContact"]])
        setup_rows.append([account["syntheticAccountNumber"], name, companies[building["companyId"]], setup["billEntryType"], setup["billServiceType"], setup["invoiceTemplate"], setup["apAccount"], setup["expenseAccount"], "; ".join(f"{o['family']} {o['state']} {o['threshold']}".strip() for o in setup["overrides"]) or "Inherits company"])
        for override in setup["overrides"]:
            override_rows.append([account["syntheticAccountNumber"], name, override["family"], override["state"], override["threshold"], override["why"]])
    sheets["Accounts And Agreements"] = table(["Account / Agreement Name", "Provider / Counterparty", "Service Category", "Account Number", "Site / Building Scope", "Cost Center", "Start Date", "End Date", "Billing Contact", "Review Status", "Notes"], account_rows, "One row per provider account, PPA agreement or internal cost center; several services may share an account. Owned submeters have no account.")
    sheets["Account Billing Details"] = table(["Account Number", "Account / Agreement", "Service Address", "Remit To", "Account Representative", "Representative Email"], detail_rows, "Where each account is served, where its bills are paid, and who the provider's representative is. The service address is the building's; the remit address and representative belong to the provider.")
    packet["accountSetup"] = table(["Account Number", "Account / Agreement", "Company", "Bill Entry Type", "Bill Service Type", "Bill Invoice Template", "Default AP Account", "Default Expense Account", "Bill Validation Tests"], setup_rows, "What to enter on the Billing Account editor beyond the account's own identity. Entry type records how the bills arrive, service type whether the account reaches AP, GL, both or neither.")
    packet["validationOverrides"] = table(["Account Number", "Account / Agreement", "Test", "Setting", "Threshold", "Why"], override_rows, "Bill validation tests set at account scope. Every other account inherits its company, and the company inherits Global.")

    meter_rows, point_rows, related_rows, mapping_rows, unit_rows = [], [], [], [], {}
    meter_names = {meter["id"]: meter["displayName"] for meter in meters}
    for meter in meters:
        source_ids = list(dict.fromkeys(s for c in meter["channels"] for s in point_sources.get(c["id"], [])))
        roles = {c.get("role") for c in meter["channels"]}
        read_method = "; ".join(onboarding["sources"][s][0] for s in source_ids) or ("Manual monthly reading" if roles & MANUAL_ROLES else "Bill / allocation statement" if meter["hasBills"] else "Calculated or awaiting source setup")
        account = accounts.get(meter.get("accountId"))
        notes = f"Company: {companies[meter['companyId']]}. Account: {account['syntheticAccountNumber'] if account else 'No billing account'}."
        for relation in ["behindMeterId", "replacesMeterId", "overlapsMeterId"]:
            assert meter.get(relation) is None or meter[relation] in meter_names, f"Meter {relation} names an unknown meter: {meter['id']}"
        if meter.get("behindMeterId"):
            notes += f" Behind {meter_names[meter['behindMeterId']]}."
        if meter.get("effectiveStart"):
            notes += f" Service dates: {meter['effectiveStart']} through {meter.get('effectiveEnd') or 'active'}."
        if meter.get("replacesMeterId"):
            notes += f" Replaces {meter_names[meter['replacesMeterId']]}; keep histories separate."
        if not meter["channels"]:
            notes += " Flat-rate service with no metered usage."
        if meter.get("notes"):
            notes += " " + meter["notes"]
        provider_name = providers[meter["providerId"]]["displayName"] if meter.get("providerId") else "Public weather station" if meter["kind"] == "weather_station" else "Northlake owned"
        meter_rows.append([meter["displayName"], meter["syntheticMeterNumber"], meter["measureType"], meter["siteName"], meter["buildingName"], provider_name, KIND_LABELS[meter["kind"]], companies[meter["companyId"]], read_method, "Documented", notes, meter["parentPath"]])
        if meter.get("unit"):
            row = unit_rows.setdefault((meter["buildingId"], meter["unit"]), [meter["buildingName"], meter["unit"], meter["floor"], "", "", "", "", "", ""])
            usage = [c for c in meter["channels"] if c["role"] != "handheld_register_reading"]
            register = [c for c in meter["channels"] if c["role"] == "handheld_register_reading"]
            if meter["channels"][0]["commodity"] == "electric":
                row[3], row[4] = meter["syntheticMeterNumber"], points[usage[0]["id"]]["name"]
            else:
                row[5], row[6], row[7] = meter["syntheticMeterNumber"], points[register[0]["id"]]["name"], points[usage[0]["id"]]["name"]
            row[8] = "; ".join(dict.fromkeys(filter(None, [row[8], read_method])))
        for channel in meter["channels"]:
            if channel["id"] not in points:
                continue
            point = points[channel["id"]]
            interval = point.get("intervalMinutes")
            frequency = "Monthly / actual bill period" if interval is None else "Monthly route / actual reading dates" if interval == 43200 else f"{interval} minutes"
            point_rows.append([point["name"], meter["displayName"], sentence(point["role"]), point["pointType"], point["unit"], frequency, "Exclude test signal" if meter.get("excludeFromTotals") else "Yes", "Documented", "Source: " + "; ".join(onboarding["sources"][s][0] for s in point_sources[point["key"]]) if point["key"] in point_sources else "Manual reading, related-point calculation or a later input path."])
            mapping_rows.append(["Point", point["key"], companies[meter["companyId"]], meter["buildingName"], meter["displayName"], point["name"], point["unit"], interval, "", "", "", "", "Not entered", ""])
            for related in point.get("createsRelatedPoints", []):
                related_rows.append([meter["displayName"], point["name"], meter["displayName"], related, "Heating degree days" if related.startswith("HDD") else "Cooling degree days", "Daily", "Create through the temperature index setting; verify base and calculation method in the UI."])
                mapping_rows.append(["Weather related point", f"{meter['id']}.{related}", companies[meter["companyId"]], meter["buildingName"], meter["displayName"], related, "Degree days (F)", 1440, "", "", "", "", "Not entered", ""])
        registers = [points[c["id"]] for c in meter["channels"] if c["id"] in points and points[c["id"]]["pointType"] == "Accumulator"]
        deltas = [points[c["id"]] for c in meter["channels"] if c["id"] in points and points[c["id"]]["pointType"] == "AccumulatorDelta"]
        assert len(registers) == len(deltas) <= 1, f"Register and usage points must come in pairs: {meter['id']}"
        for register, delta in zip(registers, deltas):
            related_rows.append([meter["displayName"], register["name"], meter["displayName"], delta["name"], rules["registerUsageReasonText"], "Actual reading dates", "Multiplier 1 for the initial case; capture the automatically created usage-point ID. Do not create an unrelated second usage point."])
    for baseline in model["baselineTargets"]:
        point = points[baseline["measuredPoint"]]
        assert point["unit"] == baseline["unit"] and point["intervalMinutes"] == baseline["intervalMinutes"], f"Baseline differs from its measured point: {baseline['id']}"
        related_rows.append([point["meter"]["displayName"], point["name"], point["meter"]["displayName"], baseline["baselinePointName"], "Measured versus baseline", f"{baseline['intervalMinutes']} minutes", "Baseline definition only; calculation and expected values are a later acceptance step."])
        mapping_rows.append(["Baseline point", baseline["id"], companies[baseline["companyId"]], point["meter"]["buildingName"], point["meter"]["displayName"], baseline["baselinePointName"], baseline["unit"], baseline["intervalMinutes"], "", "", "", "", "Not entered", ""])
    sheets["Meters"] = table(["Meter Name", "Meter Number / Tag", "Service Category", "Site Name", "Building Name", "Provider / Counterparty", "Meter Kind", "Ownership", "Read Method", "Review Status", "Notes", "Parent Path"], meter_rows, "Create each Meter node beneath its full Parent Path from Hierarchy. Measured Points identifies its Point children; bill-only meters have none. Ownership identifies the EEM company.")
    sheets["Units and Submeters"] = table(["Building", "Unit", "Floor", "Electric Submeter Tag", "Electric Point", "Water Submeter Tag", "Water Register Point", "Water Usage Point", "Read Method"], [unit_rows[key] for key in sorted(unit_rows)], "One row per apartment. Each apartment has an owned electric submeter and an owned water submeter behind the building's utility master meters; tenant rebilling maps to these points.")
    sheets["Measured Points"] = table(["Point Name", "Meter Name", "Measurement", "Direction / Role", "Units", "Interval / Frequency", "Use In Reporting", "Review Status", "Notes"], point_rows, "Point definitions for interval, route, register, sensor and equipment channels. Bill usage stays on the billing account and has no point here.")
    sheets["Related Measurements"] = table(["Source Meter", "Source Measurement", "Related Meter", "Related Measurement", "Relationship", "Frequency", "Requirement"], related_rows, "Business relationships to create through the product's supported point/index settings.")
    rollups = []
    for aggregate in model["aggregateTargets"]:
        assert aggregate["parentPath"] in hierarchy, f"Aggregate parent is not a hierarchy node: {aggregate['id']}"
        mapping_rows.append(["Aggregate point", aggregate["id"], companies[aggregate["companyId"]], aggregate["parentPath"].rsplit(" / ", 1)[-1], "", aggregate["aggregatePointName"], aggregate["unit"], aggregate["intervalMinutes"], "", "", "", "", "Not entered", ""])
        members = list(aggregate["members"])
        if "memberTemplate" in aggregate:
            template = aggregate["memberTemplate"]
            members += [dict(template, sourceChannelId=fill(template["channelTemplate"], {"unit": unit})) for unit in unit_numbers(buildings[template["perUnitOf"]])]
        for member in members:
            point = points[member["sourceChannelId"]]
            assert point["unit"] == aggregate["unit"] and point["intervalMinutes"] == aggregate["intervalMinutes"], f"Incompatible aggregate member: {aggregate['id']}"
            rollups.append([aggregate["aggregatePointName"], point["meter"]["displayName"], point["name"], member["multiplier"], "Required" if member["required"] else "Optional", aggregate["unit"], aggregate["intervalMinutes"], aggregate["boundary"]])
    sheets["Rollup Members"] = table(["Requested Total", "Member Meter", "Member Measurement", "Multiplier", "Availability", "Unit", "Interval Minutes", "Boundary"], rollups, "One row per member. Aggregate points sit directly under the site or building they summarise. Never add monthly bills to their interval representation or include the commissioning test signal.")
    assignments = model["weatherIndexTargets"]["stationAssignments"]
    exceptions = {(a["companyId"], a["buildingId"]): a["stationId"] for a in assignments.get("exceptions", [])}
    sheets["Weather Assignments"] = table(["Organization", "Location", "Reference Station"], [[companies[b["companyId"]], b["displayName"], exceptions.get((b["companyId"], b["id"]), assignments["defaultStationId"])] for b in buildings.values()], "Shared station ownership avoids duplicating weather measurements under every building; every building in every company is assigned.")
    sheets["Open Items"] = table(["Open Item", "Requested From", "Needed By", "Priority", "Current Status", "Resolution Notes"], [[item, "Implementation team", "Before the relevant acceptance run", "Medium", "Open", ""] for item in onboarding["deferredAcceptance"]], "Documented boundaries and remaining acceptance work. Sample availability does not close these items.")

    source_rows, source_mapping_rows, coverage_rows = [], [], []
    for key, profile in profiles.items():
        name, owner, method, format_name, cadence, timestamps = onboarding["sources"][key]
        bound = [b for b in bindings if b[0]["id"] == key]
        references = ", ".join(dict.fromkeys(b[3]["meter"]["buildingName"] for b in bound)) or "Neptune and MVRS reading events"
        sample = "Supplied: AcquiSuite complete, gap and backfill" if key == onboarding["acquiSuiteSample"]["profileId"] else "Sample / service not yet supplied"
        source_rows.append([name, method, format_name, owner, method, cadence, references, owner, "Documented", f"{timestamps}. {sample}."])
        for variant in profile.get("formatVariants", [profile["gatewayType"]]):
            coverage_rows.append([key, variant, references, len(bound), "Generated" if key == onboarding["acquiSuiteSample"]["profileId"] else "Planned", "Not run", "Not run"])
        for _, node, point, target in bound:
            values = point.get("values", {})
            selectors = "; ".join(f"{'Route ID' if k == 'MetaWorldID' else k}={v}" for k, v in values.items() if k not in {"PtID_Usage", "PtID_Reading"})
            device = node.get("values", {}).get("Serial Number", node["name"])
            source_mapping_rows.append([name, target["meter"]["displayName"], target["name"], device, selectors, target["unit"], timestamps])
    for provider in providers.values():
        source_rows.append([f"{provider['displayName']} billing", "Billing statement", "Monthly utility / allocation / PPA statement", "Finance", "Statement and supported bill-import file", "Monthly", provider["shortName"], "Finance", "Documented", "Existing illustrated bills are examples; reconcile their values before rate or bill acceptance."])
    sheets["Data Sources"] = table(["Source Name", "Source Type", "Service Category", "Owner / Vendor", "Delivery Method", "Expected Cadence", "File / System Reference", "Credential Owner", "Review Status", "Notes"], source_rows, "Source ownership and delivery information. Credentials are exchanged separately and are never stored in the workbook.")
    sheets["Source Measurements"] = table(["Source System", "Meter", "Measurement", "Device / Station", "Channel / Source Fields", "Unit", "Timestamp Convention"], source_mapping_rows, "Vendor-side identifiers matched to the customer's measurement inventory; installed database IDs belong in the implementation record.")
    packet["coverage"] = table(["Profile", "Format", "Destinations", "Measurements", "Artifact status", "UI setup", "Ingestion acceptance"], coverage_rows, "Independent format cases; planned coverage is not a claim of supported installed behavior.")
    packet["instanceMapping"] = table(["Object kind", "Source reference", "Company", "Location", "Meter", "Point", "Unit", "Interval minutes", "Installed point ID", "Installed meter ID", "Installed gateway ID", "Installed node ID", "Status", "Evidence"], mapping_rows, "Copy before use. Capture real IDs after UI creation; never insert the illustrative IDs from a scenario into EEMSuite.")
    packet["decisions"] = onboarding["decisions"]
    packet["counts"] = {"companies": len(companies), "sites": len(sites), "buildings": len(buildings), "providers": len(providers), "accounts": len(accounts),
                        "utilityMeters": sum(m["kind"] == "utility" for m in meters), "ownedMeters": sum(m["kind"] not in {"utility", "weather_station"} for m in meters), "weatherStations": sum(m["kind"] == "weather_station" for m in meters),
                        "meters": len(meters), "points": len(points), "apartments": len(unit_rows), "relatedMeasurements": len(related_rows), "aggregates": len(model["aggregateTargets"]),
                        "gatewayProfiles": len(profiles) - 1, "gatewayFormats": len(coverage_rows) - 1, "eventPublishers": 1, "baseRates": len(rate_rows), "contacts": len(contacts), "organizationUnits": len(organization_rows)}
    return packet


def sample_files(root=ROOT):
    onboarding = read_yaml(root, "data/scenarios/northlake-onboarding-v1.yaml")
    spec = onboarding["acquiSuiteSample"]
    scenario = read_yaml(root, "data/scenarios/demo-university-v1.yaml")
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


def register_markdown(packet):
    register_sheets = ["Hierarchy", "Departments & Responsibilities", "Contacts", "Sites", "Buildings", "Service Profiles", "Accounts And Agreements", "Account Billing Details", "Meters", "Units and Submeters", "Measured Points", "Related Measurements", "Rollup Members", "Weather Assignments"]
    register = ["# Northlake Facilities and Meter Register", "", f"Packet {packet['version']} | Issued {packet['issuedOn']} | Fictional customer", "", "This register describes the requested setup. Every building appears once, under the company that owns its site, and lists every meter that serves it. Installation and ingestion acceptance are pending.", "", "## Customer decisions", ""]
    register += [f"- **{name}:** {text}" for name, text in packet["decisions"]]
    for name in register_sheets:
        register += ["", f"## {name}", "", packet["sheets"][name]["description"], "", markdown_table(packet["sheets"][name])]
    return "\n".join(register) + "\n"


def source_inventory_markdown(packet):
    sources = ["# Northlake Source System Inventory", "", f"Packet {packet['version']} | Issued {packet['issuedOn']} | Facilities, IT and Finance", "", "Match each delivered measurement to the register. Only the AcquiSuite sample is supplied in this release; the remaining feeds require files, fixtures or services.", "", markdown_table(packet["sheets"]["Data Sources"]), "", "## Measurement mapping", "", markdown_table(packet["sheets"]["Source Measurements"])]
    return "\n".join(sources) + "\n"


def gateway_coverage_markdown(packet):
    coverage = ["# Northlake Gateway Setup Coverage", "", "Generated from the scenario profiles. Each format is a separate acceptance case. No installed setup or ingestion result has been recorded.", "", markdown_table(packet["coverage"]), "", "FIG variants reuse one point in separate restored runs. HMR publishes reading events rather than interval measurements. Catalog entries without a represented runnable component remain outside this list and must be reconciled against the installed product before claiming complete gateway coverage."]
    return "\n".join(coverage) + "\n"


def billing_account_setup_markdown(packet):
    setup = ["# Northlake Billing Account Setup", "",
             f"Packet {packet['version']} | Issued {packet['issuedOn']} | Enter on the Billing Account editor", "",
             "Every billing account carries more than its number and provider. This lists the rest of the editor for each account: where its bills arrive from, whether it reaches AP or the GL, which invoice template it prints with, and its default GL accounts. The service address, remit address and account representative are in the facilities and meter register.", "",
             "The GL accounts and the validation overrides need their Phase 3 prerequisites in place: the chart of accounts must exist before an account can point at one, and the global validation tests before an account can override one.", "",
             "## Account setup", "", packet["accountSetup"]["description"], "", markdown_table(packet["accountSetup"]), "",
             "## Bill validation overrides", "", packet["validationOverrides"]["description"], "", markdown_table(packet["validationOverrides"])]
    return "\n".join(setup) + "\n"


# Documents rendered straight from the packet, with no Markdown source: PDF path -> (masthead, Markdown).
GENERATED_DOCUMENTS = {
    "documents/intake-package/facilities-and-meter-register.pdf": ({"department": "Facilities Operations"}, register_markdown),
    "documents/intake-package/source-system-inventory.pdf": ({"department": "Facilities Operations"}, source_inventory_markdown),
    "implementation/northlake-gateway-coverage.pdf": ({}, gateway_coverage_markdown),
    "implementation/northlake-billing-account-setup.pdf": ({}, billing_account_setup_markdown),
}


def render_generated_document(packet, pdf, output, root=ROOT):
    masthead, markdown = GENERATED_DOCUMENTS[pdf]
    render_markdown(markdown(packet), output, defaults={**defaults_for(pdf, root), **masthead})


def write_packet(root=ROOT, dump_json=None):
    packet = build_packet(root)
    if dump_json:
        dump_json.parent.mkdir(parents=True, exist_ok=True)
        dump_json.write_text(json.dumps(packet, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    for pdf in GENERATED_DOCUMENTS:
        render_generated_document(packet, pdf, root / pdf, root)
    with (root / "data/eem/northlake-instance-mapping.template.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(packet["instanceMapping"]["headers"])
        writer.writerows(packet["instanceMapping"]["rows"])
    samples = sample_files(root)
    for case, sample in samples.items():
        directory = root / SAMPLES / case
        directory.mkdir(parents=True, exist_ok=True)
        (directory / sample["filename"]).write_bytes(sample["content"].encode())
    spec = read_yaml(root, "data/scenarios/northlake-onboarding-v1.yaml")["acquiSuiteSample"]
    expected = {"profile": spec["profileId"], "timestampConvention": spec["timestampConvention"], "localDate": spec["localDate"], "localTimeZone": "America/Los_Angeles", "installedAcceptance": "Not run", "cases": {case: {k: v for k, v in data.items() if k != "content"} for case, data in samples.items()}}
    (root / SAMPLES / "expected-results.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(packet["counts"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate sources and sample expectations without writing files")
    parser.add_argument("--dump-json", type=Path, metavar="PATH", help="Also write the joined packet as JSON for inspection")
    args = parser.parse_args()
    if args.check:
        packet = build_packet()
        sample_files()
        print(json.dumps(packet["counts"], indent=2))
    else:
        write_packet(dump_json=args.dump_json)
