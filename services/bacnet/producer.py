"""Publish current, closed-interval thermal values for the BACnet source."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, time as clock_time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from services.sources.generation import create_model, source_fingerprint
from services.sources.runtime import ProducerLock, atomic_write

UTC = timezone.utc
CAMPUS = ZoneInfo("America/Los_Angeles")
CONFIG = Path(__file__).with_name("bindings.json")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
EVENT_STATES = ("normal", "fault", "offnormal", "high-limit", "low-limit")
RELIABILITIES = ("no-fault-detected", "no-sensor", "over-range", "under-range", "open-loop",
                 "shorted-loop", "no-output", "unreliable-other")


def scenarios(config):
    """Validate the status calendar: each scenario is a recurring window in campus local time."""
    keys = {o["valueKey"] for device in config["devices"] for o in device["objects"]}
    items = config.get("statusScenarios", [])
    if len({s["key"] for s in items}) != len(items):
        raise ValueError("Status scenario keys must be unique")
    for scenario in items:
        if ("weekday" in scenario) == ("monthDay" in scenario):
            raise ValueError(f"{scenario['key']}: give exactly one of weekday or monthDay")
        if "weekday" in scenario and scenario["weekday"] not in WEEKDAYS:
            raise ValueError(f"{scenario['key']}: unknown weekday")
        if "monthDay" in scenario and not 1 <= scenario["monthDay"] <= 28:
            raise ValueError(f"{scenario['key']}: monthDay must be 1 to 28")
        if clock_time.fromisoformat(scenario["startLocal"]) >= clock_time.fromisoformat(scenario["endLocal"]):
            raise ValueError(f"{scenario['key']}: the window must end after it starts")
        if not scenario["valueKeys"] or not set(scenario["valueKeys"]) <= keys:
            raise ValueError(f"{scenario['key']}: unknown value key")
        if scenario.get("eventState", "normal") not in EVENT_STATES or scenario.get("reliability", "no-fault-detected") not in RELIABILITIES:
            raise ValueError(f"{scenario['key']}: unknown event state or reliability")
    return items


def window_start(scenario, interval_end, minutes):
    """UTC start of the scenario window that holds the whole interval, else None.

    The interval's local start date picks the day, so a window keeps its local clock time
    across daylight-saving changes.
    """
    start = interval_end - timedelta(minutes=minutes)
    day = start.astimezone(CAMPUS).date()
    if "weekday" in scenario and WEEKDAYS[day.weekday()] != scenario["weekday"]:
        return None
    if "monthDay" in scenario and day.day != scenario["monthDay"]:
        return None
    opens = datetime.combine(day, clock_time.fromisoformat(scenario["startLocal"]), CAMPUS).astimezone(UTC)
    closes = datetime.combine(day, clock_time.fromisoformat(scenario["endLocal"]), CAMPUS).astimezone(UTC)
    return opens if opens <= start and interval_end <= closes else None


def build_values(model, config, now):
    """Closed-interval values with each object's BACnet status.

    A scenario window sets the status of its objects. With "hold" it keeps reporting the value
    of the interval that ended when the window opened: an overridden, out-of-service or failed
    input no longer follows the sensor. A configured high limit raises the alarm whenever the
    reported value is above it.
    """
    values = _measure(model, config, now)
    calendar = scenarios(config)
    objects = {o["valueKey"]: o for device in config["devices"] for o in device["objects"]}
    held = {}
    for key, item in values.items():
        point = objects[key]
        end = datetime.fromisoformat(item["intervalEndUtc"])
        status = {"overridden": False, "outOfService": False, "eventState": "normal", "reliability": "no-fault-detected"}
        active = [(scenario, opened) for scenario in calendar if key in scenario["valueKeys"]
                  for opened in [window_start(scenario, end, point["intervalMinutes"])] if opened is not None]
        for scenario, opened in active:
            if scenario.get("hold"):
                if opened not in held:
                    held[opened] = _measure(model, config, opened)
                item["value"] = held[opened][key]["value"]
        if point.get("highLimit") is not None and item["value"] > float(point["highLimit"]):
            status["eventState"] = "high-limit"
        for scenario, _ in active:
            status.update({name: scenario[name] for name in ("overridden", "outOfService", "eventState", "reliability") if name in scenario})
            status["scenario"] = scenario["key"]
        status["inAlarm"] = status["eventState"] != "normal"
        status["fault"] = status["reliability"] != "no-fault-detected"
        item["status"] = status
    return values


def _measure(model, config, now):
    """Energy values cover the last completed native interval; rates cover that hour."""
    if now.tzinfo is None:
        raise ValueError("The source clock must be timezone-aware")
    now = now.astimezone(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    quarter = now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0)
    assumptions = {k: Decimal(v) for k, v in config["assumptions"].items()}
    for key in ("chilledWaterDistributionLossFraction", "steamDistributionLossFraction", "condensateReturnFraction"):
        if not 0 <= assumptions[key] < 1:
            raise ValueError(f"Invalid thermal fraction: {key}")
    if assumptions["condensatePoundsPerGallon"] <= 0:
        raise ValueError("Condensate density must be positive")
    science = model.meter_value("ntp_science_center_chilled_water", "chilled_water_ton_hours", hour, 60)
    recreation = model.meter_value("ntp_recreation_center_chilled_water", "chilled_water_ton_hours", hour, 60)
    steam_meters = [m["id"] for a in model.accounts.values() if a["id"].startswith("ntp_")
                    for m in a.get("meters", []) if any(c.get("unit") == "klb" for c in m.get("channels", []))]
    if not steam_meters:
        raise ValueError("No thermal steam delivery meters in source model")
    steam_delivered = sum((model.meter_value(m, "steam_klb", hour, 60) for m in steam_meters), Decimal(0))
    plant_chw = (science + recreation) / (1 - assumptions["chilledWaterDistributionLossFraction"])
    plant_steam = steam_delivered / (1 - assumptions["steamDistributionLossFraction"])
    condensate = plant_steam * assumptions["condensateReturnFraction"] / assumptions["condensatePoundsPerGallon"]
    pressure = assumptions["steamHeaderMeanPsig"] + assumptions["steamHeaderVariationPsig"] * Decimal(str(math.sin(quarter.timestamp() / 86400)))
    values = {
        "science_chw_ton_hours": science, "science_chw_tons": science,
        "recreation_chw_ton_hours": recreation, "recreation_chw_tons": recreation,
        "plant_chw_ton_hours": plant_chw, "plant_chw_tons": plant_chw,
        "plant_steam_klb": plant_steam, "plant_steam_lb_per_hour": plant_steam * 1000,
        "plant_steam_header_psig": pressure, "plant_condensate_kgal": condensate,
    }
    return {key: {"value": float(value.quantize(Decimal("0.000001"))),
                  "intervalEndUtc": (quarter if key == "plant_steam_header_psig" else hour).isoformat()}
            for key, value in values.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--clock", help="ISO timestamp for deterministic offline verification")
    args = parser.parse_args()
    if args.health:
        snapshot = json.loads((args.state / "values.json").read_text())
        age = (datetime.now(UTC) - datetime.fromisoformat(snapshot["generatedAtUtc"])).total_seconds()
        print(json.dumps({"fresh": 0 <= age <= 120, "age_seconds": age}))
        raise SystemExit(0 if 0 <= age <= 120 else 1)
    raw = CONFIG.read_bytes()
    config = json.loads(raw)
    model = create_model(args.source_root)
    fingerprint = source_fingerprint(args.source_root)
    config_hash = hashlib.sha256(raw).hexdigest()
    identity = {"version": config["version"], "sourceHash": fingerprint, "configHash": config_hash, "seed": 104729}
    args.state.mkdir(parents=True, exist_ok=True)
    lock = ProducerLock(args.state)
    try:
        identity_path = args.state / "identity.json"
        if identity_path.exists() and json.loads(identity_path.read_text()) != identity:
            raise ValueError("BACnet source identity changed; use a new source state directory")
        atomic_write(identity_path, json.dumps(identity, sort_keys=True).encode())
        while True:
            if CONFIG.read_bytes() != raw or source_fingerprint(args.source_root) != fingerprint:
                raise ValueError("Source facts changed while BACnet producer was running")
            now = datetime.fromisoformat(args.clock) if args.clock else datetime.now(UTC)
            values = build_values(model, config, now)
            snapshot = {**identity, "generatedAtUtc": now.isoformat(), "values": values}
            atomic_write(args.state / "values.json", json.dumps(snapshot, sort_keys=True).encode())
            print(json.dumps({"eventType": "sample", "generatedAtUtc": now.isoformat(), "values": len(values)}), flush=True)
            if args.once:
                return
            time.sleep(30)
    finally:
        lock.close()


if __name__ == "__main__":
    main()
