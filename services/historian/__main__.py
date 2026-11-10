"""The Northlake historian: keeps an Access database of the Library's half-hourly readings current.

On first start it writes the whole history; then, a minute after each half hour, it rewrites the last
`refreshHours`, so new readings appear and provisional codes clear. Each write goes to a copy that
replaces the published file, so an Access reader never sees a half-written database.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .rows import load_config, rows, to_csv

UTC = timezone.utc
WRITER = ("java", "-cp", "/opt/historian/classes:/opt/historian/lib/*", "HistorianWriter")
# A healthy historian has written within two cycles.
HEALTHY_AGE = timedelta(minutes=65)


def check_source(app_root, source_root):
    """Refuse an image whose source model is not the published release the rest of Northlake serves."""
    from services.sources.generation import source_fingerprint

    identity = json.loads((Path(source_root) / "public" / "catalog.json").read_text(encoding="utf-8"))["identity"]
    built = source_fingerprint(app_root)
    if built != identity["source_hash"]:
        raise SystemExit(f"The historian's source model ({built[:12]}) is not the published release "
                         f"({identity['source_hash'][:12]}); rebuild the historian from the release's source image.")
    return identity


def window(config, target, now):
    """The whole history on first write, then the last refreshHours, ending at the last closed half hour."""
    utc = now.astimezone(UTC)
    end = utc.replace(minute=utc.minute // 30 * 30, second=0, microsecond=0)
    if not Path(target).exists():
        start = datetime.fromisoformat(config["historyStartLocal"]).replace(tzinfo=ZoneInfo(config["timeZone"]))
        return start.astimezone(UTC), end
    return end - timedelta(hours=int(config["refreshHours"])), end


def publish(model, config, target, now, writer=WRITER):
    target = Path(target)
    start, end = window(config, target, now)
    items = list(rows(model, config, start, end, now))
    with tempfile.TemporaryDirectory(prefix=".writing-", dir=target.parent) as directory:
        work = Path(directory)
        (work / "rows.csv").write_text(to_csv(items), encoding="utf-8", newline="\n")
        staged = work / target.name
        if target.exists():
            shutil.copy2(target, staged)
        result = subprocess.run([*writer, str(work / "rows.csv"), str(staged)], check=True, capture_output=True, text=True)
        replace(staged, target)
    return {"start": start.isoformat(), "end": end.isoformat(), "rows": len(items),
            "flagged": sum(1 for item in items if item["SourceCode"]),
            "writer": json.loads(result.stdout.strip().splitlines()[-1])}


def replace(staged, target, attempts=5, pause=2.0):
    """Swap the new file in. Windows refuses while an Access reader holds the old one open, so wait and retry."""
    for attempt in range(attempts):
        try:
            os.replace(staged, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(pause * (attempt + 1))


def next_run(now):
    """A minute after the next half hour, once that half hour's reading has closed."""
    return now.replace(minute=now.minute // 30 * 30, second=0, microsecond=0) + timedelta(minutes=31)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "once", "health"))
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("NORTHLAKE_HISTORIAN_ROOT", "/historian")))
    parser.add_argument("--source", type=Path, default=Path(os.environ.get("NORTHLAKE_SOURCE_STATE", "/source")))
    parser.add_argument("--app-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    config = load_config()
    target = args.root / config["database"]
    if args.command == "health":
        age = datetime.now(UTC) - datetime.fromtimestamp(target.stat().st_mtime, UTC) if target.exists() else None
        print(json.dumps({"database": str(target), "ageSeconds": age.total_seconds() if age else None}))
        raise SystemExit(0 if age is not None and age <= HEALTHY_AGE else 1)

    from services.sources.generation import create_model

    identity = check_source(args.app_root, args.source)
    model = create_model(args.app_root)
    print(json.dumps({"eventType": "started", "release": identity["release_id"], "database": str(target)}), flush=True)
    while True:
        now = datetime.now(UTC)
        try:
            print(json.dumps({"eventType": "published", **publish(model, config, target, now)}), flush=True)
        except (subprocess.CalledProcessError, OSError) as error:
            print(json.dumps({"eventType": "failed", "error": str(error), "detail": getattr(error, "stderr", None)}), flush=True)
            if args.command == "once":
                raise
        if args.command == "once":
            return
        time.sleep(max(30.0, (next_run(now) - datetime.now(UTC)).total_seconds()))


if __name__ == "__main__":
    main()
