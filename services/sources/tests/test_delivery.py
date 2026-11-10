import hashlib
import json
import os
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from services.sources.delivery import deliver, selected_records
from services.sources.cli import main


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.state = self.root / "state"
        self.destination = self.root / "inputs"
        self.content = b"2024-01-01,5\n"
        self.record = {"path": "gateway/day.csv", "url": "releases/test/files/gateway/day.csv", "sha256": hashlib.sha256(self.content).hexdigest(), "size": len(self.content), "metadata": {"source": "gateway", "period_start": "2024-01-01T00:00:00Z", "delivery_path": "SCIENCE/day.csv"}}
        path = self.state / "public" / self.record["url"]
        path.parent.mkdir(parents=True)
        path.write_bytes(self.content)

    def tearDown(self):
        self.directory.cleanup()

    def test_consumed_input_is_not_delivered_again_without_explicit_replay(self):
        first = deliver([self.record], self.destination, state=self.state, input_layout=True)
        target = self.destination / "SCIENCE/day.csv"
        self.assertEqual(self.content, target.read_bytes())
        target.unlink()
        repeat = deliver([self.record], self.destination, state=self.state, input_layout=True)
        self.assertEqual("previously_delivered", repeat["files"][0]["status"])
        self.assertFalse(target.exists())
        deliver([self.record], self.destination, state=self.state, input_layout=True, replay=True)
        self.assertEqual(self.content, target.read_bytes())
        self.assertEqual("delivered", first["files"][0]["status"])
        self.assertEqual([], list(self.destination.rglob("*.partial")))

    def test_hash_failure_leaves_input_absent_and_pending_outcome_requires_replay(self):
        source = self.state / "public" / self.record["url"]
        source.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "does not match"):
            deliver([self.record], self.destination, state=self.state)
        self.assertFalse((self.destination / self.record["path"]).exists())
        source.write_bytes(self.content)
        with self.assertRaisesRegex(ValueError, "uncertain"):
            deliver([self.record], self.destination, state=self.state)
        deliver([self.record], self.destination, state=self.state, replay=True)
        receipts = [json.loads(path.read_text()) for path in (self.root / ".northlake-deliveries").glob("*.json")]
        self.assertIn("failed", {receipt["status"] for receipt in receipts})
        self.assertEqual(self.content, (self.destination / self.record["path"]).read_bytes())

    def test_source_selection_excludes_acceptance_and_preserves_partition(self):
        acceptance = {**self.record, "metadata": {**self.record["metadata"], "ordinary_delivery": False, "case": "gap"}}
        self.assertEqual([self.record], list(selected_records([self.record, acceptance], source="gateway", day="2024-01-01")))
        self.assertEqual([acceptance], list(selected_records([self.record, acceptance], case="gap", include_acceptance=True)))
        self.assertEqual([], list(selected_records([self.record], month="2024-02")))

    def test_crash_after_input_publication_and_consumption_is_not_automatically_replayed(self):
        original_replace = os.replace
        def consumed_before_commit(source, target):
            original_replace(source, target)
            if Path(target).name == "day.csv":
                Path(target).unlink()
                raise OSError("process stopped before delivery receipt commit")
        with patch("services.sources.delivery.os.replace", side_effect=consumed_before_commit):
            with self.assertRaisesRegex(OSError, "receipt commit"):
                deliver([self.record], self.destination, state=self.state)
        with self.assertRaisesRegex(ValueError, "uncertain"):
            deliver([self.record], self.destination, state=self.state)
        self.assertFalse((self.destination / self.record["path"]).exists())

    def test_delivery_path_cannot_escape_selected_input(self):
        record = {**self.record, "metadata": {"delivery_path": "../escape.csv"}}
        with self.assertRaisesRegex(ValueError, "Invalid artifact path"):
            deliver([record], self.destination, state=self.state, input_layout=True)
        self.assertFalse((self.root / "escape.csv").exists())

    def test_http_delivery_fetches_the_catalogued_release_url(self):
        with patch("services.sources.delivery.urlopen", return_value=io.BytesIO(self.content)) as request:
            deliver([self.record], self.destination, url="http://source.test")
        request.assert_called_once_with("http://source.test/" + self.record["url"], timeout=60)
        self.assertEqual(self.content, (self.destination / self.record["path"]).read_bytes())

    def test_follow_delivers_new_catalog_entries_without_repeating_consumed_inputs(self):
        catalog = self.state / "public/catalog.json"
        catalog.write_text(json.dumps({"artifacts": [self.record]}))
        second = {**self.record, "path": "gateway/next.csv", "url": "releases/test/files/gateway/next.csv", "metadata": {**self.record["metadata"], "delivery_path": "SCIENCE/next.csv"}}
        (self.state / "public" / second["url"]).write_bytes(self.content)
        waits = []
        def advance(_):
            waits.append(True)
            if len(waits) == 1:
                (self.destination / "SCIENCE/day.csv").unlink()
                catalog.write_text(json.dumps({"artifacts": [self.record, second]}))
            else:
                raise KeyboardInterrupt
        with redirect_stdout(io.StringIO()):
            result = main(["deliver", "--state", str(self.state), "--destination", str(self.destination), "--source", "gateway", "--follow"], wait=advance)
        self.assertEqual(130, result)
        self.assertFalse((self.destination / "SCIENCE/day.csv").exists())
        self.assertEqual(self.content, (self.destination / "SCIENCE/next.csv").read_bytes())


if __name__ == "__main__":
    unittest.main()
