import tempfile
import unittest
import io
import json
import signal
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.sources.cli import main, produce
from services.sources.runtime import ArtifactStore, ProducerLock, producer_health


IDENTITY = {"version": "test", "seed": 104729, "source_hash": "source-a", "history_start": "2024-01-01T00:00:00+00:00"}


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_interrupted_generation_does_not_advance_cursor_and_replay_recovers_complete_files(self):
        artifact = {"path": "gateway/2024-01-01.csv", "content": b"timestamp,value\n1,2\n", "metadata": {"source": "gateway"}}
        def interrupted():
            yield artifact
            raise RuntimeError("generator interrupted")
        store = ArtifactStore(self.root, IDENTITY)
        with self.assertRaisesRegex(RuntimeError, "generator interrupted"):
            store.publish_batch("day-1", "2024-01-02T00:00:00+00:00", interrupted())
        self.assertIsNone(store.completed_through)
        self.assertEqual([], list(store.records()))
        self.assertFalse((store.public / "catalog.json").exists())
        store.close()
        store = ArtifactStore(self.root, IDENTITY)
        self.addCleanup(store.close)
        self.assertEqual(1, store.publish_batch("day-1", "2024-01-02T00:00:00+00:00", [artifact]))
        store.publish_catalog()
        self.assertEqual("2024-01-02T00:00:00+00:00", store.completed_through)
        self.assertTrue(store.verify()["ok"])
        self.assertEqual(0, store.publish_batch("day-1", "2024-01-02T00:00:00+00:00", interrupted()))

    def test_identity_or_published_bytes_cannot_change_in_place(self):
        store = ArtifactStore(self.root, IDENTITY)
        store.publish_batch("one", "2024-01-01T00:15:00+00:00", [{"path": "one.csv", "content": b"1"}])
        with self.assertRaisesRegex(ValueError, "Immutable artifact changed"):
            store.publish_batch("two", "2024-01-01T00:30:00+00:00", [{"path": "one.csv", "content": b"2"}])
        self.assertEqual("2024-01-01T00:15:00+00:00", store.completed_through)
        store.close()
        with self.assertRaisesRegex(ValueError, "new state"):
            ArtifactStore(self.root, {**IDENTITY, "seed": 3})

    def test_verification_reports_changed_and_missing_artifacts(self):
        store = ArtifactStore(self.root, IDENTITY)
        self.addCleanup(store.close)
        store.publish_batch("one", "2024-01-01T00:15:00+00:00", [{"path": "one.csv", "content": b"1"}, {"path": "two.csv", "content": b"2"}])
        (store.release / "files/one.csv").write_bytes(b"changed")
        (store.release / "files/two.csv").unlink()
        result = store.verify()
        self.assertFalse(result["ok"])
        self.assertEqual({"content_changed", "missing"}, {row["error"] for row in result["errors"]})

    def test_path_cannot_escape_source_store(self):
        store = ArtifactStore(self.root, IDENTITY)
        self.addCleanup(store.close)
        with self.assertRaisesRegex(ValueError, "Invalid artifact path"):
            store.publish_batch("one", "2024-01-01T00:15:00+00:00", [{"path": "../escape.csv", "content": b"1"}])
        self.assertFalse((self.root / "escape.csv").exists())

    def test_bootstrap_cutoff_is_persisted_and_restart_keeps_live_quarter_hour_partitions(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bootstrap = start + timedelta(days=1)
        calls = []
        def artifacts(**kwargs):
            calls.append((kwargs["start"], kwargs["through"]))
            name = kwargs["start"].strftime("%Y%m%dT%H%M") + "-" + kwargs["through"].strftime("%Y%m%dT%H%M")
            yield {"path": name + ".csv", "content": name.encode()}
        generation = SimpleNamespace(MODEL_VERSION="test", source_fingerprint=lambda _: "hash", create_model=lambda *_: object(), iter_artifacts=artifacts)
        args = SimpleNamespace(source_root=self.root, state=self.root / "store", seed=104729, start=start, through=None, command="init", poll_seconds=60)
        with patch("services.sources.generation", generation, create=True), patch("services.sources.cli.render_pages"), redirect_stdout(io.StringIO()):
            produce(args, clock=lambda: bootstrap)
            self.assertEqual([(start, bootstrap)], calls)
            calls.clear()
            catchup = bootstrap + timedelta(days=3, minutes=30)
            produce(args, clock=lambda: catchup)
            self.assertEqual(290, len(calls))
            self.assertTrue(all(end - begin == timedelta(minutes=15) for begin, end in calls))
            expected_names = {begin.strftime("%Y%m%dT%H%M") + "-" + end.strftime("%Y%m%dT%H%M") + ".csv" for begin, end in calls}
            store = ArtifactStore(args.state)
            self.assertEqual(bootstrap.isoformat(), store.status()["bootstrap_cutoff"])
            self.assertEqual(catchup.isoformat(), store.completed_through)
            self.assertTrue(expected_names.issubset({record["path"] for record in store.records()}))
            store.close()
            calls.clear()
            (args.state / "public/catalog.json").write_text('{"completed_through":null}')
            produce(args, clock=lambda: catchup)
            self.assertEqual([], calls)
            self.assertEqual(catchup.isoformat(), json.loads((args.state / "public/catalog.json").read_text())["completed_through"])

    def test_running_producer_stops_if_source_fingerprint_changes(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        generation = SimpleNamespace(MODEL_VERSION="test", source_fingerprint=lambda _: "hash", create_model=lambda *_: object(), iter_artifacts=lambda **_: iter([]))
        args = SimpleNamespace(source_root=self.root, state=self.root / "store", seed=104729, start=start, through=None, command="run", poll_seconds=60)
        def changed(_):
            generation.source_fingerprint = lambda _: "changed"
        with patch("services.sources.generation", generation, create=True), patch("services.sources.cli.render_pages"), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "changed while running"):
                produce(args, clock=lambda: start + timedelta(minutes=15), wait=changed)

    def test_source_change_inside_chunk_rolls_back_progress(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        generation = SimpleNamespace(MODEL_VERSION="test", source_fingerprint=lambda _: "hash", create_model=lambda *_: object())
        def changed_artifacts(**kwargs):
            yield {"path": "day.csv", "content": b"first"}
            generation.source_fingerprint = lambda _: "changed"
        generation.iter_artifacts = changed_artifacts
        args = SimpleNamespace(source_root=self.root, state=self.root / "store", seed=104729, start=start, through=None, command="init", poll_seconds=60)
        with patch("services.sources.generation", generation, create=True), patch("services.sources.cli.render_pages"), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "during a generation chunk"):
                produce(args, clock=lambda: start + timedelta(days=1))
        store = ArtifactStore(args.state)
        self.addCleanup(store.close)
        self.assertIsNone(store.completed_through)
        self.assertEqual([], list(store.records()))
        self.assertFalse(producer_health(args.state, now=start + timedelta(days=1))["ok"])

    def test_release_identity_is_part_of_every_public_download_url(self):
        urls = []
        for version in ("one", "two"):
            store = ArtifactStore(self.root / version, {**IDENTITY, "release_id": version})
            self.addCleanup(store.close)
            store.publish_batch("day", "2024-01-02T00:00:00+00:00", [{"path": "gateway/day.csv", "content": version.encode()}])
            store.publish_catalog()
            record = next(iter(store.records()))
            urls.append(record["url"])
            self.assertEqual(version.encode(), (store.public / record["url"]).read_bytes())
            self.assertTrue((store.release / "manifest.json").exists())
        self.assertNotEqual(*urls)

    def test_only_one_producer_owns_a_state_and_closing_releases_ownership(self):
        lock = ProducerLock(self.root)
        try:
            with self.assertRaisesRegex(ValueError, "Another source producer"):
                ProducerLock(self.root)
        finally:
            lock.close()
        reopened = ProducerLock(self.root)
        reopened.close()

    def test_health_distinguishes_active_bootstrap_stall_and_idle_generation_lag(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        store = ArtifactStore(self.root, IDENTITY)
        self.addCleanup(store.close)
        store.heartbeat("generating", now, continuous=True)
        self.assertTrue(producer_health(self.root, now=now)["ok"])
        self.assertFalse(producer_health(self.root, now=now + timedelta(seconds=181))["ok"])
        store.publish_batch("old", "2024-01-02T00:00:00+00:00", [])
        store.heartbeat("idle", now, continuous=True)
        self.assertFalse(producer_health(self.root, now=now)["ok"])
        store.publish_batch("recent", now.isoformat(), [])
        store.heartbeat("idle", now, continuous=True)
        self.assertTrue(producer_health(self.root, now=now)["ok"])
        store.heartbeat("complete", now, continuous=False)
        self.assertFalse(producer_health(self.root, now=now)["ok"])

    def test_sigterm_rolls_back_active_chunk_releases_lock_and_restores_handler(self):
        previous = signal.getsignal(signal.SIGTERM)
        generation = SimpleNamespace(MODEL_VERSION="test", source_fingerprint=lambda _: "hash", create_model=lambda *_: object())
        def interrupted(**kwargs):
            yield {"path": "day.csv", "content": b"first"}
            self.assertIsNot(signal.getsignal(signal.SIGTERM), previous)
            signal.raise_signal(signal.SIGTERM)
            self.fail("SIGTERM must interrupt the active producer")
        generation.iter_artifacts = interrupted
        state = self.root / "store"
        with patch("services.sources.generation", generation, create=True), patch("services.sources.cli.render_pages"), redirect_stdout(io.StringIO()):
            result = main(["init", "--state", str(state), "--source-root", str(self.root), "--start", "2024-01-01T00:00:00Z", "--through", "2024-01-02T00:00:00Z"])
        self.assertEqual(130, result)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)
        lock = ProducerLock(state)
        lock.close()
        store = ArtifactStore(state)
        self.addCleanup(store.close)
        self.assertIsNone(store.completed_through)
        self.assertEqual([], list(store.records()))
        self.assertEqual("stopped", json.loads((state / "producer.json").read_text())["phase"])


if __name__ == "__main__":
    unittest.main()
