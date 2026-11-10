"""Stage 2 (Hierarchy) output checks: the seven YAML files parse and cross-reference cleanly.

These are checks on implementation/stage-2-hierarchy/*.yaml as committed, not on
generators/stage2_hierarchy.py's logic in isolation (the YAML has been hand-maintained since
that one-time generation), so they also guard the corrections made against the installed EEM:
measure-type and unit names as the editors show them, register points with a usage unit and an
archive interval the editor offers, and the billing-account variety.

A note on the point totals: generators.northlake_packet.build_packet()'s own
packet["counts"] reports 431 points (299 to enter, "264" generated), but that count is a
report-table artifact of the intake packet, not the Stage 2 target: it has no notion of the 3
baseline point shells, the activity index or the custom-unit points, and its "264 generated"
doubles every register for a phantom AccumulatorROC point that Point_Save does not actually
create on this build. Stage 2's real total is 474 entered + 203 generated (197 AccumulatorDelta
+ 6 HDD/CDD) = 677, including 18 hourly forecast points and the 73 handheld-route points added on
2026-11-07. The baselines themselves are configured in Stage 3.
"""

import re
import unittest
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2] / "implementation" / "stage-2-hierarchy"
STAGE3 = ROOT.parent / "stage-3-gateways-and-data"

# MeasureType names including the weather measurement catalog upgrade; there is no measure-type editor.
EEM_MEASURE_TYPES = {"Electricity", "Potable Water", "Sewer Water", "Natural Gas", "Steam", "Chilled Water", "Hot Water",
                     "Weather", "Sensor", "Temperature", "Relative Humidity", "Pressure", "Digital", "Activity Level",
                     "Dew Point", "Wind Speed", "Wind Direction", "Precipitation Probability", "Time", "Fuel Oil #2"}
ARCHIVE_INTERVALS = {1, 5, 10, 15, 30, 60, 1440}  # the Point editor's closed list; it has no blank


def load(name, folder=ROOT):
    return yaml.safe_load((folder / name).read_text(encoding="utf-8"))


class Stage2HierarchyFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = {name: load(name) for name in (
            "00-units.yaml", "01-billing-accounts.yaml", "02-sites-and-buildings.yaml", "03-meters.yaml",
            "04-points.yaml", "05-weather-stations.yaml", "06-aggregates.yaml",
        )}
        cls.units = cls.files["00-units.yaml"]["records"]
        cls.accounts = cls.files["01-billing-accounts.yaml"]["records"]
        cls.sites_and_buildings = cls.files["02-sites-and-buildings.yaml"]["records"]
        cls.meters = cls.files["03-meters.yaml"]["records"]
        cls.points = cls.files["04-points.yaml"]["records"]
        cls.weather = cls.files["05-weather-stations.yaml"]["records"]
        cls.aggregates = cls.files["06-aggregates.yaml"]["records"]
        cls.baselines = load("06-baselines.yaml", STAGE3)["records"]
        # Points, aggregate members and baselines name a meter by Meter Number (and Description), a point by its Description.
        cls.meter_by_number = {r["Meter Definition"]["Meter Number"]: r for r in cls.meters}
        cls.point_by_meter = {(r["Meter"]["Meter Number"], r["Point Definition"]["Description"]): r for r in cls.points if "Meter" in r}

    # ---------------------------------------------------------------- shape
    def test_files_parse_with_the_stage_convention_shape(self):
        for name, doc in self.files.items():
            self.assertEqual(2, doc["stage"], name)
            self.assertIn("step", doc, name)
            self.assertIn("title", doc, name)
            self.assertIn("app", doc, name)
            self.assertIn("screen", doc, name)
            self.assertIsInstance(doc["source"], list, name)
            self.assertIsInstance(doc["notes"], list, name)
            self.assertTrue(doc["notes"], name)
            self.assertIsInstance(doc["records"], list, name)
            self.assertTrue(doc["records"], name)
            keys = [r["key"] for r in doc["records"]]
            self.assertEqual(len(keys), len(set(keys)), f"duplicate key in {name}")

    def test_checks_sql_exists_and_is_read_only(self):
        for folder in (ROOT, ROOT.parent / "stage-1-foundation"):
            with self.subTest(stage=folder.name):
                text = (folder / "checks.sql").read_text(encoding="utf-8")
                self.assertIn("SET NOCOUNT ON", text)
                # Ignore embedded recipe text; permit only checker-owned session-local tables.
                text = re.sub(r"N?'(?:''|[^'])*'", "''", text)
                text = re.sub(r"DROP TABLE IF EXISTS #StageCheckExpected,#StageCheckActual,#StageCheckAdditional,#StageCheckIssues;", "", text)
                for verb in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "TRUNCATE ", "MERGE ", "EXEC ", "EXECUTE ", "CREATE ", "ALTER "):
                    self.assertNotIn(verb, text.upper())
                for target in re.findall(r"\bINTO\s+(\S+)", text, re.IGNORECASE):
                    self.assertIn(target, {"#StageCheckExpected", "#StageCheckActual", "#StageCheckAdditional", "#StageCheckIssues"})

    def test_checker_expectations_match_the_yaml(self):
        from generators.stage_check_data import BEGIN, END, render_data

        for number, folder in ((1, ROOT.parent / "stage-1-foundation"), (2, ROOT)):
            with self.subTest(stage=folder.name):
                text = (folder / "checks.sql").read_text(encoding="utf-8")
                self.assertEqual(render_data(number), text[text.index(BEGIN):text.index(END) + len(END)])

    # ---------------------------------------------------------------- counts
    def test_51_billing_accounts(self):
        self.assertEqual(51, len(self.accounts))
        by_kind = {"externalUtilityAccounts": 0, "internalCostCenters": 0, "ppaAgreements": 0, "generationTransfers": 0}
        for r in self.accounts:
            provider = r["Definitions"]["Utility Provider"]
            if provider == "Northlake Thermal Plant":
                by_kind["internalCostCenters"] += 1
            elif provider == "Helios Onsite Solar":
                by_kind["ppaAgreements"] += 1
            elif provider == "Ridgeline Wind":
                by_kind["generationTransfers"] += 1
            else:
                by_kind["externalUtilityAccounts"] += 1
        self.assertEqual({"externalUtilityAccounts": 41, "internalCostCenters": 6, "ppaAgreements": 3, "generationTransfers": 1}, by_kind)

    def test_390_meters(self):
        self.assertEqual(390, len(self.meters))
        with_account = sum(1 for r in self.meters if r["Meter Definition"]["Billing Account"])
        self.assertEqual(67, with_account)                     # ten turbines, the farm transfer meter and the interconnection meter included
        self.assertEqual(323, len(self.meters) - with_account)  # 320 owned (the met mast and the 54 handheld-route meters included) + 3 weather stations

    def test_the_transfer_statement_is_priced_on_one_billing_meter(self):
        billing = next(r for r in self.meters if r["key"] == "rwl_farm_transfer")
        self.assertEqual(("SYN-RWL-G-0000001", ""), (billing["Meter Definition"]["Billing Account"], billing["Meter Definition"]["Provider Meter Number"]))
        number = billing["Meter Definition"]["Meter Number"]
        self.assertFalse(any(r.get("Meter", {}).get("Meter Number") == number for r in self.points))   # its only point is the aggregate
        farm = next(r for r in self.aggregates if r["key"] == "agg_ntp_ridgeline_generated_kwh_10m")
        self.assertEqual("Ridgeline Farm Transfer Meter", farm["Create Aggregate Point"]["Parent"])
        self.assertEqual({f"ch_rwl_wtg{n:02d}_kwh_10m" for n in range(1, 11)},
                         {self.point_by_meter[(m["Meter Number"], m["Point"])]["key"] for m in farm["Members"]})

    def test_points_to_enter_plus_generated_is_677(self):
        entered = len(self.points)
        self.assertEqual(474, entered)  # includes 18 hourly forecast points, 12 observations, three baseline shells and 73 handheld-route points

        generated_deltas = sum(1 for r in self.points if r["Point Definition"]["Reading Type"] == "Accumulator")
        self.assertEqual(197, generated_deltas)  # one AccumulatorDelta per register, real Point_Save behaviour

        generated_hdd_cdd = sum(1 for r in self.points if r["Point Definition"].get("Index") == "Degree Days") * 2
        self.assertEqual(6, generated_hdd_cdd)  # HDD + CDD behind each of the 3 station temperature points

        self.assertEqual(677, entered + generated_deltas + generated_hdd_cdd)

    def test_every_meter_multiplier_has_a_point_to_act_on(self):
        with_points = {r["Meter"]["Meter Number"] for r in self.points if "Meter" in r}
        idle = [r["Meter Definition"]["Description"] for r in self.meters
                if r["Meter Definition"]["Meter Multiplier"] not in ("", None) and r["Meter Definition"]["Meter Number"] not in with_points]
        self.assertEqual([], idle)

    def test_11_aggregates_here_and_3_baselines_in_stage_3(self):
        self.assertEqual(11, len(self.aggregates))
        self.assertEqual(3, len(self.baselines))
        member_counts = sorted(len(r["Members"]) for r in self.aggregates)
        self.assertEqual([2, 2, 2, 2, 4, 4, 10, 10, 10, 61, 65], member_counts)
        self.assertEqual({"Rolling Day Type Forecast", "Average of Top 5 Days"},
                         {r["Baseline"]["Baseline Algorithm"] for r in self.baselines})

    def test_16_buildings_get_a_weather_station_assignment(self):
        rows = {row["Location"]: row["Station"] for r in self.weather for row in r["Associate with Selected"]}
        self.assertEqual(16, len(rows))
        cedar_row = {"Cedar Row A", "Cedar Row B", "Cedar Row C", "Cedar Row Common House", "Cedar Row Carport and Grounds"}
        ridgeline = {"Ridgeline Turbine Field", "Ridgeline Substation"}
        for location, station in rows.items():
            expected = ("KSMF Sacramento International Airport" if location in cedar_row
                        else "KSUU Travis Air Force Base" if location in ridgeline else "KSAC Sacramento Executive Airport")
            self.assertEqual(expected, station, location)

    def test_ridgeline_turbines_carry_the_same_six_points(self):
        turbines = [r["key"] for r in self.meters if r["key"].startswith("rwl_wtg_")]
        self.assertEqual(10, len(turbines))
        by_meter = {}
        for r in self.points:
            by_meter.setdefault(r.get("Meter", {}).get("Meter Number"), []).append(r["Point Definition"])
        numbers = {r["key"]: r["Meter Definition"]["Meter Number"] for r in self.meters}
        for meter in turbines:
            with self.subTest(meter=meter):
                points = by_meter[numbers[meter]]
                self.assertEqual(["Generated kWh 10m", "Active Power kW 10m", "Possible kW 10m", "Nacelle Wind Speed 10m", "Rotor Speed 10m", "Turbine State"],
                                 [d["Description"] for d in points])
                self.assertEqual({10}, {d["Archive Interval"] for d in points})
                self.assertEqual("Digital", points[-1]["Reading Type"])
        keywords = {r["key"]: {k["Type"]: k["Attribute"] for k in r.get("Keywords", [])} for r in self.meters}
        self.assertEqual(["Wind"] * 10 + ["Solar"] * 3, [keywords[m].get("Generation Source") for m in turbines]
                         + [keywords[m].get("Generation Source") for m in ("hos_science_center_array", "hos_student_center_array", "hos_cedar_row_carport")])

    # ---------------------------------------------------------------- names and values the editors accept
    def test_measure_types_are_eem_names(self):
        used = {r["Meter Definition"]["Measure Type"] for r in self.meters}
        used |= {r["Point Definition"]["Measure Type"] for r in self.points}
        used |= {r["Create Aggregate Point"]["Measure Type"] for r in self.aggregates}
        self.assertEqual(set(), used - EEM_MEASURE_TYPES)

    def test_units_are_written_as_the_units_list_shows_them(self):
        units = [r["Point Definition"]["Unit"] for r in self.points] + [r["Create Aggregate Point"]["Unit"] for r in self.aggregates]
        self.assertEqual([], [unit for unit in units if not re.fullmatch(r".+ - \(.+\)", unit)])

    def test_archive_intervals_are_the_editors_values_and_all_are_used(self):
        intervals = {r["Point Definition"]["Archive Interval"] for r in self.points}
        self.assertEqual(ARCHIVE_INTERVALS, intervals)

    def test_register_points_carry_their_usage_unit(self):
        registers = [r["Point Definition"] for r in self.points if r["Point Definition"]["Reading Type"] == "Accumulator"]
        self.assertEqual([], [d for d in registers if d["Unit"].startswith("Reading") or d["Archive Interval"] != 1440])

    def test_every_register_unit_is_one_point_save_takes_for_an_accumulator(self):
        # Point_Save creates a new Accumulator only in an Energy or Volume unit (classes 3 and 7) or a unit with a rate
        # unit; anything else throws hierarchy.node.point-unit.invalid and the Stage 2 import rolls the sheet back (the
        # generators' run hours in Hour did, 2026-11-09). These are the units in use, each checked against Northlake's
        # catalog: add a new one here only after checking its class and rate unit there.
        accepted = {"KilowattHours - (kWh)", "KiloVoltAmpereHours - (kVAh)", "KiloVoltAmpereReactiveHours - (kVArh)",
                    "Therm - (Therm)", "Fuel Oil#2 Gallon - (gal)", "Gallons - (gal)", "Hundreds of Cubic Feet - (ccf)",
                    "Thousands of Gallons - (kgal)"}
        registers = [r for r in self.points if r["Point Definition"]["Reading Type"] == "Accumulator"]
        self.assertEqual([], [r["key"] for r in registers if r["Point Definition"]["Unit"] not in accepted])

    def test_custom_units_are_created_in_step_0(self):
        created = {f'{r["Definitions"]["Unit Name"]} - ({r["Definitions"]["Label"]})' for r in self.units}
        for unit in ("Miles per Hour - (mph)", "Kilometers per Hour - (km/h)", "Watts per Square Meter - (W/m2)",
                     "PSIG - (PSIG)", "Events - (events)", "Knots - (kn)", "Meters per Second - (m/s)",
                     "Degrees - (°)", "Kilogram per cubic meter - (kg/m3)", "Power Factor - (PF)"):
            with self.subTest(unit=unit):
                self.assertIn(unit, created)
                self.assertTrue(any(r["Point Definition"]["Unit"] == unit for r in self.points), unit)

    def test_billing_accounts_use_every_supported_value_a_campus_uses(self):
        definitions = [r["Definitions"] for r in self.accounts]
        self.assertEqual({"Bill Importer", "Bill Entry", "Bill Allocation", "Bill Generation"}, {d["Bill Entry Type"] for d in definitions})
        self.assertEqual({"AP Upload Only", "No AP Upload", "Bill Payment"}, {d["Bill Service Type"] for d in definitions})
        self.assertEqual({"Bill Table Invoice Default", "Billing Charges Report"}, {d["Bill Invoice Template"] for d in definitions})
        self.assertEqual({"US Dollar"}, {d["Currency Unit"] for d in definitions})
        self.assertEqual(2, sum(1 for d in definitions if d.get("Previous Account Number")))  # a renewal and an acquisition
        self.assertEqual(1, sum(1 for r in self.accounts if "Account Contact" not in r))
        acquired = {"ved_ridgeline_generator", "rwl_ridgeline_transfer"}   # opened with the 2024-07-01 acquisition
        for r in self.accounts:
            with self.subTest(account=r["key"]):
                start = date(2024, 7, 1) if r["key"] in acquired else date(2024, 1, 1)
                self.assertIn({"Status": "Active Billing Account", "As of Date": start}, r["Status"])
                self.assertIsNotNone(r["Service Address"].get("Latitude"))

    # ---------------------------------------------------------------- cross-references
    def test_every_points_parent_exists(self):
        places = {r["Definitions"]["Description"] for r in self.sites_and_buildings}
        missing = [r["key"] for r in self.points
                   if ("Meter" in r) == ("Parent" in r) or ("Meter" in r and r["Meter"]["Meter Number"] not in self.meter_by_number)
                   or r.get("Parent", "") not in places | {""}]
        self.assertEqual([], missing)

    def test_every_utility_meters_billing_account_number_exists(self):
        account_numbers = {r["Definitions"]["Account Number"] for r in self.accounts}
        missing = [r["key"] for r in self.meters if r["Meter Definition"]["Billing Account"]
                   and r["Meter Definition"]["Billing Account"] not in account_numbers]
        self.assertEqual([], missing)

    def test_every_meter_reference_names_a_real_meter(self):
        references = [(r["key"], r["Meter"]) for r in self.points if "Meter" in r]
        references += [(r["key"], {"Meter Number": m["Meter Number"], "Description": m["Meter"]}) for r in self.aggregates for m in r["Members"]]
        references += [(r["key"], r["Meter"]) for r in self.baselines]
        wrong = [(key, ref) for key, ref in references if ref["Meter Number"] not in self.meter_by_number
                 or self.meter_by_number[ref["Meter Number"]]["Meter Definition"]["Description"] != ref["Description"]]
        self.assertEqual([], wrong)

    def test_every_aggregate_member_is_a_point_under_its_meter(self):
        missing = [(r["key"], m["Meter Number"], m["Point"]) for r in self.aggregates for m in r["Members"]
                   if (m["Meter Number"], m["Point"]) not in self.point_by_meter]
        self.assertEqual([], missing)

    def test_every_baseline_targets_a_real_point_and_shell_under_the_same_meter(self):
        for r in self.baselines:
            # BaselinePoints_Lookup offers only siblings, so the shell and its measured point share the named meter.
            number = r["Meter"]["Meter Number"]
            self.assertIn((number, r["Point"]), self.point_by_meter, r["key"])
            self.assertIn((number, r["Baseline"]["Baseline For"]), self.point_by_meter, r["key"])
            self.assertNotEqual(r["Point"], r["Baseline"]["Baseline For"], r["key"])
            self.assertEqual(r["key"], self.point_by_meter[(number, r["Point"])]["key"])

    def test_installed_node_ids_from_the_survey_are_recorded(self):
        installed = {r["key"]: r["installed"]["nodeId"] for r in self.sites_and_buildings}
        expected = {
            "northlake_main_campus": 22, "admin_hall": 23, "science_center": 24, "library": 25,
            "student_center": 26, "lakeview_hall": 27, "recreation_center": 28, "parking_structure": 29,
            "campus_grounds": 34, "weather_reference": 33,
            "sacramento_executive_airport": 38, "sacramento_international_airport": 39,
            "cedar_row_apartments": 8, "cedar_row_a": 9, "cedar_row_b": 10,
            "cedar_row_common_house": 11, "cedar_row_carport_grounds": 35,
            "northlake_central_plant": 31, "central_plant": 32,
            "ridgeline_wind_site": None, "ridgeline_turbine_field": None, "ridgeline_substation": None,  # new, to enter
            "cedar_row_c": None,  # new 2026-11-07, to enter
        }
        self.assertEqual(expected, installed)


if __name__ == "__main__":
    unittest.main()
