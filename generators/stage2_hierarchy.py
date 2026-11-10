"""Write the Stage 2 (Hierarchy) editor files for Northlake from the customer source model.

One-time generation: the files become the hand-maintained implementation afterwards.

This module rebuilds the same accounts / meters / points join that
generators.northlake_packet.build_packet() performs (see account_setup,
meter_and_point_setup, point_name, expand_owned_meters), reusing those exact functions, but
keeps the per-record objects instead of collapsing them into the intake-packet's report
tables. It also builds the three things build_packet does not model as hierarchy objects at
all: the two weather-station meters as Stage 2 Meter nodes, the 7 aggregates and their
members, and the 3 baseline point shells.

Refuses to overwrite an existing output file unless --force is given.
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

import yaml

from generators.northlake_packet import (
    ROOT,
    account_setup,
    build_packet,
    expand_owned_meters,
    meter_and_point_setup,
    point_name,
    read_yaml,
)

OUT = ROOT / "implementation" / "stage-2-hierarchy"
RECORDED = date(2026, 9, 18)
COUNTRY = "UNITED STATES"
TIME_ZONE = "(GMT-08:00) Pacific Time (US & Canada); Tijuana"

# Real hierarchy node ids already installed before Stage 2 begins (per the survey handed to
# this generator; Database Administrator, Nodes, as of 2026-09-18).
INSTALLED_NODE = {
    "northlake_main_campus": 22, "admin_hall": 23, "science_center": 24, "library": 25,
    "student_center": 26, "lakeview_hall": 27, "recreation_center": 28, "parking_structure": 29,
    "campus_grounds": 34, "weather_reference": 33,
    "sacramento_executive_airport": 38, "sacramento_international_airport": 39,
    "cedar_row_apartments": 8, "cedar_row_a": 9, "cedar_row_b": 10,
    "cedar_row_common_house": 11, "cedar_row_carport_grounds": 35,
    "northlake_central_plant": 31, "central_plant": 32,
}
# curBaselineCalc rows seeded in the installed database (verified by SELECT, 2026-09-18); no
# client can create or edit these, so the algorithm picked here is a read of what already
# exists, not an invented value.
BASELINE_ALGORITHM = "Rolling Day Type Forecast"


class Flow(dict):
    """A mapping dumped on one line."""


class Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


Dumper.add_representer(Flow, lambda d, data: d.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True))
Dumper.add_representer(type(None), lambda d, _: d.represent_scalar("tag:yaml.org,2002:null", ""))


def dump(name: str, header: str, data: dict, force: bool) -> None:
    path = OUT / name
    if path.exists() and not force:
        print(f"skip {name} (already exists; pass --force to overwrite)")
        return
    text = yaml.dump(data, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=110, default_flow_style=False)
    # Mark the handful of invented values the source model does not state, per the stage
    # convention (CONVENTIONS.md: "invent it plausibly, mark it with a `# assumed` comment").
    for needle in ("Currency Unit: USD", "Bill Service Type: AP Upload Only", "Bill Service Type: No AP Upload",
                   "Baseline Algorithm: Rolling Day Type Forecast"):
        text = text.replace(needle + "\n", needle + "  # assumed\n")
    full = header.rstrip("\n") + "\n" + text
    path.write_text(full, encoding="utf-8", newline="\n")
    print("wrote", name, "-", full.count("\n"), "lines")


def address_fields(a: dict, with_coordinates: bool = False) -> dict:
    out = {"Address": a["line1"], "City": a["city"], "Region": a["state"] if "state" in a else a.get("stateProvince"),
           "Postal Code": a["postalCode"], "Country": COUNTRY}
    if with_coordinates:
        out["Latitude"] = a["latitude"]
        out["Longitude"] = a["longitude"]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Overwrite files that already exist")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # build_packet() validates the whole source model (asserts) before we touch it; if the
    # model is inconsistent this raises before any Stage 2 file is written.
    build_packet()

    scenario = read_yaml(ROOT, "data/scenarios/demo-university-v1.yaml")
    setup = read_yaml(ROOT, "data/eem/northlake-eem-stage1-setup-v1.yaml")
    model = read_yaml(ROOT, "data/eem/northlake-eem-metaworld-stage1b-v1.yaml")
    onboarding = read_yaml(ROOT, "data/scenarios/northlake-onboarding-v1.yaml")
    security = read_yaml(ROOT, "data/security/northlake-eem-security-v1.yaml")
    financials = read_yaml(ROOT, "data/eem/northlake-ap-gl-v1.yaml")
    bill_entry = read_yaml(ROOT, "data/eem/northlake-bill-entry-v1.yaml")
    people = {p["id"]: p for p in security["users"]}
    providers = {p["id"]: p for p in (read_yaml(ROOT, f.relative_to(ROOT)) for f in sorted((ROOT / "data/providers").glob("*.yaml")))}
    providers_stage1 = {r["key"]: r for r in yaml.safe_load((ROOT / "implementation/stage-1-foundation/02-utility-providers.yaml").read_text(encoding="utf-8"))["records"]}
    rules = model["pointRules"]
    measure_types = model["measureTypes"]

    companies = {c["id"]: c["displayName"] for c in scenario["companies"]}
    company_department = {c["id"]: c["responsibleDepartment"] for c in scenario["companies"]}
    sites = {s["id"]: s for s in scenario["sites"]}
    buildings: dict[str, dict] = {}
    for site in sites.values():
        for b in site["buildings"]:
            buildings[b["id"]] = dict(b, siteId=site["id"], companyId=site["ownerCompanyId"])
    accounts = {a["id"]: a for a in scenario["accounts"]}

    # ---------------------------------------------------------------- meters (mirrors build_packet)
    meters = []
    for account in accounts.values():
        for meter in account["meters"]:
            meters.append(dict(meter, kind="utility", buildingId=account["buildingId"], accountId=account["id"], providerId=account["providerId"], hasBills=True))
    for meter in expand_owned_meters(scenario, buildings):
        meters.append(dict(meter, providerId=None, accountId=None, hasBills=False))
    weather_path = model["weatherIndexTargets"]["hierarchyPath"]
    weather_company = model["weatherIndexTargets"]["ownerCompanyId"]
    for station in model["weatherIndexTargets"]["weatherMeters"]:
        channels = [dict(point, id=point["sourceChannelId"], role="weather_forecast" if "Forecast" in point["name"] else "weather_observation", pointName=point["name"])
                    for point in station["points"]]
        meters.append(dict(id=station["id"], displayName=station["name"], syntheticMeterNumber=station["stationId"], kind="weather_station",
                            buildingId=None, companyId=weather_company, siteName=weather_path.rsplit(" / ", 1)[-1], parentPath=weather_path,
                            channels=channels, providerId=None, accountId=None, hasBills=False, measureType=station["measureType"]))

    for meter in meters:
        if meter["kind"] != "weather_station":
            building = buildings[meter["buildingId"]]
            site = sites[building["siteId"]]
            meter["companyId"] = building["companyId"]
            meter["siteName"] = site["displayName"]
            meter["buildingName"] = building["displayName"]
            commodity = meter["channels"][0]["commodity"] if meter["channels"] else None
            meter["measureType"] = measure_types["byMeterType"].get(meter.get("meterType")) or measure_types["byCommodity"][commodity]
        else:
            meter["buildingName"] = meter["siteName"]

    # ---------------------------------------------------------------- points (mirrors build_packet)
    points: dict[str, dict] = {}
    for meter in meters:
        for channel in meter["channels"]:
            if meter["kind"] == "weather_station":
                point = dict(channel, key=channel["id"], name=channel["pointName"], pointType=channel["pointType"], meter=meter)
            elif channel["role"] in rules["billOnlyRoles"]:
                continue
            else:
                point = dict(channel, key=channel["id"], name=point_name(channel, rules), pointType=rules["pointTypeByRole"][channel["role"]], meter=meter)
            points[point["key"]] = point

    # Mutates meters (multiplier/providerMeterNumber/billCycle) and points (unitName/measureType/
    # archiveInterval/indexType/howCreated) in place; also asserts the product's own limits.
    meter_and_point_setup(meters, points, providers, model)

    # Register points get an automatic AccumulatorDelta; capture that on the register's own
    # installed: block rather than modelling 128 near-duplicate stub records.
    registers = [p for p in points.values() if p["pointType"] == "Accumulator"]

    # The 2 temperature points drive HDD/CDD via the Degree Days index, straight off the source
    # station definition (not off point["indexType"], which the model reuses as an internal
    # "must be a Temperature point" sentinel rather than the UI's own "Degree Days" label).
    temperature_points = []
    for station in model["weatherIndexTargets"]["weatherMeters"]:
        for raw in station["points"]:
            if raw.get("indexType") == "DegreeDays":
                temperature_points.append(raw["sourceChannelId"])

    # 3 baseline point shells: new Analog points, same measure type/unit/interval/meter as the
    # point they baseline, not modelled as channels anywhere in the scenario.
    baseline_records = []
    for bl in model["baselineTargets"]:
        measured = points[bl["measuredPoint"]]
        baseline_records.append({
            "key": bl["id"], "name": bl["baselinePointName"], "meterKey": measured["meter"]["id"],
            "measureType": measured["measureType"], "unitName": measured["unitName"], "archiveInterval": measured["archiveInterval"],
            "measuredKey": bl["measuredPoint"], "measuredName": measured["name"], "companyId": bl["companyId"],
        })

    account_results = account_setup(accounts, buildings, providers, people, onboarding, model, financials, bill_entry)

    # ================================================================== 01 billing accounts
    ACCOUNT_KIND = model["billingAccountKinds"]
    BILL_SERVICE_TYPE = {"externalUtilityAccounts": "AP Upload Only", "internalCostCenters": "No AP Upload", "ppaAgreements": "No AP Upload"}
    INVOICE_TEMPLATE = "Bill Table Invoice Default"

    account_records = []
    for aid, account in accounts.items():
        provider = providers[account["providerId"]]
        building = buildings[account["buildingId"]]
        kind = ACCOUNT_KIND[provider["billingModel"]]
        setup_row = account_results[aid]
        p1 = providers_stage1[account["providerId"]]
        remit = p1["Remit Addresses"][0]
        remit_text = f"{remit['Address']}, {remit['City']}, {remit['Region']} {remit['Postal Code']}"
        account_records.append({
            "key": aid,
            "installed": {"billingAccountId": None},
            "Company": companies[building["companyId"]],
            "Definitions": {
                "Account Number": account["syntheticAccountNumber"],
                "Description": f"{building['displayName']} / {provider['shortName']}",
                "Currency Unit": "USD",
                "Utility Provider": provider["displayName"],
                "Bill Service Type": BILL_SERVICE_TYPE[kind],
                "Bill Entry Type": setup_row["billEntryType"],
                "Bill Invoice Template": INVOICE_TEMPLATE,
                "Remit Address": remit_text,
            },
            "Service Address": address_fields(building["address"]),
            "Account Address": dict(p1["Provider Address"]),
            "Account Contact": dict(p1["Provider Contact"]),
        })

    dump("01-billing-accounts.yaml", """# Stage 2, step 1: Billing Accounts (Database Administrator > Nodes > company node > Utility
# Accountant tab; BillAccountViewModel). One record per account. Section keys are the tab's own
# pages in the order it presents them: Definitions (save first), Service Address, Account
# Address, Account Contact. GL Accounts and Bill Validation Tests belong to Stage 6.
""", {
        "stage": 2, "step": 1, "title": "Billing accounts", "app": "Database Administrator",
        "screen": "Nodes > company node > Utility Accountant tab",
        "source": ["data/scenarios/demo-university-v1.yaml (accounts)",
                   "data/eem/northlake-eem-metaworld-stage1b-v1.yaml (billingAccountKinds, billingAccountSetup)",
                   "data/eem/northlake-bill-entry-v1.yaml (preferredEntry)",
                   "implementation/stage-1-foundation/02-utility-providers.yaml (remit addresses and contacts)"],
        "notes": [
            "Select the company on Nodes, open its Utility Accountant tab, click Add, fill Definitions and save; the other pages unlock after the first save.",
            "Service Address is typed text, not a picker: it repeats the building's street address from 02-sites-and-buildings.yaml, but nothing links the two records.",
            "Account Address and Account Contact are the provider's own business address and Stage 1 contact (AddressAndContactViewModel); the Northlake Thermal Plant account representative is its plant manager, same as Stage 1.",
            "Remit Address is a combo of the provider's remit addresses; every Northlake provider has exactly one, so the combo offers a single choice.",
            "Bill Invoice Template: the stage1b source manifest names a placeholder 'Energy Hippo Default Template'; the seeded BillInvoiceTemplate lookup instead has one row, 'Bill Table Invoice Default' (BillInvoice.trdp). Use the real seeded name.",
            "Currency Unit is assumed USD; nothing in the source model states a currency (Northlake is a US-only synthetic customer).",
            "Bill Service Type is simplified for Stage 2: AP Upload Only for the 40 external utility accounts, No AP Upload for the 6 internal cost centers and 3 PPA agreements. The full AP/GL-driven rule (data/eem/northlake-ap-gl-v1.yaml) needs GL accounts, which are Stage 6; apply it there and it may change some of these.",
            "Bill Entry Type (Global_Status_Code BA2: 0 Bill Entry, 1 Bill Importer, 2 Bill Generation, 3 Bill Allocation, 10 Other) follows the Phase 1 entry plan: Bill Importer for Valley Electric District and River City Utilities, except every Cedar Row Apartments account is Bill Entry regardless of provider (company scope beats the provider default); Bill Entry for Sierra Gas Utility and Helios Onsite Solar; Bill Allocation for the Northlake Thermal Plant.",
            "GL Accounts (default AP and expense accounts) and Bill Validation Tests are Stage 6; leave both at their defaults here.",
            "Status defaults to Active on save; no record below changes it.",
        ],
        "records": account_records,
    }, args.force)

    # ================================================================== 02 sites and buildings
    site_records = []
    for site_id, site in sites.items():
        site_records.append({
            "key": site_id,
            "installed": {"nodeId": INSTALLED_NODE[site_id], "recordedOn": RECORDED},
            "Company": companies[site["ownerCompanyId"]],
            "Definitions": {"Description": site["displayName"], "Time Zone": TIME_ZONE},
            "Node Address": address_fields(site["address"], with_coordinates=True),
        })
    site_records.append({
        "key": "weather_reference",
        "installed": {"nodeId": INSTALLED_NODE["weather_reference"], "recordedOn": RECORDED},
        "Company": companies[weather_company],
        "Definitions": {"Description": "Weather Reference", "Time Zone": TIME_ZONE},
        "Notes": ["A reference grouping for the two weather-station meters (03-meters.yaml); it has no street address of its own."],
    })

    building_records = []
    for building_id, building in buildings.items():
        site = sites[building["siteId"]]
        rec = {
            "key": building_id,
            "installed": {"nodeId": INSTALLED_NODE[building_id], "recordedOn": RECORDED},
            "Company": companies[building["companyId"]],
            "Parent": site["displayName"],
            "Definitions": {"Description": building["displayName"], "Time Zone": TIME_ZONE},
            "Node Address": address_fields(building["address"], with_coordinates=True),
        }
        area = building.get("grossFloorAreaSqft", building.get("parkingAreaSqft"))
        if area is not None:
            rec["Area"] = {"Area Unit": "SqFt", "History": [Flow({"Area": area, "Date": date(2026, 9, 15)})]}  # verified via SELECT against the installed database, not invented
        rec["Keywords"] = [Flow({"Type": "Department", "Attribute": company_department[building["companyId"]]})]
        building_records.append(rec)
    for airport_id, airport_name, node_id in (
        ("sacramento_executive_airport", "Sacramento Executive Airport", INSTALLED_NODE["sacramento_executive_airport"]),
        ("sacramento_international_airport", "Sacramento International Airport", INSTALLED_NODE["sacramento_international_airport"]),
    ):
        building_records.append({
            "key": airport_id,
            "installed": {"nodeId": node_id},
            "Company": companies[weather_company],
            "Parent": "Weather Reference",
            "Definitions": {"Description": airport_name},
            "Notes": ["Created as a Location node under Weather Reference before Stage 2 began, when the airport was modeled as a building instead of a meter. "
                      "Delete it, or keep it as the weather-station meter's parent in 03-meters.yaml; both placements are legal and neither changes a check."],
        })

    dump("02-sites-and-buildings.yaml", """# Stage 2, step 2: Sites and Buildings (Database Administrator > Nodes; Site and Location
# nodes). One record per node. These 4 sites and 13 buildings, plus the two airport nodes noted
# at the end, already exist on the installed instance (see installed: below); this file records
# their expected values, including direct or inherited Keywords.
""", {
        "stage": 2, "step": 2, "title": "Sites and buildings", "app": "Database Administrator", "screen": "Nodes",
        "source": ["data/scenarios/demo-university-v1.yaml (sites, buildings)",
                   "data/eem/northlake-eem-metaworld-stage1b-v1.yaml (weatherIndexTargets, ownershipRules)",
                   "generators/documents/sources/implementation/northlake-address-coordinates.md"],
        "notes": [
            "A site (Level 1) sits at the top of a company's tree; a building (Level 2, Location) sits under its site. Fill Definitions and save, then Node Address, then (buildings only) Area, and verify Keywords.",
            "These nodes, their Node Address and, for the 11 buildings that have a floor area, their Area history already exist on the installed instance; verify the values below rather than retype them, and add any missing Department keyword.",
            "Area is entered on the node's own Area page (Floor Area in SqFt, with an as-of date); Campus Grounds and Cedar Row Carport and Grounds are outdoor service areas with no floor area, so they carry none.",
            "Keywords below describe each building's expected effective value. The Department keyword (catalog type 'Department', already seeded) must have the owning company's department as its attribute, either assigned directly or inherited from the parent site. A correct inherited value satisfies this requirement.",
            "Prefer assigning Department once on the owning site and verifying that each building inherits the expected value. Direct assignments on individual buildings are also valid.",
            "Site Code and Building Code (the level's User Defined Field) have no source value for any node; left blank.",
            "Ownership: a building exists once, in the company that owns its site. The Northlake Thermal Plant company holds only Central Plant; Northlake University owns every campus building including the ones the Thermal Plant serves.",
        ],
        "records": site_records + building_records,
    }, args.force)

    # ================================================================== 03 meters
    meter_records = []
    for meter in meters:
        rec: dict = {"key": meter["id"], "installed": {"meterId": None}}
        rec["Building"] = meter["buildingName"]
        provider_name = providers[meter["providerId"]]["displayName"] if meter.get("providerId") else ""
        # Flow (one-line) mappings render a bare None as an explicit "!!null" tag rather than a
        # clean blank, so optional fields here use "" instead. The account is named by its number,
        # as the meter editor shows it, so the record reads without opening 01-billing-accounts.yaml.
        rec["Meter Definition"] = Flow({
            "Description": meter["displayName"], "Measure Type": meter["measureType"],
            "Meter Number": meter["syntheticMeterNumber"], "Provider Meter Number": meter.get("providerMeterNumber") or "",
            "Meter Multiplier": meter.get("multiplier") or "",
            "Billing Account": accounts[meter["accountId"]]["syntheticAccountNumber"] if meter.get("accountId") else "",
            "Utility Provider": provider_name, "Bill Cycle": meter.get("billCycle") or "",
        })
        meter_records.append(rec)

    dump("03-meters.yaml", """# Stage 2, step 3: Meters (Database Administrator > Nodes > Meter nodes; MeterDefinitionViewModel).
# One record per meter, key = the source model's meter id. Meter Definition is the group of
# fields under the node's own Definitions page. Billing Account and Bill Cycle are blank for
# owned meters and the two weather stations, which carry no provider or account.
""", {
        "stage": 2, "step": 3, "title": "Meters", "app": "Database Administrator", "screen": "Nodes > Meter nodes",
        "source": ["data/scenarios/demo-university-v1.yaml (accounts[].meters, ownedMeters)",
                   "data/eem/northlake-eem-metaworld-stage1b-v1.yaml (meterSetup, weatherIndexTargets)"],
        "notes": [
            "322 meters: 55 utility meters (on a billing account), 265 owned (no billing account, incl. 248 Cedar Row apartment submeters, 124 apartments x electric + water), 2 weather-station meters.",
            "PRODUCT FINDING: the Meter editor (MeterDefinitionViewModel) has no separate Serial Number field. ProviderMeterNumber is bound straight to MeterInfo.SerialNumber and labelled 'Provider Meter Number' on the form; there is one text field for both ideas, not two.",
            "Utility Provider and Bill Cycle are set by choosing the Billing Account first; the account brings its provider with it, and Bill Cycle then lists that provider's cycles for the meter's company.",
            "Meter Number is the customer's own tag (the synthetic meter number below); Provider Meter Number is the provider-formatted number extracted from it, blank for owned and weather-station meters.",
            "Meter Multiplier is blank (defaults to 1) except Science Center Electric Lab Wing (40, current-transformer ratio) and Central Plant Steam Production (10, header pulse value).",
            "The 2 weather-station meters (KSAC, KSMF) carry measure type Weather and sit directly under the Weather Reference site (02-sites-and-buildings.yaml), not under a building.",
            "Status defaults to Active on save; no meter below changes it.",
        ],
        "records": meter_records,
    }, args.force)

    # ================================================================== 04 points
    # AccumulatorDelta channels are modelled in the source data (so a gateway binding can name
    # them), but the product creates that point itself behind the register (howCreated:
    # "Generated by EEM with its register point"); it is not something a person enters, so it is
    # excluded here and captured instead on the register's own installed.deltaPointId.
    point_records = []
    for key, point in points.items():
        if point["pointType"] == "AccumulatorDelta":
            continue
        rec: dict = {"key": key, "installed": {"pointId": None}}
        if point["pointType"] == "Accumulator":
            rec["installed"]["deltaPointId"] = None
        index = "Degree Days" if key in temperature_points else ""
        if key in temperature_points:
            rec["installed"]["hddPointId"] = None
            rec["installed"]["cddPointId"] = None
        # The meter as the tree shows it (Description) and its Meter Number, not its 03-meters.yaml key.
        rec["Meter"] = Flow({"Description": point["meter"]["displayName"], "Meter Number": point["meter"]["syntheticMeterNumber"]})
        rec["Point Definition"] = Flow({
            "Description": point["name"], "Reading Type": point["pointType"], "Measure Type": point["measureType"],
            "Unit": point["unitName"], "Archive Interval": point.get("archiveInterval") or "", "Index": index,
        })
        point_records.append(rec)
    for bl in baseline_records:
        point_records.append({
            "key": bl["key"], "installed": {"pointId": None},
            "Meter": bl["meterKey"],
            "Point Definition": Flow({
                "Description": bl["name"], "Reading Type": "Analog", "Measure Type": bl["measureType"],
                "Unit": bl["unitName"], "Archive Interval": bl.get("archiveInterval") or "", "Index": "",
            }),
        })

    generated_deltas = len(registers)
    generated_hdd_cdd = len(temperature_points) * 2
    entered = len(point_records)

    dump("04-points.yaml", """# Stage 2, step 4: Points (Database Administrator > Nodes > Point nodes; PointDefinitionViewModel).
# One record per point a person enters, key = the source model's channel id (or the baseline
# target's own id for the 3 baseline point shells; see 07). What EEM creates on its own
# (AccumulatorDelta behind every Accumulator, HDD/CDD behind a Degree Days index) is not listed
# as a record; capture its id on the parent's own installed: block instead.
""", {
        "stage": 2, "step": 4, "title": "Points", "app": "Database Administrator", "screen": "Nodes > Point nodes",
        "source": ["data/scenarios/demo-university-v1.yaml (channels)",
                   "data/eem/northlake-eem-metaworld-stage1b-v1.yaml (pointRules, weatherIndexTargets, baselineTargets)"],
        "notes": [
            f"{entered} points to enter here (includes the 3 baseline point shells from Step 7); EEM adds {generated_deltas} AccumulatorDelta points (one per Accumulator/register point above) "
            f"and {generated_hdd_cdd} HDD/CDD points (2 each behind the KSAC and KSMF temperature points) on its own, for {entered + generated_deltas + generated_hdd_cdd} points total.",
            "PRODUCT FINDING: on this 7.0 build, Point_Save creates only the AccumulatorDelta behind a register point, not an AccumulatorROC as well; the stage1b model's 'generatedPointTypes' list (AccumulatorDelta, AccumulatorROC) overstates what the save proc actually does. Do not expect or wait for a rate-of-change point.",
            "Index ('Degree Days') is offered only when Measure Type is Temperature; picking it creates the point's HDD and CDD children (IndexPoints_Save) named '<point> HDD' and '<point> CDD'. It applies to KSAC and KSMF Outside Air Temperature only.",
            "Archive Interval accepts only 1, 5, 10, 15, 30, 60 or 1440 minutes; a route or monthly register read archives nothing, so its Archive Interval is blank.",
            "Time Zone (a Definitions-page field common to every node type, not specific to points) is Pacific for every point, inherited from its building; none needs to change it.",
            "The Baseline group (Baseline Algorithm, Display baseline, Baseline For) on the Point editor is left at its default ([None]) for every point here except the 3 baseline point shells, which Step 7 configures.",
            "A meter whose channels are all bill facts (for example a flat monthly kWh/kW utility meter with no interval data) has no points at all; only meters with at least one non-bill channel appear above.",
        ],
        "records": point_records,
    }, args.force)

    # ================================================================== 05 weather stations
    assignments = model["weatherIndexTargets"]["stationAssignments"]
    station_name = next(s["name"] for s in model["weatherIndexTargets"]["weatherMeters"] if s["stationId"] == assignments["defaultStationId"])
    weather_records = []
    for company_id in companies:
        owned_buildings = [b for b in buildings.values() if b["companyId"] == company_id]
        weather_records.append({
            "key": company_id,
            "Company": companies[company_id],
            "Associate with Selected": [Flow({"Location": b["displayName"], "Station": station_name}) for b in owned_buildings],
        })

    dump("05-weather-stations.yaml", """# Stage 2, step 5: Weather Stations (Database Administrator > Nodes > company node >
# Definitions tab > Weather Stations page; WeatherStationViewModel). One record per company: the
# grid lists that company's Location (building) nodes; set every row's Station combo, tick each
# row and click Associate with Selected once per company.
""", {
        "stage": 2, "step": 5, "title": "Weather stations", "app": "Database Administrator",
        "screen": "Nodes > company node > Definitions tab > Weather Stations page",
        "source": ["data/eem/northlake-eem-metaworld-stage1b-v1.yaml (weatherIndexTargets.stationAssignments)"],
        "notes": [
            "The Station combo lists every level-4 (Meter) node anywhere in the instance whose Meter row carries the Weather measure type; it is not scoped to the company being edited, so a Cedar Row Apartments or Northlake Thermal Plant building can (and here does) point at a Northlake University weather station.",
            "One station per node; the assignment cascades to that node's descendants (its meters and points).",
            "Assign KSAC Sacramento Executive Airport to every one of the 13 buildings in all three companies; there is no exception (weatherIndexTargets.stationAssignments.exceptions is empty).",
            "Buttons stage changes only; Associate with Selected writes the ticked rows (WeatherStationMap_Sync) and the shell's Save/Cancel bar is what actually persists them. Delete Associations (WeatherStationMap_Del) removes a mapping the same way.",
            "The two airport nodes (38, 39) noted in 02-sites-and-buildings.yaml get no station assignment; they are not a company's serviced buildings.",
            "PRODUCT FINDING: the Station combo is not limited to actual weather stations. The source model's measure-type mapping puts indoor_air and weather on the same 'Weather' measure type, so Science Center Lab Environment (an indoor temperature/humidity sensor group, 03-meters.yaml) also appears in the list as a selectable station. Do not pick it.",
        ],
        "records": weather_records,
    }, args.force)

    # ================================================================== 06 aggregates
    aggregate_records = []
    for agg in model["aggregateTargets"]:
        parent = agg["parentPath"].rsplit(" / ", 1)[-1]
        members = list(agg["members"])
        if "memberTemplate" in agg:
            from generators.northlake_packet import fill, unit_numbers
            template = agg["memberTemplate"]
            members += [dict(template, sourceChannelId=fill(template["channelTemplate"], {"unit": unit})) for unit in unit_numbers(buildings[template["perUnitOf"]])]
        member_rows = [Flow({"Meter": points[m["sourceChannelId"]]["meter"]["displayName"],
                             "Meter Number": points[m["sourceChannelId"]]["meter"]["syntheticMeterNumber"],
                             "Point": points[m["sourceChannelId"]]["name"], "Required": m["required"], "Multiplier": m["multiplier"]})
                       for m in members]
        aggregate_records.append({
            "key": agg["id"],
            "installed": {"pointId": None, "aggregateId": None},
            "Create Aggregate Point": {
                "Name": agg["aggregatePointName"], "Parent": parent, "Measure Type": measure_types["byUnit"].get(agg["unit"]) or _measure_from_points(points, members),
                "Unit": rules["unitLabels"].get(agg["unit"], agg["unit"]), "Interval": agg["intervalMinutes"],
            },
            "Members": member_rows,
        })

    dump("06-aggregates.yaml", """# Stage 2, step 6: Aggregates. Two screens: an aggregate point is CREATED from the Nodes tree's
# "Create Aggregate Point" context menu (ordinary point editor fields, gateway is the
# Aggregation Gateway), then its MEMBERS are added on the top-level Aggregates workspace (nav
# item after Nodes): pick the aggregate, use the Add Points drawer, set Required and Multiplier
# per member, then Recalculate.
""", {
        "stage": 2, "step": 6, "title": "Aggregates", "app": "Database Administrator",
        "screen": "Nodes (Create Aggregate Point) and the Aggregates workspace",
        "source": ["data/eem/northlake-eem-metaworld-stage1b-v1.yaml (aggregateTargets)"],
        "notes": [
            "Create Aggregate Point: right-click the parent site or building in the tree, choose Create Aggregate Point, and fill it exactly like an ordinary point (Name, Measure Type, Unit, Interval); the gateway is set to Aggregation automatically.",
            "Members: on the Aggregates workspace, select the aggregate, open Add Points, and pick from the eligible list (same company, time zone, measure type, interval and unit as the aggregate). Set Required and Multiplier per row; Science Center Net Electric kWh has one member at Multiplier -1 and Required unchecked (delivered minus generated, and generation may be offline).",
            "Cedar Row A and B totals use a member template: every apartment's electric submeter in that building, plus the building's own house submeter (Required).",
            "PRODUCT FINDING: Database Administrator writes PointAggregatePoints (the members) only; it never creates the PointAggregates_TBL row, which is reached only from the web API (PointAggregation_Save). An aggregate created here shows ID 0 and 'Last calc: never' in the Aggregates workspace's picker, and Recalculate has nothing to run against. Leave Recalculate From/To blank; there is no interval data in Stage 2 to recalculate from anyway.",
            "7 aggregates: 4 members each for the two campus electric totals, 2 for the campus solar total, 2 for the campus chilled-water total, 2 for Science Center Net Electric, 61 for Cedar Row A (60 apartments + house), 65 for Cedar Row B (64 apartments + house).",
        ],
        "records": aggregate_records,
    }, args.force)

    # ================================================================== 07 baselines
    baseline_yaml_records = []
    for bl in baseline_records:
        baseline_yaml_records.append({
            "key": bl["key"],
            "installed": {"pointId": None},
            "Point": bl["key"],
            "Baseline": Flow({"Baseline Algorithm": BASELINE_ALGORITHM, "Display baseline": True, "Baseline For": bl["measuredKey"]}),
        })

    dump("07-baselines.yaml", """# Stage 2, step 7: Baselines. The 3 baseline point shells from baselineTargets are created as
# ordinary points in 04-points.yaml (same company, measure type, unit and interval as the point
# they baseline); this step is the Baseline group on THAT point's own Definitions page.
""", {
        "stage": 2, "step": 7, "title": "Baselines", "app": "Database Administrator", "screen": "Nodes > Point nodes (Baseline group)",
        "source": ["data/eem/northlake-eem-metaworld-stage1b-v1.yaml (baselineTargets)"],
        "notes": [
            "Open the baseline point (already created in 04-points.yaml), set Baseline Algorithm, tick Display baseline, then choose Baseline For: the measured point this one baselines (the combo is scoped by the chosen algorithm, via BaselinePoints_Lookup).",
            "Baseline Algorithm is assumed 'Rolling Day Type Forecast' (curBaselineCalcID 7): the only non-curtailment, data-creating algorithm already seeded in the instance's curBaselineCalc table. Nothing in the source model names a specific algorithm.",
            "PRODUCT FINDING: curBaselineCalc (the Baseline Algorithm list) has no editor in any client; every row is database-only configuration. If a customer needs a new algorithm, it has to be added directly in the database, not through the UI.",
            "The Baseline group is hidden entirely when the user preference HidePointBaselineSettings is on; turn it off first if it does not appear.",
            "The 3 targets: Science Center Electric kWh Baseline (for the Science Center 15-minute delivered kWh point), Student Center Demand kW Baseline (for the Student Center 15-minute demand point), Science Center Chilled Water Ton-Hours Baseline (for the Science Center hourly chilled-water delivery point).",
        ],
        "records": baseline_yaml_records,
    }, args.force)

    print()
    print(f"companies={len(companies)} sites={len(sites)} buildings={len(buildings)} accounts={len(accounts)} meters={len(meters)}")
    print(f"points entered={entered} (incl. {len(baseline_records)} baseline shells), generated deltas={generated_deltas}, generated HDD/CDD={generated_hdd_cdd}, total={entered + generated_deltas + generated_hdd_cdd}")


def _measure_from_points(points: dict, members: list) -> str:
    return points[members[0]["sourceChannelId"]]["measureType"]


if __name__ == "__main__":
    main()
