"""Crash-safe publication of immutable synthetic source files and their catalog."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


def safe_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or any(p in {"", ".", ".."} for p in value.split("/")) or ":" in value:
        raise ValueError(f"Invalid artifact path: {value!r}")
    return path


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(6):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            # Windows readers/scanners can briefly deny replacement after close.
            time.sleep(0.02 * (attempt + 1))


class ProducerLock:
    """One producer per state; the operating system releases ownership after a crash."""
    def __init__(self, root: Path):
        Path(root).mkdir(parents=True, exist_ok=True)
        self.stream = (Path(root) / "producer.lock").open("a+b")
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.stream.close()
            raise ValueError("Another source producer owns this state directory") from error

    def close(self) -> None:
        self.stream.close()


def producer_health(root: Path, *, now: datetime | None = None, max_age_seconds=180, max_lag_seconds=1800) -> dict:
    now = now or datetime.now(timezone.utc)
    path = Path(root) / "producer.json"
    if not path.is_file():
        return {"ok": False, "phase": "not_started", "reason": "No producer heartbeat"}
    state = json.loads(path.read_text(encoding="utf-8"))
    heartbeat = datetime.fromisoformat(state["heartbeat_at"])
    age = max(0, (now - heartbeat).total_seconds())
    completed = datetime.fromisoformat(state["completed_through"]) if state.get("completed_through") else None
    lag = max(0, (now - completed).total_seconds()) if completed else None
    live_phase = state["phase"] in {"starting", "generating", "idle"}
    caught_up = state["phase"] != "idle" or not state.get("continuous") or (lag is not None and lag <= max_lag_seconds)
    return {**state, "heartbeat_age_seconds": age, "generation_lag_seconds": lag, "ok": live_phase and age <= max_age_seconds and caught_up}


class ArtifactStore:
    def __init__(self, root: Path, identity: dict | None = None):
        self.root = Path(root)
        self.public = self.root / "public"
        if identity is None and not (self.root / "catalog.sqlite3").is_file():
            raise FileNotFoundError(f"No source store at {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)
        self.public.mkdir(exist_ok=True)
        self.connection = sqlite3.connect(self.root / "catalog.sqlite3", timeout=60)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts (
                path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
                media_type TEXT NOT NULL, metadata TEXT NOT NULL, batch_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS batches (
                batch_id TEXT PRIMARY KEY, through TEXT NOT NULL, artifact_count INTEGER NOT NULL);
        """)
        row = self.connection.execute("SELECT value FROM settings WHERE key='identity'").fetchone()
        if row:
            self.identity = json.loads(row[0])
            if identity is not None and self.identity != identity:
                self.connection.close()
                raise ValueError("Source version, facts, seed or history start changed; use a new state directory or volume.")
        elif identity is not None:
            self.identity = identity
            self.connection.execute("INSERT INTO settings VALUES ('identity', ?)", (json.dumps(identity, sort_keys=True),))
            self.connection.commit()
        else:
            self.connection.close()
            raise ValueError("Source store has no release identity")
        release_id = self.identity.get("release_id")
        if not release_id:
            release_id = hashlib.sha256(json.dumps(self.identity, sort_keys=True).encode()).hexdigest()[:20]
        if len(safe_path(release_id).parts) != 1:
            self.connection.close()
            raise ValueError("Release identity must be one path component")
        self.release_url = "releases/" + release_id
        self.release = self.public / self.release_url
        self.release.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        self.connection.close()

    @property
    def completed_through(self) -> str | None:
        row = self.connection.execute("SELECT value FROM settings WHERE key='completed_through'").fetchone()
        return row[0] if row else None

    def initialize_bootstrap(self, cutoff: str) -> str:
        self.connection.execute("INSERT OR IGNORE INTO settings VALUES ('bootstrap_cutoff', ?)", (cutoff,))
        self.connection.commit()
        return self.connection.execute("SELECT value FROM settings WHERE key='bootstrap_cutoff'").fetchone()[0]

    def publish_batch(self, batch_id: str, through: str, artifacts: Iterable[dict]) -> int:
        """Commit progress only after complete files exist; replay can reclaim crash orphans."""
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            if self.connection.execute("SELECT 1 FROM batches WHERE batch_id=?", (batch_id,)).fetchone():
                self.connection.rollback()
                return 0
            count = 0
            for artifact in artifacts:
                logical = str(safe_path(artifact["path"]))
                content = artifact["content"]
                if not isinstance(content, bytes):
                    raise TypeError(f"Artifact content must be bytes: {logical}")
                digest = hashlib.sha256(content).hexdigest()
                metadata = json.dumps(artifact.get("metadata", {}), sort_keys=True, default=str)
                media_type = artifact.get("media_type", "application/octet-stream")
                existing = self.connection.execute("SELECT sha256, size, media_type, metadata FROM artifacts WHERE path=?", (logical,)).fetchone()
                if existing:
                    if (existing["sha256"], existing["size"], existing["media_type"], existing["metadata"]) != (digest, len(content), media_type, metadata):
                        raise ValueError(f"Immutable artifact changed: {logical}")
                    continue
                target = self.release / "files" / logical
                if target.exists():
                    if not target.is_file():
                        raise ValueError(f"Conflicting unpublished file: {logical}")
                    with target.open("rb") as stream:
                        existing_digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    if existing_digest != digest:
                        raise ValueError(f"Conflicting unpublished file: {logical}")
                else:
                    atomic_write(target, content)
                self.connection.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)", (logical, digest, len(content), media_type, metadata, batch_id))
                count += 1
            self.connection.execute("INSERT INTO batches VALUES (?, ?, ?)", (batch_id, through, count))
            self.connection.execute("INSERT INTO settings VALUES ('completed_through', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (through,))
            self.connection.commit()
            return count
        except BaseException:
            self.connection.rollback()
            raise

    def records(self) -> Iterable[dict]:
        for row in self.connection.execute("SELECT * FROM artifacts ORDER BY path"):
            yield {"path": row["path"], "url": self.release_url + "/files/" + row["path"], "sha256": row["sha256"], "size": row["size"], "media_type": row["media_type"], "metadata": json.loads(row["metadata"])}

    def status(self) -> dict:
        row = self.connection.execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM artifacts").fetchone()
        bootstrap = self.connection.execute("SELECT value FROM settings WHERE key='bootstrap_cutoff'").fetchone()
        return {"identity": self.identity, "bootstrap_cutoff": bootstrap[0] if bootstrap else None, "completed_through": self.completed_through, "artifact_count": row[0], "bytes": row[1]}

    def publish_catalog(self) -> None:
        target = self.release / "manifest.json"
        temporary = target.with_suffix(".json.partial")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write('{"schema_version":1,"identity":')
            json.dump(self.identity, stream, sort_keys=True)
            stream.write(',"completed_through":')
            json.dump(self.completed_through, stream)
            stream.write(',"manifest_url":')
            json.dump(self.release_url + "/manifest.json", stream)
            stream.write(',"artifacts":[')
            for index, record in enumerate(self.records()):
                if index:
                    stream.write(",")
                json.dump(record, stream, sort_keys=True, separators=(",", ":"))
            stream.write("]}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        current = self.public / "catalog.json"
        temporary = current.with_suffix(".json.partial")
        with target.open("rb") as source, temporary.open("wb") as output:
            shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, current)
        atomic_write(self.public / "health" / "ready", json.dumps(self.status(), sort_keys=True).encode() + b"\n")

    def heartbeat(self, phase: str, now: datetime, *, continuous: bool) -> None:
        atomic_write(self.root / "producer.json", json.dumps({"phase": phase, "heartbeat_at": now.isoformat(), "completed_through": self.completed_through, "continuous": continuous}, sort_keys=True).encode() + b"\n")

    def verify(self) -> dict:
        errors = []
        count = 0
        for record in self.records():
            target = self.public / record["url"]
            if not target.is_file():
                errors.append({"path": record["path"], "error": "missing"})
            else:
                with target.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if target.stat().st_size != record["size"] or digest != record["sha256"]:
                    errors.append({"path": record["path"], "error": "content_changed"})
            count += 1
        return {"checked": count, "errors": errors, "ok": not errors}
