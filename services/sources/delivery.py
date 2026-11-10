"""Deliberate delivery of catalogued artifacts from local storage or HTTP."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from .runtime import atomic_write, safe_path


def selected_records(records, *, source=None, provider=None, kind=None, artifact=None, day=None, month=None, case=None, include_acceptance=False):
    if day:
        datetime.strptime(day, "%Y-%m-%d")
    if month:
        datetime.strptime(month, "%Y-%m")
    for record in records:
        metadata = record.get("metadata", {})
        if not include_acceptance and not metadata.get("ordinary_delivery", metadata.get("ordinaryDelivery", True)):
            continue
        if source and metadata.get("source", metadata.get("source_id")) != source:
            continue
        if provider and metadata.get("provider", metadata.get("provider_id")) != provider:
            continue
        if kind and metadata.get("kind") != kind:
            continue
        if artifact and metadata.get("artifact") != artifact:
            continue
        if case and metadata.get("case", "normal") != case:
            continue
        period = str(metadata.get("period_start", metadata.get("periodStart", "")))
        if day and period[:10] != day:
            continue
        if month and period[:7] != month:
            continue
        yield record


def load_catalog(*, state: Path | None = None, url: str | None = None) -> dict:
    if bool(state) == bool(url):
        raise ValueError("Select exactly one local state directory or HTTP URL")
    if url:
        with urlopen(url.rstrip("/") + "/catalog.json", timeout=60) as response:
            return json.load(response)
    return json.loads((Path(state) / "public" / "catalog.json").read_text(encoding="utf-8"))


def deliver(records, destination: Path, *, state: Path | None = None, url: str | None = None, flat=False, input_layout=False, replay=False) -> dict:
    """Move only hash-verified complete files into the caller-selected destination."""
    if bool(state) == bool(url):
        raise ValueError("Select exactly one local state directory or HTTP URL")
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    delivery_id = uuid.uuid4().hex
    receipt_root = destination.parent / ".northlake-deliveries"
    staging = receipt_root / (delivery_id + ".staging")
    staging.mkdir(parents=True)
    ledger = sqlite3.connect(receipt_root / "delivery.sqlite3", timeout=60)
    ledger.execute("CREATE TABLE IF NOT EXISTS deliveries (target TEXT NOT NULL, sha256 TEXT NOT NULL, path TEXT NOT NULL, status TEXT NOT NULL, delivery_id TEXT NOT NULL, PRIMARY KEY(target, sha256, path))")
    ledger.commit()
    receipt = {"id": delivery_id, "started_at": datetime.now(timezone.utc).isoformat(), "destination": str(destination), "status": "running", "files": []}
    receipt_path = receipt_root / (delivery_id + ".json")
    seen = set()
    try:
        for record in records:
            logical = safe_path(record["path"])
            download = safe_path(record["url"])
            if len(download.parts) < 4 or download.parts[0] != "releases" or download.parts[2] != "files":
                raise ValueError("Artifact URL must identify an immutable source release")
            relative = logical.name if flat else str(safe_path(record.get("metadata", {}).get("delivery_path", str(logical)))) if input_layout else str(logical)
            if relative.casefold() in seen:
                raise ValueError(f"Multiple artifacts target the same delivery filename: {relative}")
            seen.add(relative.casefold())
            target = (destination / relative).resolve()
            if not target.is_relative_to(destination):
                raise ValueError(f"Delivery target leaves the selected directory: {relative}")
            ledger.execute("BEGIN IMMEDIATE")
            prior = ledger.execute("SELECT status FROM deliveries WHERE target=? AND sha256=? AND path=?", (str(target), record["sha256"], str(download))).fetchone()
            if prior and prior[0] == "completed" and not replay:
                ledger.commit()
                receipt["files"].append({"path": str(logical), "destination": relative, "sha256": record["sha256"], "status": "previously_delivered"})
                continue
            if prior and prior[0] == "pending" and not target.exists() and not replay:
                raise ValueError(f"Delivery outcome is uncertain for {relative}; reconcile the consumer or explicitly replay")
            if target.exists():
                if not target.is_file():
                    raise ValueError(f"Delivery target is not a file: {relative}")
                with target.open("rb") as stream:
                    existing = hashlib.file_digest(stream, "sha256").hexdigest()
                if existing != record["sha256"]:
                    raise ValueError(f"Refusing to replace different existing delivery file: {relative}")
                if not replay:
                    receipt["files"].append({"path": str(logical), "destination": relative, "sha256": existing, "status": "already_present"})
                    ledger.execute("INSERT INTO deliveries VALUES (?, ?, ?, 'completed', ?) ON CONFLICT(target, sha256, path) DO UPDATE SET status='completed', delivery_id=excluded.delivery_id", (str(target), existing, str(download), delivery_id))
                    ledger.commit()
                    continue
            ledger.execute("INSERT INTO deliveries VALUES (?, ?, ?, 'pending', ?) ON CONFLICT(target, sha256, path) DO UPDATE SET status='pending', delivery_id=excluded.delivery_id", (str(target), record["sha256"], str(download), delivery_id))
            ledger.commit()
            temporary = staging / (str(len(seen)) + ".partial")
            source = urlopen(url.rstrip("/") + "/" + quote(str(download), safe="/"), timeout=60) if url else (Path(state) / "public" / str(download)).open("rb")
            digest = hashlib.sha256()
            length = 0
            with source, temporary.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    length += len(chunk)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest() != record["sha256"] or length != record["size"]:
                raise ValueError(f"Downloaded artifact does not match its catalog: {logical}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, target)
            ledger.execute("UPDATE deliveries SET status='completed' WHERE target=? AND sha256=? AND path=?", (str(target), record["sha256"], str(download)))
            ledger.commit()
            receipt["files"].append({"path": str(logical), "destination": relative, "sha256": digest.hexdigest(), "status": "delivered"})
        receipt["status"] = "completed"
        return receipt
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["error"] = str(error)
        raise
    finally:
        ledger.close()
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n")
        for remaining in staging.iterdir():
            if remaining.is_file():
                remaining.unlink()
        staging.rmdir()
