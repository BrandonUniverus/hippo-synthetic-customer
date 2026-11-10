"""Protect the HMR meter identities, format limits and generated check data."""
import collections
import copy
import csv
import io
import unittest

import yaml

from generators.stage_check_data import (
    ROOT, UniqueLoader, HANDHELD_BEGIN, HANDHELD_END, HANDHELD_PASTE, HANDHELD_PASTE_COLUMNS,
    HANDHELD_OPERATIONS_BEGIN, HANDHELD_OPERATIONS_END, handheld_expectations, render_handheld,
    render_handheld_operations, render_handheld_paste, render_handheld_starting_readings,
)

CEDAR_ROW_B_TEXT = "Cedar Row B water submeter. Confirm the unit on the meter before reading."


class HandheldRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT / "implementation/stage-3-gateways-and-data"
        cls.gateways = yaml.load((cls.folder / "02-gateways.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
        cls.recipe = yaml.load((cls.folder / "05-handheld-routes.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
        cls.points = yaml.load((ROOT / "implementation/stage-2-hierarchy/04-points.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
        cls.rows = handheld_expectations(cls.gateways, cls.recipe, cls.points)["meters"]

    def record(self, recipe, key):
        return next(r for r in recipe["records"] if r["key"] == key)

    def registers(self, meter_number):
        return {r["Prompt"]: r for r in self.rows if r["MeterNumber"] == meter_number}

    def test_every_route_meter_has_unique_registers_and_one_route_position(self):
        data = handheld_expectations(self.gateways, self.recipe, self.points)
        meters = {(r["Company"], r["MeterNumber"]): (r["Cycle"], r["Route"], r["Sequence"]) for r in self.rows}
        self.assertEqual(204, len(self.rows))
        self.assertEqual(192, len(meters))
        self.assertEqual(192, len(set(meters.values())))
        self.assertEqual(9, len(data["readTypes"]))
        self.assertEqual({("01", "CHECK"): 2, ("01", "SCGAS"): 1, ("02", "CRAWTR"): 61, ("02", "CRBMW"): 1,
                          ("02", "CRBWTR"): 65, ("02", "CRCWTR"): 49, ("03", "DEDUCT"): 4, ("03", "SWGR"): 1,
                          ("04", "IRRIG"): 4, ("05", "GEN"): 3, ("20", "CRCWTR"): 1},
                         dict(collections.Counter(position[:2] for position in meters.values())))
        by_number = {r["MeterNumber"]: r for r in self.rows}
        self.assertEqual(10, by_number["SYN-SUB-W-AH"]["Sequence"])
        self.assertEqual(20, by_number["SYN-SUB-W-A101"]["Sequence"])
        self.assertEqual(610, by_number["SYN-SUB-W-A320"]["Sequence"])
        self.assertEqual(650, by_number["SYN-SUB-W-B416"]["Sequence"])
        self.assertEqual(("03", "DEDUCT", 40), tuple(by_number["SYN-DED-W-CH01"][k] for k in ("Cycle", "Route", "Sequence")))

    def test_cedar_row_c_keeps_the_installers_mistakes(self):
        c = {r["MeterNumber"]: r for r in self.rows if r["MeterNumber"].startswith("SYN-SUB-W-C")}
        self.assertEqual(50, len(c))
        # Floor by floor from the top, in unit order; the house and laundry last.
        self.assertEqual([("SYN-SUB-W-C401", 10), ("SYN-SUB-W-C301", 130), ("SYN-SUB-W-C201", 250), ("SYN-SUB-W-C101", 370),
                          ("SYN-SUB-W-CH", 490), ("SYN-SUB-W-CL", 500)],
                         [(n, c[n]["Sequence"]) for n in ("SYN-SUB-W-C401", "SYN-SUB-W-C301", "SYN-SUB-W-C201",
                                                         "SYN-SUB-W-C101", "SYN-SUB-W-CH", "SYN-SUB-W-CL")])
        self.assertEqual(("20", "CRCWTR", 120), tuple(c["SYN-SUB-W-C412"][k] for k in ("Cycle", "Route", "Sequence")))
        self.assertEqual(["SYN-SUB-W-CL"], [n for n, r in c.items() if not r["Active"]])
        # Two meter batches on one route: ccf upstairs, gallons downstairs.
        self.assertEqual({("CCF", "Hundreds of Cubic Feet - (ccf)", "Northlake Keyed Water 6D CCF"): 24,
                          ("GAL", "Gallons - (gal)", "Northlake Keyed Water 8D Gallons"): 26},
                         dict(collections.Counter((r["Prompt"], r["UsageUnit"], r["ReadType"]) for r in c.values())))
        self.assertEqual({CEDAR_ROW_B_TEXT}, {r["MeterText"] for r in c.values()})
        self.assertEqual({"2025-09-01"}, {r["StartingDate"] for r in c.values()})

    def test_multi_register_meters_and_demand_reads(self):
        switchgear = self.registers("SYN-SUB-E-CPSWGR")
        self.assertEqual({"KWH", "KWHP", "KWHM", "KWHO", "KVRH", "KVAH", "KW", "KWP", "KVA", "PF"}, set(switchgear))
        self.assertEqual(list(range(1, 11)), sorted(r["Channel"] for r in switchgear.values()))
        demand = {p: r for p, r in switchgear.items() if r["ReadingDescription"] is None}
        self.assertEqual({"KW", "KWP", "KVA", "PF"}, set(demand))
        self.assertEqual({None}, {r["StartingReading"] for r in demand.values()})
        self.assertEqual(("Power Factor at Max Demand", "Power Factor - (PF)", "ch_swgr_power_factor"),
                         (demand["PF"]["UsageDescription"], demand["PF"]["UsageUnit"], demand["PF"]["UsageChannel"]))
        self.assertEqual("kVArh Register Delta", switchgear["KVRH"]["UsageDescription"])
        self.assertEqual(switchgear["KWH"]["StartingReading"],
                         sum(switchgear[p]["StartingReading"] for p in ("KWHP", "KWHM", "KWHO")))
        for number in ("SYN-GEN-LIB01", "SYN-GEN-SCI01", "SYN-GEN-CP01"):
            with self.subTest(generator=number):
                generator = self.registers(number)
                self.assertEqual({"RUN": "Hour - (hr)", "FUEL": "Fuel Oil#2 Gallon - (gal)"},
                                 {p: r["UsageUnit"] for p, r in generator.items()})
                # Hour cannot be an Accumulator's unit, so run hours are an Analog register with its own usage point.
                self.assertEqual(("Analog", "Run Hours Register", "Run Hours"),
                                 (generator["RUN"]["RegisterKind"], generator["RUN"]["ReadingDescription"], generator["RUN"]["UsageDescription"]))
                self.assertEqual(("Accumulator", "Fuel Register Delta"), (generator["FUEL"]["RegisterKind"], generator["FUEL"]["UsageDescription"]))
        self.assertEqual({"Accumulator": 197, "Analog": 3, "Demand": 4}, dict(collections.Counter(r["RegisterKind"] for r in self.rows)))
        self.assertEqual(40, self.registers("SYN-VED-M-0040007")["KWH"]["Constant"])
        self.assertEqual(3.0367, self.registers("SYN-SGU-M-0050010")["CCF"]["Constant"])

    def test_starting_readings_follow_each_route_and_fit_the_dials(self):
        by_number = {r["MeterNumber"]: r for r in self.rows}
        self.assertEqual(12000, by_number["SYN-RCU-M-0060004"]["StartingReading"])
        self.assertEqual(1000, by_number["SYN-SGU-M-0050004"]["StartingReading"])
        self.assertEqual((1010, 1610), (by_number["SYN-SUB-W-AH"]["StartingReading"], by_number["SYN-SUB-W-A320"]["StartingReading"]))
        self.assertEqual((1620, 2260), (by_number["SYN-SUB-W-BH"]["StartingReading"], by_number["SYN-SUB-W-B416"]["StartingReading"]))
        self.assertEqual("2024-01-01", by_number["SYN-DED-W-SC01"]["StartingDate"])
        recipe = copy.deepcopy(self.recipe)
        recipe["records"][1]["Starting reading"] = 1000000
        with self.assertRaisesRegex(ValueError, "fit the read type's dials"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe["records"][1]["Starting reading"] = {"First": 1}
        with self.assertRaisesRegex(ValueError, "whole number or First and Step"):
            handheld_expectations(self.gateways, recipe, self.points)

    def test_starting_reading_files_follow_the_starting_readings_grid(self):
        files = render_handheld_starting_readings()
        self.assertEqual({"05-handheld-starting-readings-2024-01-01.txt": 150, "05-handheld-starting-readings-2025-09-01.txt": 50},
                         {name: len(text.splitlines()) for name, text in files.items()})
        cedar_row_c = files["05-handheld-starting-readings-2025-09-01.txt"].splitlines()
        self.assertEqual(["2", "12", "14"], [cedar_row_c[0], cedar_row_c[10], cedar_row_c[11]])  # 401, 411, then 301
        self.assertEqual(["160", "165", "13"], cedar_row_c[-3:])  # house, laundry, then unit 412 on cycle 20
        first = files["05-handheld-starting-readings-2024-01-01.txt"].splitlines()
        self.assertEqual(["48210", "15320", "1000"], first[:3])  # cycle 01: route CHECK before SCGAS

    def test_paste_rows_follow_the_setup_grid_order(self):
        rows = list(csv.reader(io.StringIO(render_handheld_paste())))
        self.assertEqual(list(HANDHELD_PASTE_COLUMNS), rows[0])
        self.assertEqual(205, len(rows))
        self.assertEqual(["SYN-VED-M-0040007", "01", "CHECK"], [rows[1][0], rows[1][2], rows[1][3]])
        self.assertEqual(["SYN-SUB-W-C412", "20", "CRCWTR"], [rows[-1][0], rows[-1][2], rows[-1][3]])
        order = [(row[2], row[3], int(row[4]), row[8]) for row in rows[1:]]
        self.assertEqual(sorted(order), order)
        # Columns by name: the paste gained High Warning and Low Warning on 2026-11-09, which moved the ones after them.
        column = {name: index for index, name in enumerate(rows[0])}
        demand = [row for row in rows[1:] if row[column["Reading Point"]] == ""]
        self.assertEqual(4, len(demand))
        self.assertEqual({("", "")}, {(row[column["Starting Reading"]], row[column["Starting Date"]]) for row in demand})
        # Cedar Row C's 50 registers and the power factor read carry no warnings; a Low of 0 is written, not left empty.
        self.assertEqual(51, len([row for row in rows[1:] if row[column["High Warning"]] == ""]))
        self.assertEqual(10, len([row for row in rows[1:] if row[column["Low Warning"]] == "0"]))

    def test_legacy_oversized_cycle_and_route_fail_before_sql_generation(self):
        for field, value in (("Cycle", "RCU-2"), ("Route Number", "CRB-WATER-01"), ("Cycle", "99")):
            with self.subTest(field=field, value=value):
                recipe = copy.deepcopy(self.recipe)
                recipe["records"][0]["HMR_Meter"][field] = value
                with self.assertRaisesRegex(ValueError, "cycle, route or sequence"):
                    handheld_expectations(self.gateways, recipe, self.points)

    def test_meter_text_the_setup_page_would_change_is_rejected(self):
        for value in ("Read the dial; then the totalizer.", "Main, then side", "Unit (C) 412", "North/South bank"):
            with self.subTest(value=value):
                recipe = copy.deepcopy(self.recipe)
                recipe["records"][0]["HMR_Meter"]["Meter Text"] = value
                with self.assertRaisesRegex(ValueError, "saves as _"):
                    handheld_expectations(self.gateways, recipe, self.points)

    def test_missing_channel_and_non_accumulator_mapping_are_rejected(self):
        for value in (None, 0, 100):
            with self.subTest(channel=value):
                recipe = copy.deepcopy(self.recipe)
                recipe["records"][0]["HMR_Reading"]["Channel"] = value
                with self.assertRaisesRegex(ValueError, "Invalid handheld channel"):
                    handheld_expectations(self.gateways, recipe, self.points)
        points = copy.deepcopy(self.points)
        next(r for r in points["records"] if r["key"] == "ch_rcu_cedar_row_b_water_register")["Point Definition"]["Reading Type"] = "Analog"
        with self.assertRaisesRegex(ValueError, "existing accumulator"):
            handheld_expectations(self.gateways, self.recipe, points)

    def test_meter_points_must_be_the_stage_two_register_and_its_delta(self):
        for field, value in (("Reading Point", "unrelated reading"), ("Consumption Point", "Register Reading")):
            recipe = copy.deepcopy(self.recipe)
            recipe["records"][0]["Meters"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "register and its delta"):
                handheld_expectations(self.gateways, recipe, self.points)

    def test_register_and_demand_rules_are_enforced(self):
        def switchgear(recipe):
            return self.record(recipe, "hmr_central_plant_switchgear")["Meters"][0]["Registers"]

        recipe = copy.deepcopy(self.recipe)
        switchgear(recipe)[0]["Read Type"] = "demand_keyed"
        with self.assertRaisesRegex(ValueError, "non-demand read type"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe = copy.deepcopy(self.recipe)
        switchgear(recipe)[6]["Read Type"] = "electric_keyed"
        with self.assertRaisesRegex(ValueError, "demand read with no starting value"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe = copy.deepcopy(self.recipe)
        switchgear(recipe)[6]["Starting reading"] = 900
        with self.assertRaisesRegex(ValueError, "demand read with no starting value"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe = copy.deepcopy(self.recipe)
        switchgear(recipe)[1]["Text Prompt"] = "kwh"
        with self.assertRaisesRegex(ValueError, "used once per meter"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe = copy.deepcopy(self.recipe)
        switchgear(recipe)[7]["usageChannel"] = "ch_swgr_max_demand_kw"
        switchgear(recipe)[7]["Consumption Point"] = "Max Demand kW"
        with self.assertRaisesRegex(ValueError, "serves one register"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe = copy.deepcopy(self.recipe)
        self.record(recipe, "hmr_cedar_row_c_upper_floors")["Meters"][1]["HMR_Meter"] = {"First Read Sequence": 5}
        with self.assertRaisesRegex(ValueError, "only its route fields"):
            handheld_expectations(self.gateways, recipe, self.points)
        # An Analog register needs a separate Analog usage point on its own meter.
        recipe = copy.deepcopy(self.recipe)
        run_hours = self.record(recipe, "hmr_emergency_generators")["Meters"][0]["Registers"][0]
        run_hours["usageChannel"], run_hours["Consumption Point"] = run_hours["relatedReadingChannel"], "Run Hours Register"
        with self.assertRaisesRegex(ValueError, "its own Analog usage point"):
            handheld_expectations(self.gateways, recipe, self.points)
        points = copy.deepcopy(self.points)
        next(r for r in points["records"] if r["key"] == "ch_gen_library_run_hours")["Point Definition"]["Reading Type"] = "Accumulator"
        with self.assertRaisesRegex(ValueError, "its own Analog usage point"):
            handheld_expectations(self.gateways, self.recipe, points)

    def test_omitted_route_and_demand_with_register_are_rejected(self):
        recipe = copy.deepcopy(self.recipe)
        recipe["records"].pop()
        with self.assertRaisesRegex(ValueError, "export totals"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe = copy.deepcopy(self.recipe)
        recipe["records"] = [r for r in recipe["records"] if r["Gateway"] != "gw_neptune_cedar_row_submeters"]
        with self.assertRaisesRegex(ValueError, "Every handheld gateway"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe = copy.deepcopy(self.recipe)
        recipe["records"][0]["Gateway"] = "gw_acquisuite_student_electric"
        with self.assertRaisesRegex(ValueError, "handheld type"):
            handheld_expectations(self.gateways, recipe, self.points)
        recipe = copy.deepcopy(self.recipe)
        recipe["acceptanceOnly"]["directDemand"]["Reading Point"] = "Register Reading"
        with self.assertRaisesRegex(ValueError, "without a register"):
            handheld_expectations(self.gateways, recipe, self.points)

    def test_new_route_acceptance_cases_build_on_the_starting_readings(self):
        pack = yaml.load((self.folder / "04-acceptance-runs.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)["handheldAcceptance"]
        cases = {case["key"]: case for case in pack["cases"]}
        registers = {(r["MeterNumber"], r["Prompt"]): r for r in self.rows}
        new_cases = ("utility_check_constants", "switchgear_round", "generator_round", "irrigation_season_read", "cedar_row_c_round")
        self.assertTrue(set(new_cases) <= set(pack["independentCases"]))
        for key in new_cases[:4]:
            case = cases[key]
            route = case["Route"]
            covered = set()
            for reading in case["Readings"]:
                with self.subTest(case=key, meter=reading["Meter"], prompt=reading["Prompt"]):
                    row = registers[(reading["Meter"], reading["Prompt"])]
                    self.assertEqual(route, f'{row["Cycle"]}/{row["Route"]}')
                    covered.add((reading["Meter"], reading["Prompt"]))
                    if "Value" in reading:
                        self.assertIsNone(row["ReadingDescription"])  # a demand read has no register
                        continue
                    self.assertEqual(row["StartingReading"], reading["Previous register"])
                    self.assertEqual(row["Constant"], reading["Multiplier"])
                    self.assertGreater(reading["Current register"], reading["Previous register"])
                    self.assertAlmostEqual((reading["Current register"] - reading["Previous register"]) * reading["Multiplier"],
                                           reading["Expected usage"], places=6)
            # Every register on the route is read by its case.
            self.assertEqual({k for k, r in registers.items() if f'{r["Cycle"]}/{r["Route"]}' == route}, covered, key)
        switchgear = {r["Prompt"]: r for r in cases["switchgear_round"]["Readings"]}
        self.assertEqual(switchgear["KWH"]["Expected usage"], sum(switchgear[p]["Expected usage"] for p in ("KWHP", "KWHM", "KWHO")))
        # Cedar Row C as built: the reader reads only what cycle 02's route file carries.
        cedar_row_c = cases["cedar_row_c_round"]
        on_file = {r["MeterNumber"] for r in self.rows if (r["Cycle"], r["Route"]) == ("02", "CRCWTR") and r["Active"]}
        every = {r["MeterNumber"] for r in self.rows if r["Route"] == "CRCWTR"}
        self.assertEqual(cedar_row_c["Reading pairs"], len(on_file))
        self.assertEqual(set(cedar_row_c["Not read"]), every - on_file)
        self.assertEqual({"CCF", "GAL", "SYN-SUB-W-CH"}, set(cedar_row_c["Increments"]))

    def test_generated_files_match_the_current_handheld_recipe(self):
        sql = (self.folder / "checks.sql").read_text(encoding="utf-8")
        self.assertEqual(render_handheld(), sql[sql.index(HANDHELD_BEGIN):sql.index(HANDHELD_END) + len(HANDHELD_END)])
        self.assertEqual(render_handheld_paste(), (self.folder / HANDHELD_PASTE).read_text(encoding="utf-8"))
        for name, text in render_handheld_starting_readings().items():
            with self.subTest(file=name):
                self.assertEqual(text, (self.folder / name).read_text(encoding="utf-8"))
        sql = (ROOT / "implementation/stage-9-operations/checks.sql").read_text(encoding="utf-8")
        self.assertEqual(render_handheld_operations(), sql[sql.index(HANDHELD_OPERATIONS_BEGIN):sql.index(HANDHELD_OPERATIONS_END) + len(HANDHELD_OPERATIONS_END)])


if __name__ == "__main__":
    unittest.main()
