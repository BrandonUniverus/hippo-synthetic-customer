"""Source encoder contracts. Real EEM collector proof uses the generated manifest."""
import csv
import gzip
import io
import json
import struct
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from services.sources.gateways import (
    FIG_FORMATS, acceptance_samples, encode_compatibility, encode_fig, encode_mv90,
    encode_partition, gateway_bindings, write_fixture_manifest,
)

ROOT = Path(__file__).resolve().parents[3]
UTC = timezone.utc


class ContractModel:
    """Pinned, deliberately simple values isolate serializer behavior from models."""

    def __init__(self, root=ROOT):
        self.root = root
        self.bindings = gateway_bindings(root)

    def readings(self, binding, start, end):
        interval = timedelta(minutes=binding["interval_minutes"])
        seconds = int(interval.total_seconds())
        first = datetime.fromtimestamp((int(start.timestamp()) // seconds + 1) * seconds, UTC)
        index = 0
        while first <= end:
            value = Decimal(index % 4) if binding["reading_type"] == "Digital" else Decimal(index % 4) / 4 + 1
            yield {"timestamp_utc": first, "value": value}
            first += interval
            index += 1


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = ContractModel()
        cls.start = datetime(2024, 1, 15, 8, tzinfo=UTC)
        cls.end = cls.start + timedelta(days=1)

    def test_expanded_direct_inputs_are_215_with_no_generated_or_duplicate_points(self):
        bindings = self.model.bindings
        self.assertEqual(215, len(bindings))
        self.assertEqual(215, len({row["channel"] for row in bindings}))
        self.assertEqual({"Analog": 205, "Digital": 10}, dict(Counter(row["reading_type"] for row in bindings)))
        self.assertEqual([1, 2, 4, 5, 9, 66, 128], sorted(Counter(row["profile"] for row in bindings).values()))

    def test_full_day_native_artifacts_cover_every_binding_and_are_repeatable(self):
        first = list(encode_partition(self.model, self.start, self.end))
        second = list(encode_partition(self.model, self.start, self.end))
        self.assertEqual([(x["path"], x["content"]) for x in first], [(x["path"], x["content"]) for x in second])
        self.assertEqual(14616, sum(x["metadata"]["records"] for x in first))
        self.assertEqual({b["channel"] for b in self.model.bindings}, {c for x in first for c in x["metadata"]["channels"]})
        self.assertTrue(all(x["metadata"]["ordinary_delivery"] for x in first))
        self.assertEqual(len(first), len({x["path"] for x in first}))

    def test_acquisuite_continuous_data_is_utc_interval_end_and_filename_matches_device(self):
        artifact = next(x for x in encode_partition(self.model, self.start, self.end)
                        if x["metadata"]["delivery_path"].startswith("ASQVED01_STUDENT_"))
        rows = list(csv.reader(io.StringIO(gzip.decompress(artifact["content"]).decode())))
        self.assertEqual(96, len(rows))
        self.assertEqual("'2024-01-15 08:15:00'", rows[0][0])
        self.assertEqual("'2024-01-16 08:00:00'", rows[-1][0])
        self.assertEqual(["1", "1"], rows[0][1:])

    def test_customer_acquisuite_cases_stay_start_stamped_and_out_of_normal_delivery(self):
        samples = list(acceptance_samples(ROOT))
        self.assertEqual([96, 88, 8], [len(x["content"].splitlines()) for x in samples])
        self.assertTrue(samples[0]["content"].startswith(b"'2024-01-15 08:00:00'"))
        self.assertTrue(all(not x["metadata"]["ordinary_delivery"] for x in samples))
        complete = samples[0]["content"].splitlines()
        self.assertEqual(complete, sorted(samples[1]["content"].splitlines() + samples[2]["content"].splitlines()))

    def test_seven_compatibility_encodings_do_not_become_seven_normal_deliveries(self):
        artifacts = list(encode_compatibility(self.model, self.start, self.end))
        self.assertEqual({"gw_fig_multi_format"}, {x["metadata"]["feed"] for x in artifacts})
        self.assertEqual(set(FIG_FORMATS), {x["metadata"]["format"] for x in artifacts})
        self.assertTrue(all(x["metadata"]["records"] == 24 and not x["metadata"]["ordinary_delivery"] for x in artifacts))
        fixed = ET.fromstring(next(x["content"] for x in artifacts if x["metadata"]["format"] == "FIXEDNETWORKS"))
        self.assertEqual("2024-01-15T09:00:00Z", fixed.find(".//TimePeriod").get("StartTime"))
        self.assertNotIn("EndRead", fixed.find(".//TimePeriod").attrib)

    def test_binary_one_interval_file_has_headers_and_correct_value_without_a_day_padding(self):
        stamp = self.start + timedelta(minutes=15)
        for dialect, endian in (("MDEF", "<"), ("MV9", ">")):
            content = encode_mv90(dialect, "VEDSCIENCE01", {1: [(stamp, Decimal("4.25"))]})
            self.assertEqual(216 * 3, len(content))
            self.assertEqual((216, 1), struct.unpack_from(endian + "HH", content, 0))
            self.assertEqual((216, 10), struct.unpack_from(endian + "HH", content, 216))
            self.assertEqual(4.25, struct.unpack_from("<f", content, 432 + 24)[0])
            self.assertEqual(b"VEDSCIENCE01", content[4:24].rstrip())

    def test_binary_and_fixed_network_gaps_start_new_runs_instead_of_filling(self):
        stamps = [self.start + timedelta(minutes=n) for n in (15, 30, 60)]
        content = encode_mv90("MDEF", "VEDSCIENCE01", {1: [(s, 1) for s in stamps]})
        self.assertEqual([1, 10, 1010, 10, 1010], [struct.unpack_from("<H", content, offset + 2)[0] for offset in range(0, len(content), 216)])
        binding = next(b for b in self.model.bindings if b["profile"] == "gw_fig_multi_format")
        series = [(binding, [(self.start + timedelta(hours=n), 1) for n in (1, 2, 4)])]
        document = ET.fromstring(encode_fig("FIXEDNETWORKS", series))
        self.assertEqual(2, len(document.findall(".//ContiguousIntervalSet")))
        self.assertEqual(3, len(document.findall(".//Reading")))

    def test_binary_rejects_unrepresentable_times_and_preserves_long_matching_identity(self):
        with self.assertRaisesRegex(ValueError, "fifteen-minute"):
            encode_mv90("MDEF", "VEDSCIENCE01", {1: [(self.start + timedelta(seconds=1), 1)]})
        recorder = "VEDRECREATION01"
        content = encode_mv90("MDEF", recorder, {1: [(self.start, 1)]})
        self.assertEqual(recorder.encode(), content[4:24].rstrip())
        self.assertEqual(recorder.encode(), content[220:240].rstrip())

    def test_encoder_refuses_duplicate_or_outside_partition_model_rows(self):
        binding = self.model.bindings[0]
        for rows in ([{"timestamp_utc": self.start, "value": 1}],
                     [{"timestamp_utc": self.end, "value": 1}] * 2):
            class InvalidModel:
                bindings = [binding]

                def readings(self, binding, start, end):
                    return rows

            with self.assertRaises(ValueError):
                list(encode_partition(InvalidModel(), self.start, self.end))

    def test_spinwave_keeps_channel_zero_placeholder_and_ridgeline_keeps_fixed_pst(self):
        artifacts = list(encode_partition(self.model, self.start, self.end))
        spinwave = next(x for x in artifacts if x["metadata"]["format"] == "SPINWAVE")
        self.assertTrue(spinwave["metadata"]["delivery_path"].startswith("SCIENCE/"))
        rows = list(csv.reader(io.StringIO(spinwave["content"].decode())))
        self.assertEqual(["SW-SCI-LAB-01", "", "1", "1"], rows[1][1:])
        ridge = next(x for x in artifacts if x["metadata"]["feed"] == "gw_fig_ridgeline_scada")
        self.assertIn(b"2024-01-15 00:10:00", ridge["content"])
        self.assertEqual("utc", ridge["metadata"]["requiredSettings"]["TimeStampType"])

    def test_utc_boundaries_keep_both_fallback_instants_and_native_interval_counts(self):
        for start, hours, count in ((datetime(2024, 3, 10, 8, tzinfo=UTC), 23, 92),
                                    (datetime(2024, 11, 3, 7, tzinfo=UTC), 25, 100)):
            artifacts = list(encode_partition(self.model, start, start + timedelta(hours=hours)))
            sample = next(x for x in artifacts if x["metadata"]["format"] == "MDEF")
            self.assertEqual(count, len(sample["_expected"][0][1]))
            with tempfile.TemporaryDirectory() as folder:
                manifest = write_fixture_manifest([sample], folder)
                expected = manifest["cases"][0]["expected"]
                self.assertEqual(len(expected), len({(r["ptId"], r["utcTimeStamp"]) for r in expected}))
                if hours == 25:
                    one_point = [r for r in expected if r["ptId"] == 1]
                    self.assertLess(len({r["localTimeStamp"] for r in one_point}), len(one_point))

    def test_manifest_uses_synthetic_runtime_ids_and_carries_actual_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            artifacts = list(encode_partition(self.model, self.start, self.start + timedelta(hours=1), compatibility=True))
            manifest = write_fixture_manifest(artifacts, folder)
            self.assertGreater(len(manifest["cases"]), 7)
            self.assertEqual(manifest, json.loads((Path(folder) / "manifest.json").read_text()))
            for case, artifact in zip(manifest["cases"], artifacts):
                self.assertEqual(artifact["content"], (Path(folder) / case["source"]).read_bytes())
                self.assertEqual(1, case["runtime"]["gatewayId"])
                self.assertEqual(artifact["metadata"]["records"], len(case["expected"]))

    def test_actual_model_hour_and_four_quarter_hour_chunks_emit_identical_readings(self):
        from services.sources.model import SourceModel

        model = SourceModel(ROOT)
        start = datetime(2025, 1, 31, 8, tzinfo=UTC)
        for binding in model.bindings:
            whole = list(model.readings(binding, start, start + timedelta(hours=1)))
            pieces = [row for quarter in range(4) for row in model.readings(
                binding, start + timedelta(minutes=15 * quarter), start + timedelta(minutes=15 * (quarter + 1)))]
            self.assertEqual(whole, pieces, binding["channel"])
            if binding["reading_type"] == "Digital":
                self.assertTrue(all(row["value"] in (0, 1, 2, 3) for row in whole))


if __name__ == "__main__":
    unittest.main()
