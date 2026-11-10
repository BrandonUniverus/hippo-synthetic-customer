import argparse
import json
import os
from pathlib import Path

from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Northlake controlled handheld rounds")
    parser.add_argument("--state", type=Path, default=Path(os.environ.get("NORTHLAKE_HANDHELD_STATE", ".handheld")))
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18082)
    fixtures = sub.add_parser("fixtures")
    fixtures.add_argument("--output", type=Path, required=True)
    sub.add_parser("status")
    delivery = sub.add_parser("deliver")
    delivery.add_argument("--round", required=True)
    delivery.add_argument("--target", required=True)
    delivery.add_argument("--targets", type=Path, required=True)
    delivery.add_argument("--replay", action="store_true")
    remote = sub.add_parser("sync")
    remote.add_argument("--url", required=True)
    remote.add_argument("--round", required=True)
    remote.add_argument("--target", required=True)
    remote.add_argument("--targets", type=Path, required=True)
    remote.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.command == "fixtures":
        from .fixtures import write_fixtures
        write_fixtures(args.output)
    elif args.command == "serve":
        from .server import run
        run(args.state, Path(os.environ.get("NORTHLAKE_SOURCE_STATE", ".sources")), args.host, args.port)
    elif args.command == "status":
        print(json.dumps(Store(args.state).list(), indent=2))
    elif args.command == "deliver":
        targets = json.loads(args.targets.read_text(encoding="utf-8"))
        print(json.dumps(Store(args.state).deliver(args.round, targets, args.target, args.replay), indent=2))
    elif args.command == "sync":
        from .remote import sync
        targets = json.loads(args.targets.read_text(encoding="utf-8"))
        print(json.dumps(sync(args.url, args.round, targets, args.target, replay=args.replay), indent=2))


if __name__ == "__main__":
    main()
