import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from services.handheld.codecs import encode
from services.handheld.contracts import digest, json_bytes, native_time, parse_export, validate_binding
from services.handheld.fixtures import FIXTURE_SOURCE, demo
from services.handheld.store import Conflict, Store


class HandheldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw, self.binding = demo()
        self.channel = validate_binding(self.raw, self.binding, FIXTURE_SOURCE)[1]
        self.store = Store(self.root / "state")
        self.doc = self.store.create(self.raw, json_bytes(self.binding), FIXTURE_SOURCE, "SCGAS")
        self.observation = {"action": "read", "value": 1125, "reader": "NLR001", "observed_at": "2026-10-15T12:00:00-07:00", "note": "Access clear"}

    def tearDown(self):
        self.temp.cleanup()

    def test_export_envelopes_counts_identity_and_precision(self):
        rows = parse_export(self.raw)
        self.assertEqual([(900001, "0CRBMW", 10000000000), (900002, "0SCGAS", 1000000)],
                         [(r["meter_id"], r["wire_route"], 10 ** r["num_dials"]) for r in rows])
        for changed in [self.raw[:-128], self.raw.replace(b"0CRBMWNN00000001", b"0CRBMWNN00000002"), self.raw.replace(b"FTRNN", b"BADNN"), self.raw.replace(b"RDG", b"BAD", 1)]:
            with self.subTest(changed=changed[:30]), self.assertRaises(ValueError):
                parse_export(changed)
        for field, value in [("meter_id", 42), ("gateway_id", None), ("meter_constant", "0.001"), ("text_prompt", "CCF"), ("sequence", 2)]:
            changed = deepcopy(self.binding)
            changed["channels"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_binding(self.raw, changed, FIXTURE_SOURCE)
        with self.assertRaises(ValueError):
            validate_binding(self.raw, self.binding, {**FIXTURE_SOURCE, "source_hash": "1" * 64})

    def test_native_fields_skip_and_width_limits(self):
        lines = encode(self.channel, self.observation).decode().splitlines()
        self.assertEqual("900002", lines[1][101:120].strip())
        self.assertEqual("0000001125", lines[2][33:43])
        self.assertEqual("0000001000", lines[2][105:115])
        self.assertEqual("NLR001", lines[2][75:83].strip())
        self.assertEqual("MTM", lines[3][:3])
        with self.assertRaises(ValueError):
            encode(self.channel, {**self.observation, "observed_at": self.channel["opening"]["observed_at"]})
        skip = {**self.observation, "action": "skip", "value": None, "note": "Locked"}
        skipped = encode(self.channel, skip).decode().splitlines()[2]
        self.assertEqual(("S", "01", "0000001000"), (skipped[61], skipped[63:65], skipped[33:43]))
        water = validate_binding(self.raw, self.binding, FIXTURE_SOURCE)[0]
        self.assertEqual("SK", encode(water, skip).decode().splitlines()[4][44:46])
        for patch_value in [{"value": 1000000}, {"value": -1}, {"value": 999}, {"value": 1125.5}, {"note": "x" * 41}, {"note": "é"}]:
            with self.subTest(value=patch_value), self.assertRaises(ValueError):
                encode(self.channel, {**self.observation, **patch_value})

    def test_mvrs_read_audit_and_skip_codes(self):
        # Without codes, a read is N with audit 0 and a skip is 01: the bytes of every round saved before codes existed.
        self.assertEqual(("N", "00", "0"), self._codes(self.observation))
        self.assertEqual(("O", "00", "3"), self._codes({**self.observation, "read_code": "O", "audit_code": "3"}))
        self.assertEqual(("C", "00", "0"), self._codes({**self.observation, "read_code": "C"}))
        skip = {**self.observation, "action": "skip", "value": None, "note": "Dog in yard", "skip_code": "04"}
        self.assertEqual(("S", "04", "0"), self._codes(skip))
        for patch_value in [{"read_code": "S"}, {"read_code": "X"}, {"audit_code": "A"}, {"audit_code": "10"}, {"skip_code": "00"}, {"skip_code": "10"}]:
            with self.subTest(value=patch_value), self.assertRaises(ValueError):
                encode(self.channel, {**self.observation, **patch_value})
        water = validate_binding(self.raw, self.binding, FIXTURE_SOURCE)[0]
        with self.assertRaises(ValueError):
            encode(water, {**self.observation, "read_code": "O"})

    def _codes(self, observation):
        rdg = encode(self.channel, observation).decode().splitlines()[2]
        return rdg[61], rdg[63:65], rdg[65]

    def test_leap_day_dst_both_folds_and_utc_conversion(self):
        self.assertEqual("2024-02-29T12:00:00-08:00", native_time("2024-02-29T20:00:00Z").isoformat())
        for value in ["2026-11-01T01:30:00-07:00", "2026-11-01T01:30:00-08:00", "2026-11-01T01:30:00", "2026-11-01T12:00:00.123-08:00"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                native_time(value)
        self.assertEqual("2026-03-08T03:00:00-07:00", native_time("2026-03-08T10:00:00Z").isoformat())

    def test_resume_conflict_finalization_and_linked_correction(self):
        saved = self.store.edit(self.doc["id"], 1, self.observation)
        resumed = Store(self.root / "state").get(saved["id"])
        self.assertEqual(125, resumed["observation"]["usage"])
        with self.assertRaises(Conflict):
            self.store.edit(saved["id"], 1, self.observation)
        final = self.store.finalize(saved["id"], saved["revision"])
        self.assertEqual(final, self.store.finalize(saved["id"], saved["revision"]))
        with self.assertRaises(Conflict):
            self.store.edit(final["id"], final["revision"], self.observation)
        corrected = self.store.linked(final["id"], final["revision"], "correction")
        corrected = self.store.edit(corrected["id"], 1, {**self.observation, "value": 1127})
        corrected = self.store.finalize(corrected["id"], corrected["revision"])
        self.assertEqual(final["artifact"]["sha256"], corrected["parent"]["sha256"])
        self.assertNotEqual(final["artifact"]["sha256"], corrected["artifact"]["sha256"])
        self.assertEqual(2, len(self.store.catalog()["artifacts"]))
        self.assertEqual(125, self.store.get(final["id"])["observation"]["usage"])

    def test_interrupted_publication_is_ineligible_and_retry_identical(self):
        saved = self.store.edit(self.doc["id"], 1, self.observation)
        from services.handheld import store
        original = store.atomic_write
        calls = 0
        def fault(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("interrupted manifest publication")
            original(path, data)
        with patch.object(store, "atomic_write", fault), self.assertRaises(OSError):
            self.store.finalize(saved["id"], saved["revision"])
        self.assertEqual([], self.store.catalog()["artifacts"])
        self.assertEqual("draft", self.store.get(saved["id"])["status"])
        final = Store(self.root / "state").finalize(saved["id"], saved["revision"])
        self.assertEqual(digest(encode(self.channel, self.observation)), final["artifact"]["sha256"])

    def test_explicit_delivery_receipts_consumed_files_and_uncertainty(self):
        saved = self.store.edit(self.doc["id"], 1, self.observation)
        final = self.store.finalize(saved["id"], saved["revision"])
        destination = self.root / "gateway" / "Input"
        targets = {"fixture-only": {"enabled": True, "fixture_only": True, "environment_id": "fixture-only",
                                    "gateway_profile": self.channel["gateway_profile"], "destination": str(destination)}}
        with self.assertRaises(ValueError):
            self.store.deliver(final["id"], {}, "fixture-only")
        receipt = self.store.deliver(final["id"], targets, "fixture-only")
        target = destination / final["artifact"]["path"]
        self.assertEqual("delivered", receipt["files"][0]["status"])
        self.assertEqual(final["artifact"]["sha256"], digest(target.read_bytes()))
        target.unlink()  # simulate EEM claiming its input
        self.assertEqual("previously_delivered", self.store.deliver(final["id"], targets, "fixture-only")["files"][0]["status"])
        self.assertFalse(target.exists())
        self.store.deliver(final["id"], targets, "fixture-only", replay=True)
        self.assertTrue(target.exists())
        target.unlink()
        with sqlite3.connect(destination.parent / ".northlake-deliveries/delivery.sqlite3") as db:
            db.execute("UPDATE deliveries SET status='pending'")
        with self.assertRaisesRegex(ValueError, "uncertain"):
            self.store.deliver(final["id"], targets, "fixture-only")
        self.assertEqual("delivery-failed", self.store.get(final["id"])["events"][-1]["action"])

    def test_skip_followup_keeps_opening_and_source_pin(self):
        saved = self.store.edit(self.doc["id"], 1, {**self.observation, "action": "skip", "note": "Locked"})
        final = self.store.finalize(saved["id"], saved["revision"])
        later = self.store.linked(final["id"], final["revision"], "follow-up")
        with self.assertRaises(ValueError):
            self.store.edit(later["id"], 1, {**self.observation, "value": 1180})
        later = self.store.edit(later["id"], 1, {**self.observation, "value": 1180, "observed_at": "2026-11-04T12:00:00-08:00"})
        self.assertEqual(180, later["observation"]["usage"])
        self.assertEqual(FIXTURE_SOURCE, later["source"])
        self.assertIsNone(final["observation"]["usage"])


if __name__ == "__main__":
    unittest.main()
