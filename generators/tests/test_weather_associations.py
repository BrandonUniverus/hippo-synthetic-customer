import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from generators.weather_associations import ROOT, OUTPUT, expected_associations, render
from generators.gateway_assignments import SOURCES, build_data
from generators.northlake_packet import build_packet
from generators.stage_check_data import UniqueLoader


class WeatherAssociationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents = [yaml.load((ROOT / p).read_text(encoding="utf-8"), Loader=UniqueLoader) for p in SOURCES]
        cls.data = build_data(documents)
        cls.point_definitions = {p["key"]: p for p in documents[2]["records"]}
        cls.mapping = yaml.load((ROOT / "data/eem/northlake-eem-metaworld-stage1b-v1.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
        cls.canonical = {p["sourceChannelId"]: p for station in cls.mapping["weatherIndexTargets"]["weatherMeters"] for p in station["points"]}

    def test_all_three_stations_route_six_hourly_forecasts_to_matching_point_definitions(self):
        expected = {
            "KSAC": {"Temperature": "Fahrenheit", "DewPoint": "Fahrenheit", "RelativeHumidity": "Percent", "WindSpeed": "MilesPerHour", "WindDirection": "Degrees", "ProbabilityOfPrecipitation": "Percent"},
            "KSMF": {"Temperature": "Fahrenheit", "DewPoint": "Celsius", "RelativeHumidity": "Percent", "WindSpeed": "KilometersPerHour", "WindDirection": "Degrees", "ProbabilityOfPrecipitation": "Percent"},
            "KSUU": {"Temperature": "Celsius", "DewPoint": "Celsius", "RelativeHumidity": "Percent", "WindSpeed": "Knots", "WindDirection": "Degrees", "ProbabilityOfPrecipitation": "Percent"},
        }
        measure_types = {"Temperature": "Temperature", "DewPoint": "Dew Point", "RelativeHumidity": "Relative Humidity", "WindSpeed": "Wind Speed", "WindDirection": "Wind Direction", "ProbabilityOfPrecipitation": "Precipitation Probability"}
        units = {"Fahrenheit": "degF", "Celsius": "degC", "Percent": "pct", "MilesPerHour": "mph", "KilometersPerHour": "kph", "Knots": "knots", "Degrees": "deg"}
        nodes = [n for n in self.data["Nodes"] if n["Profile"] == "gw_noaa_ksac_observations" and n["Params"][1] == "Forecast"]
        self.assertEqual(set(expected), {n["Params"][2] for n in nodes})
        self.assertEqual(3, len(nodes))
        for node in nodes:
            station = node["Params"][2]
            points = [p for p in self.data["Points"] if p["Profile"] == node["Profile"] and p["Node"] == node["Key"]]
            self.assertEqual(6, len(points))
            self.assertEqual(expected[station], {p["Params"][1]: p["Params"][2] for p in points})
            for point in points:
                with self.subTest(channel=point["Channel"]):
                    definition = self.point_definitions[point["Channel"]]["Point Definition"]
                    canonical = self.canonical[point["Channel"]]
                    self.assertEqual(station, point["Meter"])
                    self.assertEqual("Analog", definition["Reading Type"])
                    self.assertEqual(60, definition["Archive Interval"])
                    self.assertFalse(definition["Index"])
                    self.assertFalse(canonical.get("indexType"))
                    self.assertEqual(measure_types[point["Params"][1]], definition["Measure Type"])
                    self.assertEqual(canonical["measureType"], definition["Measure Type"])
                    unit = units[point["Params"][2]]
                    self.assertEqual(unit, canonical["unit"])
                    self.assertEqual(self.mapping["pointRules"]["unitListEntries"][unit], definition["Unit"])
        self.assertFalse(any(p["Key"] == "gw_aeris_ksmf_weather" for p in self.data["Profiles"]))

    def test_all_observations_keep_their_units_and_each_has_one_matching_association(self):
        expected = {
            "ch_weather_ksac_temp_f_hourly": "Fahrenheit",
            "ch_weather_ksac_dewpoint_f_hourly": "Fahrenheit",
            "ch_weather_ksac_rh_hourly": "Percent",
            "ch_weather_ksac_wind_mph_hourly": "MilesPerHour",
            "ch_weather_ksmf_temp_c_hourly": "Celsius",
            "ch_weather_ksmf_dewpoint_c_hourly": "Celsius",
            "ch_weather_ksmf_rh_hourly": "Percent",
            "ch_weather_ksmf_wind_kph_hourly": "KilometersPerHour",
            "ch_weather_ksuu_temp_c_hourly": "Celsius",
            "ch_weather_ksuu_rh_hourly": "Percent",
            "ch_weather_ksuu_wind_knots_hourly": "Knots",
            "ch_weather_ksuu_dewpoint_c_hourly": "Celsius",
        }
        observations = [p for p in self.data["Points"] if p["Channel"] in expected]
        self.assertEqual(expected, {p["Channel"]: p["Params"][2] for p in observations})
        nodes = {n["Key"]: n for n in self.data["Nodes"] if n["Profile"] == "gw_noaa_ksac_observations"}
        bindings = {p["Channel"]: p for p in self.data["Points"] if p["Profile"] == "gw_noaa_ksac_observations"}
        links = self.mapping["weatherForecastAssociations"]
        self.assertEqual(12, len(links))
        self.assertEqual(set(expected), {link["sourceChannelId"] for link in links})
        self.assertEqual(12, len({link["relatedChannelId"] for link in links}))
        observed_nodes = [node for node in nodes.values() if node["Params"][1] == "Observation"]
        self.assertEqual(3, len(observed_nodes))
        for node in observed_nodes:
            points = [point for point in bindings.values() if point["Node"] == node["Key"]]
            self.assertEqual(4, len(points))
            self.assertEqual({"Temperature", "DewPoint", "RelativeHumidity", "WindSpeed"},
                             {point["Params"][1] for point in points})
        for link in links:
            source = bindings[link["sourceChannelId"]]
            target = bindings[link["relatedChannelId"]]
            self.assertEqual("Observation", nodes[source["Node"]]["Params"][1])
            self.assertEqual("Forecast", nodes[target["Node"]]["Params"][1])
            self.assertEqual(source["Params"][1], target["Params"][1])
            self.assertEqual(source["Meter"], target["Meter"])
            self.assertEqual("V", link["reasonType"])
            self.assertEqual("Association", link["relationshipKind"])
            for binding in (source, target):
                definition = self.point_definitions[binding["Channel"]]["Point Definition"]
                self.assertEqual(self.canonical[binding["Channel"]]["measureType"], definition["Measure Type"])
        rows = expected_associations()
        self.assertEqual(12, len(rows))
        baseline = yaml.load((ROOT / "implementation/stage-3-gateways-and-data/06-baselines.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
        self.assertEqual({(r["Station"], r["Source"], r["Target"], "V", "Association") for r in rows},
                         {(r["Meter"]["Meter Number"], r["Source Point"], r["Target Point"], r["ReasonType"], r["RelationshipKind"]) for r in baseline["weatherAssociations"]})

    def test_equal_units_do_not_make_different_measurements_compatible(self):
        for source, target in (
            ("ch_weather_ksac_temp_f_hourly", "ch_weather_ksac_forecast_dewpoint_f_hourly"),
            ("ch_weather_ksac_rh_hourly", "ch_weather_ksac_forecast_precip_probability_hourly"),
        ):
            mapping = copy.deepcopy(self.mapping)
            link = next(link for link in mapping["weatherForecastAssociations"] if link["sourceChannelId"] == source)
            link["relatedChannelId"] = target
            with self.subTest(source=source), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path = root / "data/eem/northlake-eem-metaworld-stage1b-v1.yaml"
                path.parent.mkdir(parents=True)
                path.write_text(yaml.safe_dump(mapping), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "same supported measurement"):
                    expected_associations(root)

    def test_association_validation_rejects_invalid_station_unit_ownership_and_target(self):
        for case in ("station", "unit", "duplicate", "chain", "derived", "interval"):
            mapping = copy.deepcopy(self.mapping)
            links = mapping["weatherForecastAssociations"]
            points = {p["sourceChannelId"]: p for station in mapping["weatherIndexTargets"]["weatherMeters"] for p in station["points"]}
            target = points[links[0]["relatedChannelId"]]
            if case == "station":
                links[0]["relatedChannelId"] = "ch_weather_ksmf_forecast_temp_f_hourly"
            elif case == "unit":
                target["unit"] = "pct"
            elif case == "duplicate":
                links.append(copy.deepcopy(links[0]))
            elif case == "chain":
                links[0]["relatedChannelId"] = links[0]["sourceChannelId"]
            elif case == "derived":
                target["indexType"] = "DegreeDays"
            else:
                target["intervalMinutes"] = 15
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path = root / "data/eem/northlake-eem-metaworld-stage1b-v1.yaml"
                path.parent.mkdir(parents=True)
                path.write_text(yaml.safe_dump(mapping), encoding="utf-8")
                with self.assertRaises(ValueError):
                    expected_associations(root)

    def test_packet_preserves_explicit_measurements_instead_of_inferring_from_units(self):
        rows = build_packet()["pointSetup"]["rows"]
        counts = {measure: sum(row[6] for row in rows if row[1] == measure) for measure in ("Dew Point", "Wind Speed", "Wind Direction", "Precipitation Probability")}
        self.assertEqual({"Dew Point": 6, "Wind Speed": 6, "Wind Direction": 3, "Precipitation Probability": 3}, counts)

    def test_scenario_reference_channels_and_runtime_bindings_match_stage_three(self):
        scenario = yaml.load((ROOT / "data/scenarios/demo-university-v1.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
        profile = next(p for p in scenario["gatewayBindings"]["profiles"] if p["id"] == "gw_noaa_ksac_observations")
        references = {p["id"]: p for p in scenario["referenceChannels"]}
        actual = {}
        for node in profile["runtime"]["nodes"]:
            for point in node["points"]:
                key = point["channelId"]
                actual[key] = (node["values"]["WeatherKind"], node["values"]["StationID"], point["values"]["Measurement"], point["values"]["OutputUnit"])
                self.assertEqual(60, point["interval"])
                self.assertEqual(self.canonical[key]["unit"], references[key]["unit"])
                self.assertEqual(node["values"]["StationID"], references[key]["sourceId"])
                self.assertEqual(node["values"]["WeatherKind"].lower(), references[key]["role"])
        nodes = {n["Key"]: n for n in self.data["Nodes"] if n["Profile"] == "gw_noaa_ksac_observations"}
        expected = {p["Channel"]: (nodes[p["Node"]]["Params"][1], nodes[p["Node"]]["Params"][2], p["Params"][1], p["Params"][2])
                    for p in self.data["Points"] if p["Profile"] == "gw_noaa_ksac_observations"}
        self.assertEqual(expected, actual)
        self.assertEqual(set(self.canonical), set(actual))
        ids = [p["ptId"] for g in scenario["gatewayBindings"]["profiles"] for n in g.get("runtime", {}).get("nodes", []) for p in n.get("points", []) if "ptId" in p]
        self.assertEqual(len(ids), len(set(ids)))

    def test_generated_association_check_matches_the_recipe(self):
        self.assertEqual(render(), OUTPUT.read_text(encoding="utf-8"))

    def test_current_and_history_schedules_reuse_one_task_and_workflow(self):
        path = ROOT / "implementation/stage-3-gateways-and-data/03-workflows-and-tasks.yaml"
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
        noaa = [row for row in data["schedules"] if row.get("Gateway") == "gw_noaa_ksac_observations"]
        self.assertEqual({"Current", "History"}, {row["Parameters"]["Operation"] for row in noaa})
        self.assertEqual({"task_noaa"}, {row["Task"] for row in noaa})
        self.assertEqual(1, len([row for row in data["tasks"] if row["Workflow"] == "NOAAGateway"]))
        current = next(row for row in noaa if row["Parameters"]["Operation"] == "Current")
        history = next(row for row in noaa if row["Parameters"]["Operation"] == "History")
        self.assertEqual(900, current["Interval seconds"])
        self.assertFalse(current["Enabled"])
        self.assertEqual("2024-01-01T08:00:00Z", history["Parameters"]["HistoryStartUtc"])
        task = next(row for row in data["tasks"] if row["key"] == "task_noaa")
        self.assertEqual(3, task["Default parameters"]["ArchiveDelayDays"])
        self.assertFalse(history["Enabled"])


if __name__ == "__main__":
    unittest.main()
