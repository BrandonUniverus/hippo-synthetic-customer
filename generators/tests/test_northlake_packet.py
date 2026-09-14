"""Source and fixture checks; these do not claim installed EEM acceptance."""

import csv
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from generators.northlake_packet import ROOT, CUSTOMER, build_packet, sample_files


class NorthlakePacketTests(unittest.TestCase):
    def test_complete_inventory_has_consistent_tables_and_student_center_feed(self):
        packet = build_packet()
        self.assertEqual(21, packet["counts"]["accounts"])
        self.assertEqual(29, packet["counts"]["meters"])
        self.assertEqual(52, packet["counts"]["points"])
        for name, sheet in packet["sheets"].items():
            for row in sheet["rows"]:
                self.assertEqual(len(sheet["headers"]), len(row), (name, row))
        student = [row for row in packet["sheets"]["Meters"]["rows"] if row[0] == "Student Center Electric Interval"]
        self.assertEqual(1, len(student))
        self.assertEqual("SYN-VED-M-0040004", student[0][1])
        mapping = [row for row in packet["sheets"]["Source Measurements"]["rows"] if row[0] == "Student Center AcquiSuite logger"]
        self.assertEqual({"kWh", "kW"}, {row[5] for row in mapping})
        self.assertTrue(all(row[3] == "ASQVED01" and "DeviceID=STUDENT" in row[4] for row in mapping))

    def test_relationships_and_format_cases_are_explicit_without_fake_rollups(self):
        packet = build_packet()
        relationships = packet["sheets"]["Related Measurements"]["rows"]
        self.assertEqual(2, sum(row[4] == "Usage from register difference" for row in relationships))
        self.assertEqual(4, sum("degree days" in row[4] for row in relationships))
        self.assertEqual(3, sum(row[4] == "Measured versus baseline" for row in relationships))
        self.assertEqual(4, len({row[0] for row in packet["sheets"]["Rollup Members"]["rows"]}))
        self.assertNotIn("Fake", json.dumps(packet["sheets"]["Rollup Members"]))
        formats = {row[1] for row in packet["coverage"]["rows"]}
        self.assertTrue({"MDEF", "MV9", "FIG", "SIEMANSREPORT", "MEDIATOR", "EATON", "XML", "FIXEDNETWORKS", "CMEP", "HMR_EVENTS"} <= formats)
        self.assertTrue(all(row[-2:] == ["Not run", "Not run"] for row in packet["coverage"]["rows"]))
        records = packet["instanceMapping"]["rows"]
        self.assertEqual(63, len(records))  # 52 explicit + 4 degree-day + 3 baseline + 4 aggregate points.
        self.assertEqual(63, len({row[1] for row in records}))
        self.assertTrue(all(row[8:12] == ["", "", "", ""] for row in records))
        self.assertTrue(all(len(row) == len(packet["instanceMapping"]["headers"]) for row in records))

    def test_tariff_and_area_values_come_from_existing_sources(self):
        packet = build_packet()
        buildings = {row[0]: row for row in packet["sheets"]["Buildings"]["rows"]}
        self.assertEqual(95000, buildings["Student Center"][5])
        self.assertEqual(58000, buildings["Cedar Row A"][5])
        schedules = {row[1] for row in packet["sheets"]["Rate Schedules"]["rows"]}
        self.assertIn("VED-TOU-GS", schedules)
        self.assertNotIn("VED TOU-GS-3", json.dumps(packet["sheets"]["Utility Services"]))
        charges = packet["sheets"]["Rate Components"]["rows"]
        peak = next(row for row in charges if row[1] == "VED-TOU-GS" and row[2] == "energy / peak")
        self.assertEqual(0.241, peak[3])
        self.assertTrue(all(isinstance(row[3], (int, float)) for row in charges))

    def test_drifted_account_identifier_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="northlake-source-test-") as folder:
            root = Path(folder)
            for directory in ["providers", "scenarios", "eem", "security"]:
                shutil.copytree(ROOT / directory, root / directory)
            file = root / "scenarios/demo-university-v1.yaml"
            file.write_text(file.read_text(encoding="utf-8").replace("SYN-VED-A-0010004", "WRONG-ACCOUNT"), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Account identifier drift: ved_student_center"):
                build_packet(root)

    def test_company_contacts_cover_the_handover_and_department_ownership(self):
        packet = build_packet()
        contacts = {row[1]: row for row in packet["sheets"]["Contacts"]["rows"]}
        self.assertEqual(12, len(contacts))
        self.assertTrue({"Samantha Ireland", "Jordan Hale", "Priya Nandakumar", "Iris Morales", "Nora Chen", "Leo Martinez", "Maya Chen", "Devon Brooks"} <= contacts.keys())
        self.assertEqual("samantha.ireland@northlake.example.edu", contacts["Samantha Ireland"][3])
        self.assertEqual("devon.brooks@northlake.example.edu", contacts["Devon Brooks"][3])
        self.assertEqual("Cedar Row Apartments", contacts["Maya Chen"][0])
        self.assertEqual("Northlake Thermal Plant", contacts["Devon Brooks"][0])
        self.assertEqual("facilities.ops@northlake.example.edu", contacts["Jordan Hale"][3])
        self.assertTrue(all(row[3] and row[4] and "TBD" not in row for row in contacts.values()))
        self.assertTrue({"Valley Electric District", "Sierra Gas Utility", "River City Utilities", "Helios Onsite Solar", "Northlake Thermal Plant"} <= {row[0] for row in contacts.values()})
        units = packet["sheets"]["Organization Units"]["rows"]
        self.assertEqual(6, len(units))
        self.assertEqual({"Northlake University", "Cedar Row Apartments", "Northlake Thermal Plant"}, {row[7] for row in units})
        for row in units:
            contact = contacts[row[2]]
            self.assertEqual([contact[0], contact[3], contact[4]], [row[7], row[3], row[4]])

    def test_acquisuite_golden_delivery_has_exact_time_and_energy_contract(self):
        files = sample_files()
        rows = list(csv.reader(io.StringIO(files["complete"]["content"])))
        self.assertEqual(96, len(rows))
        times = [datetime.strptime(row[0], "'%Y-%m-%d %H:%M:%S'") for row in rows]
        self.assertEqual(datetime(2024, 1, 15, 8), times[0])
        self.assertEqual(datetime(2024, 1, 16, 7, 45), times[-1])
        self.assertTrue(all(b - a == timedelta(minutes=15) for a, b in zip(times, times[1:])))
        self.assertEqual(2020, sum(float(row[1]) for row in rows))
        self.assertEqual(120, max(float(row[2]) for row in rows))
        self.assertTrue(all(float(row[1]) == float(row[2]) / 4 for row in rows))
        self.assertEqual("ASQVED01_STUDENT.log", files["complete"]["filename"])

    def test_gap_and_backfill_are_disjoint_and_reconstruct_the_complete_file(self):
        files = sample_files()
        complete = files["complete"]["content"].splitlines()
        gap = files["gap"]["content"].splitlines()
        backfill = files["backfill"]["content"].splitlines()
        self.assertEqual(88, len(gap))
        self.assertEqual(8, len(backfill))
        self.assertFalse(set(gap) & set(backfill))
        self.assertEqual(complete, sorted(gap + backfill))
        self.assertTrue(backfill[0].startswith("'2024-01-15 20:00:00'"))
        self.assertTrue(backfill[-1].startswith("'2024-01-15 21:45:00'"))

    def test_checked_in_deliveries_and_hashes_match_regeneration(self):
        directory = ROOT / CUSTOMER / "sample-data/acquisuite"
        expected = json.loads((directory / "expected-results.json").read_text(encoding="utf-8"))
        self.assertEqual("Not run", expected["installedAcceptance"])
        for case, sample in sample_files().items():
            actual = (directory / case / sample["filename"]).read_bytes()
            self.assertEqual(sample["content"].encode(), actual)
            self.assertEqual(expected["cases"][case]["sha256"], hashlib.sha256(actual).hexdigest())


if __name__ == "__main__":
    unittest.main()
