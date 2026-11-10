"""Historian rows for Northlake's ODBC gateway: model values plus the vendor's classification, code and metadata.

Values come from the canonical source model, so they agree with every other Northlake feed. A flag window
marks the readings whose interval lies wholly inside it; the most recent readings carry a provisional code
that clears once they are older than the provisional window, which exercises Energy Hippo's same-value recode.
Rows hold the interval end, in UTC and as the campus wall time the gateway's Local timestamps expect.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
CONFIG = Path(__file__).with_name("historian.json")
CLASSIFICATIONS = ("Actual", "Estimated", "Substituted", "Unknown")
COLUMNS = ("Channel", "UtcTimeStamp", "TimeStamp", "Value", "SourceClassification", "SourceCode", "Reader", "Method", "HistorianTag")
# Energy Hippo keeps a code of up to 16 printable ASCII characters (IntervalSourceFacts.MaximumCodeLength).
MAXIMUM_CODE_LENGTH = 16


def load_config(path=CONFIG):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    channels = {c["channel"] for c in config["channels"]}
    keys = [flag["key"] for flag in config["flags"]]
    if len(keys) != len(set(keys)):
        raise ValueError("Historian flag keys must be unique")
    for flag in [*config["flags"], config["provisional"]]:
        if flag["classification"] not in CLASSIFICATIONS:
            raise ValueError(f"Unknown classification: {flag['classification']}")
        code = flag["code"]
        if not 0 < len(code) <= MAXIMUM_CODE_LENGTH or any(not 33 <= ord(c) <= 126 for c in code):
            raise ValueError(f"A code must be 1 to {MAXIMUM_CODE_LENGTH} printable characters: {code!r}")
    for flag in config["flags"]:
        if not set(flag["channels"]) <= channels:
            raise ValueError(f"{flag['key']}: unknown channel")
        if datetime.fromisoformat(flag["startLocal"]) >= datetime.fromisoformat(flag["endLocal"]):
            raise ValueError(f"{flag['key']}: the window must end after it starts")
    return config


def binding(channel):
    """The source-model binding for a historian channel, shaped like the file gateways' bindings."""
    return {"channel": channel["channel"], "profile": "gw_odbc_library_historian", "node": "node_odbc_library",
            "params": {}, "node_params": {}, "interval_minutes": int(channel["intervalMinutes"]),
            "reading_type": "Analog", "timezone": "America/Los_Angeles", "units": "kWh", "description": "", "company": "",
            "meter": {}}


def _window(flag, campus):
    opens = datetime.fromisoformat(flag["startLocal"]).replace(tzinfo=campus).astimezone(UTC)
    closes = datetime.fromisoformat(flag["endLocal"]).replace(tzinfo=campus).astimezone(UTC)
    return opens, closes


def rows(model, config, start, end, now=None):
    """Yield one row per reading with an interval end in (start, end], oldest first.

    `now` is when the historian is written (the range's end by default): readings within the provisional
    window before it carry the provisional code.
    """
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    campus = ZoneInfo(config["timeZone"])
    provisional = config["provisional"]
    provisional_after = (now or end).astimezone(UTC) - timedelta(hours=int(provisional["hours"]))
    for channel in config["channels"]:
        step = timedelta(minutes=int(channel["intervalMinutes"]))
        windows = [(flag, *_window(flag, campus)) for flag in config["flags"] if channel["channel"] in flag["channels"]]
        for reading in model.readings(binding(channel), start, end):
            stamp = reading["timestamp_utc"].astimezone(UTC)
            flag = next((f for f, opens, closes in windows if opens <= stamp - step and stamp <= closes), None)
            if flag is None and stamp > provisional_after:
                flag = provisional
            yield {
                "Channel": channel["channel"],
                "UtcTimeStamp": stamp.strftime("%Y-%m-%d %H:%M:%S"),
                "TimeStamp": stamp.astimezone(campus).strftime("%Y-%m-%d %H:%M:%S"),
                "Value": format(Decimal(str(reading["value"])), "f"),
                "SourceClassification": flag["classification"] if flag else None,
                "SourceCode": flag["code"] if flag else None,
                "Reader": flag["reader"] if flag else None,
                "Method": flag["method"] if flag else None,
                "HistorianTag": channel["historianTag"],
            }


def to_csv(items):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(items)
    return output.getvalue()


def _literal(value, column):
    if value is None:
        return "NULL"
    if column == "Value":
        return value
    return "'" + str(value).replace("'", "''") + "'"


def to_sql(items, table, batch=500):
    """Plain INSERT batches that SQL Server and PostgreSQL both accept, for loading an empty table."""
    statements, pending = [], []
    names = ", ".join(COLUMNS)

    def flush():
        if pending:
            statements.append(f"INSERT INTO {table} ({names}) VALUES\n" + ",\n".join(pending) + ";")
            pending.clear()

    for item in items:
        pending.append("(" + ", ".join(_literal(item[column], column) for column in COLUMNS) + ")")
        if len(pending) == batch:
            flush()
    flush()
    return "\n".join(statements) + ("\n" if statements else "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="ISO time with offset; rows after it")
    parser.add_argument("--end", required=True, help="ISO time with offset; rows up to and including it")
    parser.add_argument("--now", help="ISO time with offset the provisional window counts back from; defaults to --end")
    parser.add_argument("--format", choices=("csv", "sql"), default="csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    from services.sources.generation import create_model

    config = load_config()
    now = datetime.fromisoformat(args.now) if args.now else None
    items = list(rows(create_model(args.source_root), config, datetime.fromisoformat(args.start), datetime.fromisoformat(args.end), now))
    text = to_csv(items) if args.format == "csv" else to_sql(items, config["table"])
    args.output.write_text(text, encoding="utf-8", newline="\n")
    flagged = sum(1 for item in items if item["SourceCode"])
    print(json.dumps({"rows": len(items), "flagged": flagged, "output": str(args.output)}))


if __name__ == "__main__":
    main()
