"""Protect the executable Northlake task recipe and its generated SQL expectations."""
import copy
import json
import unittest
from datetime import datetime, timedelta

import yaml

from generators.stage_check_data import (
    ROOT, UniqueLoader, WORKFLOW_BEGIN, WORKFLOW_END, render_gateway_types, render_workflows, workflow_expectations,
)


class Stage3WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT / "implementation" / "stage-3-gateways-and-data"
        cls.gateways = yaml.load((cls.folder / "02-gateways.yaml").read_text(), Loader=UniqueLoader)
        cls.recipe = yaml.load((cls.folder / "03-workflows-and-tasks.yaml").read_text(), Loader=UniqueLoader)
        cls.data = workflow_expectations(cls.gateways, cls.recipe)

    def test_one_reusable_task_per_workflow_supports_independent_schedules(self):
        self.assertEqual(11, len(self.data["tasks"]))
        self.assertEqual(11, len({task["Workflow"] for task in self.data["tasks"]}))
        self.assertEqual(16, len(self.data["schedules"]))
        counts = {}
        for schedule in self.data["schedules"]:
            counts[schedule["Workflow"]] = counts.get(schedule["Workflow"], 0) + 1
            self.assertFalse(schedule["Active"])
            self.assertEqual(33, schedule["TimeZoneId"])
        self.assertEqual(3, counts["FIGGateway"])
        self.assertEqual(2, counts["MV90Gateway"])
        self.assertEqual(2, counts["NOAAGateway"])
        self.assertEqual(2, counts["NeptuneGateway"])
        self.assertEqual(15, len({schedule["Gateway"] for schedule in self.data["schedules"]}))
        self.assertFalse(any(task["Name"] in self.data["retiredTasks"] for task in self.data["tasks"]))

    def test_history_overrides_do_not_leak_into_current_schedule_or_defaults(self):
        noaa = [task for task in self.data["schedules"] if task["Workflow"] == "NOAAGateway"]
        self.assertEqual(1, len({schedule["Task"] for schedule in noaa}))
        by_operation = {next(p["Value"] for p in task["Parameters"] if p["Name"] == "Operation"): task for task in noaa}
        history = by_operation["History"]
        current = by_operation["Current"]
        self.assertEqual((1, 900), (current["ScheduleKind"], current["IntervalSeconds"]))
        self.assertEqual((2, "0 0 3 * * ?"), (history["ScheduleKind"], history["CronExpression"]))
        parameters = {p["Name"]: p["Value"] for p in history["Parameters"]}
        self.assertEqual("2024-01-01T08:00:00Z", parameters["HistoryStartUtc"])
        self.assertEqual("3", parameters["ArchiveDelayDays"])
        self.assertEqual("", parameters["HistoryEndUtc"])
        self.assertEqual("", next(p["Value"] for p in current["Parameters"] if p["Name"] == "HistoryStartUtc"))
        defaults = next(task["Parameters"] for task in self.data["tasks"] if task["Workflow"] == "NOAAGateway")
        self.assertEqual("", next(p["Value"] for p in defaults if p["Name"] == "Operation"))

    def test_gateway_and_root_defaults_stay_blank_until_the_schedule_supplies_them(self):
        for task in self.data["tasks"]:
            parameters = {p["Name"]: p for p in task["Parameters"]}
            self.assertEqual("", parameters["GatewayId"]["Value"])
            self.assertTrue(parameters["GatewayId"]["Required"])
            self.assertEqual("", parameters["RootDirectory"]["Value"])
        for schedule in self.data["schedules"]:
            parameters = {p["Name"]: p for p in schedule["Parameters"]}
            self.assertTrue(parameters["GatewayId"]["Override"])
            self.assertTrue(parameters["RootDirectory"]["Override"])
            self.assertTrue(parameters["RootDirectory"]["Value"])

    def test_gateway_ids_are_resolved_by_name_instead_of_snapshot_ids(self):
        gateways = copy.deepcopy(self.gateways)
        for record in gateways["records"]:
            record["installed"]["gatewayId"] = 999999
            record["Schedule parameters"]["GatewayId"] = 999999
        recipe = copy.deepcopy(self.recipe)
        for record in recipe["schedules"]:
            record["Parameters"]["GatewayId"] = 999999
        self.assertEqual(self.data, workflow_expectations(gateways, recipe))

    def test_fake_requires_a_connected_publication_step(self):
        recipe = copy.deepcopy(self.recipe)
        fake = recipe["customWorkflows"][0]
        fake["Links"] = [link for link in fake["Links"] if not link["From"].endswith(".IntervalDataFilePath")]
        with self.assertRaisesRegex(ValueError, "missing publication links"):
            workflow_expectations(self.gateways, recipe)

    def test_unknown_references_and_parameters_are_rejected(self):
        for section, field, message in (("schedules", "Gateway", "Unknown schedule gateway"),
                                        ("schedules", "Task", "Unknown schedule task"),
                                        ("tasks", "Workflow", "Unknown task workflow")):
            with self.subTest(section=section, field=field):
                recipe = copy.deepcopy(self.recipe)
                recipe[section][0][field] = "unknown"
                with self.assertRaisesRegex(ValueError, message):
                    workflow_expectations(self.gateways, recipe)
        recipe = copy.deepcopy(self.recipe)
        recipe["tasks"][0]["Default parameters"]["BackupDirectory"] = "obsolete"
        with self.assertRaisesRegex(ValueError, "Unknown workflow parameters"):
            workflow_expectations(self.gateways, recipe)

    def test_required_bacnet_interface_may_be_blank_in_defaults_but_not_on_the_schedule(self):
        recipe = copy.deepcopy(self.recipe)
        configured_task = next(task for task in recipe["tasks"] if task["Workflow"] == "BacnetGateway")
        self.assertIsNone(configured_task["Default parameters"]["LocalIpAddress"])
        schedule = next(schedule for schedule in recipe["schedules"] if schedule["Task"] == configured_task["key"])
        schedule["Parameters"]["LocalIpAddress"] = "192.0.2.15"
        task = next(task for task in workflow_expectations(self.gateways, recipe)["schedules"] if task["Workflow"] == "BacnetGateway")
        interface = next(p for p in task["Parameters"] if p["Name"] == "LocalIpAddress")
        self.assertTrue(interface["Required"])
        self.assertEqual("192.0.2.15", interface["Value"])
        schedule["Parameters"]["LocalIpAddress"] = None
        with self.assertRaisesRegex(ValueError, "Missing required schedule parameters"):
            workflow_expectations(self.gateways, recipe)
        del schedule["Parameters"]["LocalIpAddress"]
        with self.assertRaisesRegex(ValueError, "Missing required schedule parameters"):
            workflow_expectations(self.gateways, recipe)

    def test_duplicate_workflow_tasks_or_missing_gateway_override_are_rejected(self):
        recipe = copy.deepcopy(self.recipe)
        recipe["tasks"].append(copy.deepcopy(recipe["tasks"][0]))
        with self.assertRaisesRegex(ValueError, "one reusable task"):
            workflow_expectations(self.gateways, recipe)
        recipe = copy.deepcopy(self.recipe)
        del recipe["schedules"][0]["Parameters"]["GatewayId"]
        with self.assertRaisesRegex(ValueError, "schedule must select its GatewayId"):
            workflow_expectations(self.gateways, recipe)

    def test_fake_inclusive_range_is_96_intervals_on_one_pacific_day(self):
        task = next(task for task in self.recipe["schedules"] if task["Task"] == "task_fake")
        start = datetime.fromisoformat(task["Parameters"]["StartTimestamp"])
        end = datetime.fromisoformat(task["Parameters"]["EndTimestamp"])
        self.assertEqual(96, (end - start).total_seconds() / (15 * 60) + 1)
        self.assertEqual("2024-01-01T00:00:00+00:00", (start - timedelta(hours=8)).isoformat())
        self.assertEqual("2024-01-01T23:45:00+00:00", (end - timedelta(hours=8)).isoformat())

    def test_optional_workspace_overrides_are_checked_as_blank_unless_explicit(self):
        names = {"InputDirectory", "WorkingDirectory", "ArchiveDirectory", "ErrorDirectory", "OutputDirectory"}
        file_tasks = [task for task in self.data["schedules"] if any(p["Name"] in names for p in task["Parameters"])]
        self.assertEqual(10, len(file_tasks))
        for task in file_tasks:
            self.assertTrue(task["RootDirectory"])
            for parameter in task["Parameters"]:
                if parameter["Name"] in names:
                    self.assertEqual("", parameter["Value"])
                    self.assertFalse(parameter["Required"])
        recipe = copy.deepcopy(self.recipe)
        task = next(task for task in recipe["schedules"] if task["Task"] == "task_spinwave")
        task["Parameters"]["ArchiveDirectory"] = r"\\archive\northlake\spinwave"
        result = next(task for task in workflow_expectations(self.gateways, recipe)["schedules"] if task["Workflow"] == "SpinwaveGateway")
        self.assertEqual(r"\\archive\northlake\spinwave", next(p["Value"] for p in result["Parameters"] if p["Name"] == "ArchiveDirectory"))

    def test_source_file_clocks_are_explicit_at_the_collector_boundary(self):
        for record in self.gateways["records"]:
            if record["key"] in ("gw_mv90_valley_mdef", "gw_mv90_helios_mv9"):
                self.assertTrue(all(n["Node Parameters"]["TimeStampType"] == "UTC" for n in record["Nodes"]))
        fig = [record for record in self.data["schedules"] if record["Workflow"] == "FIGGateway"]
        self.assertEqual(3, len(fig))
        self.assertTrue(all(next(p["Value"] for p in record["Parameters"] if p["Name"] == "TimeStampType") == "utc" for record in fig))

    def test_node_check_ignores_fields_that_the_collector_does_not_read(self):
        text = render_gateway_types()
        data = json.loads(text.split(" = N'", 1)[1].rsplit("';", 1)[0].replace("''", "'"))
        fig_nodes = [n for n in data["nodes"] if n["Gateway"] in (
            "Northlake FIG File Imports", "Northlake Fixed Network Submeters", "Ridgeline SCADA File Imports")]
        self.assertEqual(6, len(fig_nodes))
        self.assertTrue(all(not n["Params"] for n in fig_nodes))

    def test_invalid_intervals_and_five_field_cron_are_rejected(self):
        recipe = copy.deepcopy(self.recipe)
        recipe["schedules"][0]["Interval seconds"] = 299
        with self.assertRaisesRegex(ValueError, "Interval below 300"):
            workflow_expectations(self.gateways, recipe)
        recipe = copy.deepcopy(self.recipe)
        history = next(record for record in recipe["schedules"] if record["Schedule kind"] == "Cron")
        history["Cron expression"] = "0 3 * * *"
        with self.assertRaisesRegex(ValueError, "Cron requires six fields"):
            workflow_expectations(self.gateways, recipe)

    def test_acceptance_cases_resolve_the_task_and_schedule_together(self):
        cases = yaml.load((self.folder / "04-acceptance-runs.yaml").read_text(), Loader=UniqueLoader)
        schedules = {schedule["key"]: schedule for schedule in self.recipe["schedules"]}
        for record in cases["records"]:
            if "Schedule" not in record:
                continue
            schedule = schedules[record["Schedule"].split()[0]]
            self.assertEqual(schedule["Task"], record["Task"])
            self.assertEqual(schedule["Gateway"], record["Gateway"].split()[0])

    def test_checker_snapshot_matches_the_recipe(self):
        text = (self.folder / "checks.sql").read_text()
        self.assertEqual(render_workflows(), text[text.index(WORKFLOW_BEGIN):text.index(WORKFLOW_END) + len(WORKFLOW_END)])


if __name__ == "__main__":
    unittest.main()
