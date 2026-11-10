"""Check the Stage 2-to-gateway join without connecting to a database."""
import copy
import json
import unittest

import yaml

from generators.gateway_assignments import ROOT, SOURCES, OUTPUT, NOAA_GATEWAY_TYPE, build_data, expand_points, parameter_values, render
from generators.stage_check_data import UniqueLoader, load_handheld_expectations, render_gateway_types


class GatewayAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = [yaml.load((ROOT / path).read_text(encoding="utf-8"), Loader=UniqueLoader) for path in SOURCES]
        cls.data = build_data(cls.documents)

    def test_direct_inputs_and_handheld_meters_are_disjoint(self):
        data = self.data
        direct = {p["Channel"] for p in data["Points"]}
        _, handheld = load_handheld_expectations()
        routes = {row["Key"] for row in handheld["meters"]}
        registers = {row["ReadingChannel"] for row in handheld["meters"] if row["ReadingChannel"]}
        usage = {row["UsageChannel"] for row in handheld["meters"] if row["UsageChannel"]}
        self.assertEqual(258, len(data["Points"]))
        self.assertEqual(258, len(direct))
        self.assertEqual(204, len(routes))
        self.assertEqual(200, len(registers))  # every register read through its Delta
        self.assertEqual(7, len(usage))        # 4 switchgear demand points and 3 run-hours usage points, all Analog
        self.assertFalse(direct & routes)
        self.assertFalse(direct & registers)
        self.assertFalse(direct & usage)
        self.assertEqual(12, len(data["Profiles"]))
        self.assertTrue(all(p["Vendor"] for p in data["Profiles"]))
        self.assertEqual(26, sum(n["Profile"] in {p["Profile"] for p in data["Points"]} for n in data["Nodes"]))
        self.assertTrue(all(p["ReadingType"] in ("Analog", "Digital", "Accumulator") for p in data["Points"]))
        self.assertTrue(all(len(p["Params"]) == 15 for p in data["Points"]))

    def test_apartment_numbers_and_leading_zero_channels_match_stage_two(self):
        points = {p["Channel"]: p for p in self.data["Points"]}
        a = [p for key, p in points.items() if key.startswith("ch_cedar_row_a_unit_")]
        b = [p for key, p in points.items() if key.startswith("ch_cedar_row_b_unit_")]
        self.assertEqual(60, len(a))
        self.assertEqual(64, len(b))
        for building, units in (("a", (101, 201, 320)), ("b", (101, 216, 301, 416))):
            for unit in units:
                point = points[f"ch_cedar_row_{building}_unit_{unit}_kwh_60m"]
                self.assertEqual(f"FN_CR{building.upper()}_{unit}_E", point["Params"][1])
                self.assertEqual("01", point["Params"][2])
        self.assertNotIn("ch_cedar_row_a_unit_1_kwh_60m", points)

    def test_ridgeline_offsets_and_turbine_padding_are_preserved(self):
        points = {p["Channel"]: p for p in self.data["Points"] if p["Profile"] == "gw_fig_ridgeline_scada"}
        self.assertEqual(66, len(points))
        self.assertIn("ch_rwl_wtg01_kwh_10m", points)
        self.assertIn("ch_rwl_wtg10_kwh_10m", points)
        self.assertTrue(all(p["Params"][5] == "480" for p in points.values()))

    def test_template_expansion_preserves_padding(self):
        entry = {"pointTemplate": True, "channelPattern": "turbine_{n} for n in 01..03", "count": 3,
                 "Description": "Energy", "Company": "Plant",
                 "Meter pattern": {"Description": "Turbine {n}", "Meter Number": "T-{n}"},
                 "Point Parameters pattern": "Point Alias: TURBINE_{n}, Channel: 01"}
        expanded = list(expand_points([entry]))
        self.assertEqual(["turbine_01", "turbine_02", "turbine_03"], [p["channel"] for p in expanded])
        self.assertEqual({"Point Alias": "TURBINE_01", "Channel": "01"}, expanded[0]["Point Parameters"])
        self.assertEqual("Energy", expanded[0]["Description"])
        self.assertEqual("Plant", expanded[0]["Company"])
        self.assertEqual({"Description": "Turbine 01", "Meter Number": "T-01"}, expanded[0]["Meter"])
        self.assertEqual({"Description": "Turbine 03", "Meter Number": "T-03"}, expanded[-1]["Meter"])

    def test_lookup_annotations_reject_names_or_meters_that_do_not_identify_the_source(self):
        for field, value in (("Description", "different point"), ("Company", "different company"),
                             ("Meter", {"Description": "different meter", "Meter Number": "wrong"})):
            documents = copy.deepcopy(self.documents)
            documents[3]["records"][0]["Nodes"][0]["Points"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Gateway point lookup"):
                build_data(documents)

    def test_bad_or_overlapping_template_ranges_are_rejected(self):
        for pattern, count in (("x_{n} for n in 1..3", 2), ("x_{n} for n in 1..2,2..3", 4), ("x_{n} for n in 1-3", 3)):
            with self.subTest(pattern=pattern), self.assertRaises(ValueError):
                list(expand_points([{"pointTemplate": True, "channelPattern": pattern, "count": count}]))

    def test_parameter_enablement_and_sparse_columns(self):
        definitions = [{"Label": "IsEnabled", "Column": 1, "Reads": "0 skips the point"},
                       {"Label": "Channel", "Column": 7, "Reads": "channel"}]
        result = parameter_values(definitions, {"Channel": "01"})
        self.assertEqual("1", result[0])
        self.assertEqual("01", result[6])
        self.assertEqual(13, result.count(None))
        self.assertEqual("0", parameter_values([{"Label": "Disabled", "Column": 1}], {})[0])
        self.assertIsNone(parameter_values([{"Label": "IsEnabled", "Column": 1, "Reads": "not read by 7.0"}], {})[0])
        self.assertEqual("0", parameter_values(definitions, {"IsEnabled": "0"})[0])

    def test_unknown_oversized_or_ambiguous_parameters_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown parameter"):
            parameter_values([], {"missing": "x"})
        with self.assertRaisesRegex(ValueError, "exceeds SQL column length"):
            parameter_values([{"Label": "x", "Column": 1}], {"x": "a" * 256})
        for definitions in ([{"Label": "x", "Column": 0}], [{"Label": "x", "Column": 16}],
                            [{"Label": "x", "Column": 1}, {"Label": "y", "Column": 1}],
                            [{"Label": "x", "Column": 1}, {"Label": "x", "Column": 2}]):
            with self.subTest(definitions=definitions), self.assertRaises(ValueError):
                parameter_values(definitions, {})

    def test_duplicate_assignments_and_missing_inputs_are_rejected(self):
        documents = copy.deepcopy(self.documents)
        node = documents[3]["records"][0]["Nodes"][0]
        node["Points"].append(copy.deepcopy(node["Points"][0]))
        with self.assertRaisesRegex(ValueError, "Point assigned more than once"):
            build_data(documents)
        documents = copy.deepcopy(self.documents)
        documents[3]["records"][0]["Nodes"][0]["Points"][0]["channel"] = "missing_stage_two_point"
        with self.assertRaises(KeyError):
            build_data(documents)

    def test_legacy_migration_is_limited_to_nine_complete_weather_snapshots(self):
        legacy = {p["Channel"]: p for p in self.data["Points"] if "Legacy" in p}
        self.assertEqual(9, len(legacy))
        self.assertTrue(all(p["Profile"] == "gw_noaa_ksac_observations" for p in legacy.values()))
        self.assertTrue(all(len(p["Legacy"]["Params"]) == 15 for p in legacy.values()))
        self.assertTrue(all(p["Legacy"]["Params"][0] == "1" for p in legacy.values()))
        self.assertTrue(all(p["Legacy"]["Params"][2:] == [None] * 13 for p in legacy.values()))
        self.assertEqual("dewptm", legacy["ch_weather_ksuu_dewpoint_c_hourly"]["Legacy"]["Params"][1])
        forecast = legacy["ch_weather_ksmf_forecast_temp_f_hourly"]
        self.assertEqual("AERIS-KSMF-FORECAST", forecast["Legacy"]["Node"])
        self.assertEqual(["Northlake Aeris Weather"], forecast["Legacy"]["GatewayNames"])
        self.assertEqual(["1", "tempF"], forecast["Legacy"]["Params"][:2])

    def test_invalid_or_nonweather_legacy_snapshots_are_rejected(self):
        for case in ("other_profile", "empty_gateway", "missing_node", "too_many_params", "nontext_param"):
            documents = copy.deepcopy(self.documents)
            record = documents[4]["records"][0]
            legacy = record["Existing binding"]
            if case == "other_profile":
                record["channel"] = documents[3]["records"][0]["Nodes"][0]["Points"][0]["channel"]
            elif case == "empty_gateway":
                legacy["GatewayNames"] = []
            elif case == "missing_node":
                legacy.pop("Node")
            elif case == "too_many_params":
                legacy["Params"] = ["1"] * 16
            else:
                legacy["Params"][0] = 1
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, "Invalid legacy weather binding"):
                build_data(documents)

    def test_noaa_setup_names_the_actual_destination_and_explicit_enablement(self):
        weather = next(g for g in self.documents[3]["records"] if g["key"] == "gw_noaa_ksac_observations")
        for node in weather["Nodes"]:
            self.assertEqual(1, node["Node Parameters"]["IsEnabled"])
            for binding in node["Points"]:
                self.assertEqual({"Gateway": weather["Gateway"]["Description"], "Node": node["Description"]},
                                 binding["Gateway binding"])
                self.assertEqual(1, binding["Point Parameters"]["IsEnabled"])
                self.assertNotIn("Legacy binding", binding)
        documents = copy.deepcopy(self.documents)
        weather = next(g for g in documents[3]["records"] if g["key"] == "gw_noaa_ksac_observations")
        weather["Nodes"][0]["Points"][0]["Gateway binding"]["Node"] = "different node"
        with self.assertRaisesRegex(ValueError, "Gateway binding does not match"):
            build_data(documents)

    def test_noaa_and_aeris_have_separate_types_and_parameter_contracts(self):
        types = {entry["key"]: entry for entry in self.documents[3]["gatewayTypes"]}
        noaa, aeris = types["type_noaa"], types["type_aeris"]
        self.assertNotEqual(noaa["Name"], aeris["Name"])
        self.assertEqual(NOAA_GATEWAY_TYPE, noaa["Name"])
        self.assertEqual(["IsEnabled", "Measurement", "OutputUnit"],
                         [p["Label"] for p in noaa["Point Parameters"]])
        self.assertEqual(["IsEnabled", "WeatherTypeName", "PointType"],
                         [p["Label"] for p in aeris["Point Parameters"]])
        self.assertEqual(["IsEnabled", "WeatherType", "StationID", "BackFillDays"],
                         [p["Label"] for p in aeris["Node Parameters"]])
        noaa_nodes = {p["Column"]: p["Label"] for p in noaa["Node Parameters"]}
        self.assertEqual({1: "IsEnabled", 2: "WeatherKind", 3: "StationID", 4: "GhcnStationID",
                          5: "WeatherProvider", 6: "EcccStationID", 7: "EcccForecastLocationID"}, noaa_nodes)
        for node in self.data["Nodes"]:
            if node["Profile"] == "gw_noaa_ksac_observations":
                self.assertEqual("NWS", node["Params"][4])
                self.assertIsNone(node["Params"][5])
                self.assertIsNone(node["Params"][6])
        documents = copy.deepcopy(self.documents)
        profile = next(g for g in documents[3]["records"] if g["key"] == "gw_noaa_ksac_observations")
        for incorrect_type in ("Weather Gateway", aeris["Name"]):
            profile["Gateway"]["Vendor"] = incorrect_type
            with self.subTest(vendor=incorrect_type), self.assertRaisesRegex(ValueError, "separate NOAA gateway type"):
                build_data(documents)

    def test_checker_requires_noaa_type_and_checks_aeris_only_while_present(self):
        text = render_gateway_types()
        literal = text.split("DECLARE @GatewayTypesJson nvarchar(max) = N'", 1)[1].rsplit("';", 1)[0]
        expected = json.loads(literal.replace("''", "'"))
        profiles = {p["Name"]: p for p in expected["profiles"]}
        self.assertEqual(NOAA_GATEWAY_TYPE, profiles["Northlake NOAA Weather"]["Vendor"])
        self.assertTrue(profiles["Northlake NOAA Weather"]["Required"])
        self.assertEqual("Aeris Weather Gateway", profiles["Northlake Aeris Weather"]["Vendor"])
        self.assertFalse(profiles["Northlake Aeris Weather"]["Required"])
        self.assertIn({"Name": "Weather Gateway"}, expected["retired"])

    def test_duplicate_and_unmatched_migration_channels_are_rejected(self):
        documents = copy.deepcopy(self.documents)
        documents[4]["records"].append(copy.deepcopy(documents[4]["records"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate weather migration channel"):
            build_data(documents)
        documents = copy.deepcopy(self.documents)
        documents[4]["records"][0]["channel"] = "missing_point"
        with self.assertRaisesRegex(ValueError, "does not identify a direct point binding"):
            build_data(documents)

    def test_generated_sql_matches_sources(self):
        self.assertEqual(render(), (ROOT / OUTPUT).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
