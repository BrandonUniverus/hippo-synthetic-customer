"""Northlake source production, verification and explicit delivery commands."""
from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .delivery import deliver, load_catalog, selected_records
from .runtime import ArtifactStore, ProducerLock, producer_health
from .web import render_pages


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("A timestamp must include Z or a UTC offset")
    return parsed.astimezone(timezone.utc)


def produce(args, clock=lambda: datetime.now(timezone.utc), wait=time.sleep) -> None:
    from . import generation

    source_root = Path(args.source_root).resolve()
    fingerprint = generation.source_fingerprint(source_root)
    identity = {"version": generation.MODEL_VERSION, "source_hash": fingerprint, "seed": args.seed, "history_start": args.start.isoformat(), "release_id": f"{generation.MODEL_VERSION}-{fingerprint[:12]}-{args.seed}"}
    lock = ProducerLock(Path(args.state))
    store = None
    continuous = args.command == "run" and args.through is None
    try:
        store = ArtifactStore(Path(args.state), identity)
        store.heartbeat("starting", clock(), continuous=continuous)
        first_now = args.through or clock()
        first_cutoff = first_now.replace(minute=first_now.minute // 15 * 15, second=0, microsecond=0)
        bootstrap_cutoff = utc(store.initialize_bootstrap(first_cutoff.isoformat()))
        model = generation.create_model(source_root, args.seed)
        refresh_views = True
        while True:
            if generation.source_fingerprint(source_root) != fingerprint:
                raise ValueError("Source facts or generator code changed while running; stop and use a new release state")
            current = args.through or clock()
            target = current.replace(minute=current.minute // 15 * 15, second=0, microsecond=0)
            cursor = utc(store.completed_through) if store.completed_through else args.start
            if target < cursor:
                raise ValueError("Requested cutoff precedes already published data; use another state directory for a replay")
            changed = False
            while cursor < target:
                if generation.source_fingerprint(source_root) != fingerprint:
                    raise ValueError("Source facts or generator code changed before a generation chunk; use a new release state")
                if cursor < bootstrap_cutoff:
                    next_day = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    through = min(next_day, bootstrap_cutoff, target)
                else:
                    through = min(cursor + timedelta(minutes=15), target)
                store.heartbeat("generating", clock(), continuous=continuous)
                def checked_artifacts():
                    # The final fingerprint check runs before publish_batch commits progress.
                    last_heartbeat = clock()
                    for artifact in generation.iter_artifacts(start=cursor, through=through, seed=args.seed, source_root=source_root, include_acceptance=store.completed_through is None, model=model):
                        now = clock()
                        if (now - last_heartbeat).total_seconds() >= 30:
                            store.heartbeat("generating", now, continuous=continuous)
                            last_heartbeat = now
                        yield artifact
                    if generation.source_fingerprint(source_root) != fingerprint:
                        raise ValueError("Source facts or generator code changed during a generation chunk; progress was not committed")
                batch_id = cursor.isoformat() + "/" + through.isoformat()
                count = store.publish_batch(batch_id, through.isoformat(), checked_artifacts())
                store.heartbeat("generating", clock(), continuous=continuous)
                print(json.dumps({"through": through.isoformat(), "new_artifacts": count}), flush=True)
                cursor = through
                changed = True
            if store.completed_through and (changed or refresh_views):
                render_pages(store.public, source_root, store.records(), store.status())
                store.publish_catalog()
                refresh_views = False
            print(json.dumps(store.status(), sort_keys=True), flush=True)
            if args.command == "init" or args.through:
                store.heartbeat("complete", clock(), continuous=continuous)
                return
            store.heartbeat("idle", clock(), continuous=continuous)
            wait(args.poll_seconds)
    except BaseException as error:
        if store:
            store.heartbeat("stopped" if isinstance(error, KeyboardInterrupt) else "failed", clock(), continuous=continuous)
        raise
    finally:
        if store:
            store.close()
        lock.close()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="northlake-sources")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("init", "run"):
        command = commands.add_parser(name, help="Generate through the latest completed quarter-hour" if name == "init" else "Generate and continue producing completed quarter-hours")
        command.add_argument("--state", default=os.environ.get("NORTHLAKE_STATE", "/state"))
        command.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
        command.add_argument("--seed", type=int, default=104729)
        command.add_argument("--start", type=utc, default=utc("2023-12-01T08:00:00Z"))
        command.add_argument("--through", type=utc, help="Fixed cutoff; run exits after this cutoff instead of polling")
        command.add_argument("--poll-seconds", type=int, default=60)
    for name in ("status", "verify", "health"):
        command = commands.add_parser(name)
        command.add_argument("--state", default=os.environ.get("NORTHLAKE_STATE", "/state"))
        if name == "health":
            command.add_argument("--max-age-seconds", type=int, default=180)
            command.add_argument("--max-lag-seconds", type=int, default=1800)
    command = commands.add_parser("deliver", help="Explicitly copy selected published files; never runs with the producer")
    location = command.add_mutually_exclusive_group(required=True)
    location.add_argument("--state", type=Path)
    location.add_argument("--url", help="HTTP base of a source service, e.g. http://localhost:18081")
    command.add_argument("--destination", type=Path, required=True)
    command.add_argument("--source")
    command.add_argument("--provider")
    command.add_argument("--kind")
    command.add_argument("--artifact", help="Representation: nativeXml, bif, providerCsv, pdf, manifest, extractedJson, json or schema")
    window = command.add_mutually_exclusive_group()
    window.add_argument("--day")
    window.add_argument("--month")
    command.add_argument("--case")
    command.add_argument("--all", action="store_true", help="Explicitly select every ordinary file")
    command.add_argument("--include-nonordinary", "--include-acceptance", dest="include_acceptance", action="store_true", help="Explicitly include acceptance fixtures and alternative bill representations")
    command.add_argument("--flat", action="store_true", help="Flatten filenames; collisions are rejected")
    command.add_argument("--replay", action="store_true", help="Explicitly redeliver previously acknowledged files")
    command.add_argument("--follow", action="store_true", help="Opt in to continuous selected delivery as new files arrive")
    command.add_argument("--poll-seconds", type=int, default=60)
    return result


def main(argv=None, *, wait=time.sleep) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    previous_sigterm = None
    try:
        if args.command in {"init", "run"}:
            if threading.current_thread() is threading.main_thread():
                def stop_producer(signum, frame):
                    signal.signal(signal.SIGTERM, signal.SIG_IGN)
                    raise KeyboardInterrupt
                previous_sigterm = signal.signal(signal.SIGTERM, stop_producer)
            if args.poll_seconds < 1:
                arguments.error("--poll-seconds must be positive")
            produce(args)
        elif args.command == "health":
            output = producer_health(Path(args.state), max_age_seconds=args.max_age_seconds, max_lag_seconds=args.max_lag_seconds)
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0 if output["ok"] else 1
        elif args.command in {"status", "verify"}:
            store = ArtifactStore(Path(args.state))
            try:
                output = store.status() if args.command == "status" else store.verify()
                print(json.dumps(output, indent=2, sort_keys=True))
                if args.command == "verify" and not output["ok"]:
                    return 1
            finally:
                store.close()
        else:
            if not args.all and not any((args.source, args.provider, args.kind, args.artifact, args.day, args.month, args.case)):
                arguments.error("Choose a source/provider/kind/day/month/case, or explicitly use --all")
            if args.follow and args.replay:
                arguments.error("--follow and --replay cannot be combined")
            if args.poll_seconds < 1:
                arguments.error("--poll-seconds must be positive")
            while True:
                catalog = load_catalog(state=args.state, url=args.url)
                records = selected_records(catalog["artifacts"], source=args.source, provider=args.provider, kind=args.kind, artifact=args.artifact, day=args.day, month=args.month, case=args.case, include_acceptance=args.include_acceptance)
                output = deliver(records, args.destination, state=args.state, url=args.url, flat=args.flat, input_layout=bool(args.source), replay=args.replay)
                print(json.dumps(output, indent=2, sort_keys=True), flush=True)
                if not args.follow:
                    break
                wait(args.poll_seconds)
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}), flush=True)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if previous_sigterm is not None:
            signal.signal(signal.SIGTERM, previous_sigterm)

