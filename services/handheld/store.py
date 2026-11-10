"""Durable rounds, immutable returns and explicit delivery. No EEM connectivity."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from services.sources.delivery import deliver
from services.sources.runtime import atomic_write, safe_path
from .codecs import encode
from .contracts import digest, instant, json_bytes, validate_binding, validate_observation


class Conflict(ValueError):
    pass


def source_identity(root: Path):
    uri = (root / "catalog.sqlite3").resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        identity = json.loads(db.execute("SELECT value FROM settings WHERE key='identity'").fetchone()[0])
        expected = db.execute("SELECT sha256 FROM artifacts WHERE path='contracts/source-model.json'").fetchone()[0]
    relative = safe_path(f"releases/{identity['release_id']}/files/contracts/source-model.json")
    data = (root / "public" / relative).read_bytes()
    if digest(data) != expected:
        raise ValueError("Mounted source model fails its catalog hash")
    model = json.loads(data)
    if model["source_hash"] != identity["source_hash"] or model["seed"] != identity["seed"] or model["model_version"] != identity["version"]:
        raise ValueError("Mounted source model and release identity disagree")
    return {"release_id": identity["release_id"], "model_version": identity["version"], "source_hash": identity["source_hash"],
            "seed": identity["seed"], "assumptions_version": model["assumptions"]["version"]}


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS rounds (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS imports (hash TEXT PRIMARY KEY, export BLOB NOT NULL, binding BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, round_id TEXT NOT NULL, at TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.root / "handheld.sqlite3", timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _save(self, db, doc, action, detail=None):
        db.execute("INSERT INTO rounds VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,document=excluded.document",
                   (doc["id"], doc["revision"], json.dumps(doc, sort_keys=True)))
        db.execute("INSERT INTO events(round_id,at,action,detail) VALUES (?,?,?,?)",
                   (doc["id"], datetime.now(timezone.utc).isoformat(), action, json.dumps(detail or {})))

    def _get(self, db, key, revision=None):
        row = db.execute("SELECT document FROM rounds WHERE id=?", (key,)).fetchone()
        if not row:
            raise ValueError("Round not found")
        doc = json.loads(row[0])
        if revision is not None and doc["revision"] != revision:
            raise Conflict("Round changed in another window; reload it before editing")
        return doc

    def get(self, key):
        with self.connection() as db:
            doc = self._get(db, key)
            doc["events"] = [{"at": r[0], "action": r[1], "detail": json.loads(r[2])} for r in
                             db.execute("SELECT at,action,detail FROM events WHERE round_id=? ORDER BY id", (key,))]
            return doc

    def list(self):
        with self.connection() as db:
            return [{k: doc[k] for k in ("id", "revision", "status", "created_at", "channel", "parent", "fixture_only")}
                    for (data,) in db.execute("SELECT document FROM rounds ORDER BY rowid DESC LIMIT 200") for doc in [json.loads(data)]]

    def create(self, raw, binding_raw, source, route):
        binding = json.loads(binding_raw)
        channels = validate_binding(raw, binding, source)
        matches = [c for c in channels if c["route"] == route]
        if len(matches) != 1:
            raise ValueError("Select a route included in the checked binding")
        import_hash = digest(raw + b"\0" + binding_raw)
        doc = {"id": uuid.uuid4().hex, "revision": 1, "status": "draft", "created_at": datetime.now(timezone.utc).isoformat(),
               "channel": matches[0], "source": source, "environment_id": binding["environment_id"], "database": binding["database"],
               "import_hash": import_hash, "export_sha256": digest(raw), "binding_sha256": digest(binding_raw),
               "fixture_only": binding["environment_id"] == "fixture-only", "observation": None, "artifact": None, "parent": None}
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO imports VALUES (?,?,?)", (import_hash, raw, binding_raw))
            self._save(db, doc, "created")
        return doc

    def edit(self, key, revision, observation):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            doc = self._get(db, key, revision)
            if doc["status"] != "draft":
                raise Conflict("Prepared returns are immutable; create a linked correction")
            doc["observation"] = validate_observation(doc["channel"], observation)
            if doc.get("after") and instant(doc["observation"]["observed_at"]) <= instant(doc["after"]):
                raise ValueError("A follow-up must occur after the skipped visit")
            doc["revision"] += 1
            self._save(db, doc, "saved", doc["observation"])
        return doc

    def finalize(self, key, revision):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            doc = self._get(db, key)
            if doc["artifact"]:
                # Idempotent retry after a response was lost, including its old revision.
                return doc
            if revision != doc["revision"]:
                raise Conflict("Round changed before review; reload it")
            if not doc["observation"]:
                raise ValueError("Save a complete observation before finalizing")
            content = encode(doc["channel"], doc["observation"])
            filename = f"{doc['channel']['route']}-{key}.imp"
            url = f"releases/handheld-{key}/files/{filename}"
            record = {"path": filename, "url": url, "sha256": digest(content), "size": len(content), "media_type": "text/plain",
                      "metadata": {"kind": "handheld", "source": doc["channel"]["gateway_profile"], "ordinary_delivery": False,
                                   "artifact": key, "delivery_path": filename, "period_start": doc["observation"]["observed_at"],
                                   "return_format": doc["channel"]["return_format"], "relationship": doc["parent"],
                                   "supersedes": doc["parent"] if doc["parent"] and doc["parent"]["kind"] == "correction" else None,
                                   "expected_readings": 0 if doc["observation"]["action"] == "skip" else 2,
                                   "expected_usage": doc["observation"]["usage"],
                                   "required_settings": {"UseSqlValues": False, "IgnoreDays": 0, "UseReadingTimeStamp": False, "AllowNoData": True}}}
            path = self.root / "public" / url
            if path.exists() and path.read_bytes() != content:
                raise Conflict("Existing return bytes differ; recovery needs inspection")
            atomic_write(path, content)
            if digest(path.read_bytes()) != record["sha256"]:
                raise ValueError("Return verification failed")
            doc["artifact"], doc["status"] = record, "prepared"
            doc["revision"] += 1
            evidence = {"schema": "northlake-handheld-return-v1", "round": doc, "artifacts": [record]}
            atomic_write(self.root / "public" / f"releases/handheld-{key}/manifest.json", json_bytes(evidence))
            self._save(db, doc, "prepared", record)
        return doc

    def linked(self, key, revision, kind):
        if kind not in {"correction", "follow-up"}:
            raise ValueError("Unknown linked round type")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            parent = self._get(db, key, revision)
            if not parent["artifact"]:
                raise ValueError("Prepare the original return first")
            doc = {**parent, "id": uuid.uuid4().hex, "revision": 1, "status": "draft", "artifact": None,
                   "created_at": datetime.now(timezone.utc).isoformat(), "parent": {"round_id": key, "kind": kind, "sha256": parent["artifact"]["sha256"]}}
            if kind == "follow-up":
                if parent["observation"]["action"] != "skip":
                    raise ValueError("Follow-up is for a skipped visit; export fresh bindings after an actual import")
                doc["observation"] = None
                doc["after"] = parent["observation"]["observed_at"]
            self._save(db, doc, kind, doc["parent"])
        return doc

    def catalog(self):
        with self.connection() as db:
            return {"schema": "northlake-handheld-catalog-v1", "artifacts": [d["artifact"] for (raw,) in db.execute("SELECT document FROM rounds")
                                                                          for d in [json.loads(raw)] if d["artifact"]]}

    def download(self, key):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            doc = self._get(db, key)
            if not doc["artifact"]:
                raise ValueError("Return has not been prepared")
            data = (self.root / "public" / doc["artifact"]["url"]).read_bytes()
            if digest(data) != doc["artifact"]["sha256"]:
                raise ValueError("Return hash mismatch")
            if doc["status"] == "prepared":
                doc["status"] = "downloaded"
            self._save(db, doc, "download-served")
            return data, doc["artifact"]["path"]

    def deliver(self, key, targets, target, replay=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            doc = self._get(db, key)
            if not doc["artifact"]:
                raise ValueError("Return has not been prepared")
            config = targets.get(target)
            if not config or config.get("enabled") is not True or target != doc["channel"]["delivery_target"]:
                raise ValueError("Delivery target is not explicitly configured and enabled for this binding")
            if doc["fixture_only"] and config.get("fixture_only") is not True:
                raise ValueError("Demonstration IDs can only go to a fixture-only target")
            if config.get("environment_id") != doc["environment_id"] or config.get("gateway_profile") != doc["channel"]["gateway_profile"]:
                raise ValueError("Delivery target environment/gateway does not match the binding")
            try:
                receipt = deliver([doc["artifact"]], Path(config["destination"]), state=self.root, input_layout=True, replay=replay)
            except (ValueError, OSError) as error:
                self._save(db, doc, "delivery-failed", {"target": target, "error": str(error)})
                db.commit()
                raise
            doc["status"] = "delivered"
            self._save(db, doc, "delivery", {"target": target, "replay": replay, "receipt": receipt})
            return receipt
