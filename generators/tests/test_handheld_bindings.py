"""Validate the checked environment-to-simulator binding contract."""
import copy
import hashlib
import unittest

from generators.handheld_bindings import make_manifest, pilot_expectations


class HandheldBindingTests(unittest.TestCase):
    def setUp(self):
        self.expected = pilot_expectations(["CRBMW", "SCGAS"])
        self.rows = []
        for index, item in enumerate(self.expected, 1):
            read_type = item["ReadTypeFields"]
            self.rows.append({"channel_key": item["Key"], "reading_pt_id": 10 * index,
                             "usage_pt_id": 10 * index + 1, "meter_id": index, "hmr_meter_id": index,
                             "hmr_reading_id": index, "gateway_id": 20 + index, "cycle": item["Cycle"],
                             "route": item["Route"], "sequence": item["Sequence"], "text_prompt": item["Prompt"],
                             "channel": item["Channel"], "active": True, "type_description": item["ReadType"],
                             "ert_type": None, "num_dials": read_type["NumDials"], "num_decimals": 0,
                             "read_type_code": read_type["ReadTypeCode"], "read_direction": read_type["ReadDirection"],
                             "demand_read": "N", "truncation_factor": 0, "raw_unit": "Reading",
                             "usage_unit": item["DisplayUnit"], "meter_constant": 1, "delta_multiplier": 1})
        self.options = {"export_bytes": b"actual export bytes\r\n", "source": {
            "release_id": "source-one", "model_version": "v1", "source_hash": "a" * 64,
            "seed": 104729, "assumptions_version": 1},
            "openings": {row["Route"]: {"value": 1000, "observed_at": "2024-01-01T00:00:00-08:00",
                         "basis": "controlled-pilot", "reason": "Controlled opening"} for row in self.expected},
            "environment_id": "northlake-test", "verified_at": "2026-11-04T20:00:00+00:00"}

    def test_two_codecs_keep_checked_ids_units_source_pin_and_export_hash(self):
        result = make_manifest(self.expected, self.rows, **self.options)
        self.assertEqual("northlake-handheld-bindings-v1", result["schema"])
        self.assertEqual(hashlib.sha256(self.options["export_bytes"]).hexdigest(), result["export_sha256"])
        self.assertEqual(self.options["source"], result["source"])
        self.assertEqual(["neptune", "mvrs"], [row["return_format"] for row in result["channels"]])
        self.assertEqual([10, 20], [row["reading_pt_id"] for row in result["channels"]])
        self.assertEqual(["kgal", "therm"], [row["usage_unit"] for row in result["channels"]])
        self.assertTrue(all(row["channel"] == "01" for row in result["channels"]))

    def test_missing_installed_ids_do_not_become_placeholder_bindings(self):
        for field in ("meter_id", "reading_pt_id", "usage_pt_id", "hmr_meter_id", "hmr_reading_id", "gateway_id"):
            with self.subTest(field=field):
                rows = copy.deepcopy(self.rows)
                rows[0][field] = None
                with self.assertRaisesRegex(ValueError, "complete app setup first"):
                    make_manifest(self.expected, rows, **self.options)

    def test_changed_units_formats_or_multiplier_fail_before_export(self):
        for field, value in (("raw_unit", "kgal"), ("num_decimals", 3), ("meter_constant", .001),
                             ("delta_multiplier", None), ("delta_multiplier", 2), ("cycle", "99"), ("active", False)):
            with self.subTest(field=field, value=value):
                rows = copy.deepcopy(self.rows)
                rows[0][field] = value
                with self.assertRaisesRegex(ValueError, "differs from controlled pilot"):
                    make_manifest(self.expected, rows, **self.options)

    def test_ambiguous_rows_and_unsupported_route_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            make_manifest(self.expected, [self.rows[0], self.rows[0]], **self.options)
        with self.assertRaisesRegex(ValueError, "Unsupported pilot route"):
            pilot_expectations(["CRAWTR"])

    def test_opening_must_fit_digits_and_have_an_explicit_timezone(self):
        for field, value in (("value", 10000000000), ("observed_at", "2024-01-01T00:00:00"), ("basis", "inferred")):
            with self.subTest(field=field):
                options = copy.deepcopy(self.options)
                options["openings"]["CRBMW"][field] = value
                with self.assertRaises(ValueError):
                    make_manifest(self.expected, self.rows, **options)


if __name__ == "__main__":
    unittest.main()
