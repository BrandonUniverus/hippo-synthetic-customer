"""EEM HMR_HDLData export and checked companion binding contract, version 1."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

SCHEMA = "northlake-handheld-bindings-v1"
READERS = {"NLR001": "Alex Morgan", "NLR002": "Sam Rivera", "NLR003": "Casey Lee"}
PACIFIC = ZoneInfo("America/Los_Angeles")
ROUTES = {
    "CRBMW": ("02", "KGAL", "kgal", "neptune", "gw_neptune_river_city_water", "water_keyed", 10, "65"),
    "SCGAS": ("01", "THRM", "therm", "mvrs", "gw_mvrs_sierra_gas", "gas_keyed", 6, "88"),
}
# MVRS RDG codes, as EnergyHippo's MVRS parser reads them. N is a normal read; a read code O or C, a nonzero audit
# code and a skip code each become an HMR log event. Itron publishes no meanings for them, so none are claimed.
MVRS_READ_CODES = ("N", "O", "C")
MVRS_AUDIT_CODES = tuple("0123456789")
MVRS_SKIP_CODES = tuple(f"{number:02d}" for number in range(1, 10))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def ascii_text(value, label, width, *, empty=False):
    if not isinstance(value, str) or (not value and not empty) or len(value) > width or any(not 32 <= ord(c) <= 126 for c in value):
        raise ValueError(f"{label}: expected printable ASCII, at most {width} characters")
    return value


def integer(value, label, maximum=9999999999):
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)) or not 0 <= int(value) <= maximum:
        raise ValueError(f"{label}: expected an unsigned whole number no greater than {maximum}")
    return int(value)


def instant(value):
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None or not 1903 <= result.year <= 9998:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise ValueError("Timestamp needs an explicit UTC offset and a supported date") from None


def native_time(value):
    local = instant(value).astimezone(PACIFIC)
    # Neither native protocol carries a UTC offset. Both folds must be rejected.
    if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
        raise ValueError("Repeated Pacific hour cannot be represented unambiguously in native handheld files")
    if local.microsecond:
        raise ValueError("Native handheld timestamps support whole seconds only")
    return local


def parse_export(raw: bytes) -> list[dict]:
    if not raw or len(raw) > 2_000_000:
        raise ValueError("Export is empty or exceeds 2 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ValueError("Export must be UTF-8 with printable ASCII records") from None
    lines = text.splitlines()
    if len(lines) < 2:
        raise ValueError("Export has no complete envelope")
    if any(len(line) != 126 or any(not 32 <= ord(c) <= 126 for c in line) for line in lines):
        raise ValueError("Every export record must contain exactly 126 printable ASCII characters")
    if lines[0][:3] != "FHD" or lines[-1] != "FTR" + lines[0][3:]:
        raise ValueError("Missing or mismatched file envelope")
    cycle = route = meter = None
    channels, seen, cycles, route_keys = [], set(), set(), set()
    cycle_routes = route_readings = route_meters = meter_readings = 0
    customer_pending = False
    for number, line in enumerate(lines[1:-1], 2):
        kind = line[:3]
        if kind == "CHD" and cycle is None and route is None:
            cycle, cycle_routes = line, 0
            if line[3:5] in cycles:
                raise ValueError(f"Line {number}: duplicate cycle")
            cycles.add(line[3:5])
        elif kind == "RHD" and cycle and route is None and line[3:5] == cycle[3:5]:
            route, route_readings, route_meters = line, 0, 0
            cycle_routes += 1
            if line[3:11] in route_keys:
                raise ValueError(f"Line {number}: duplicate route")
            route_keys.add(line[3:11])
        elif kind in {"CUS", "MTR", "MTS", "RDG", "RFF"} and route and line[3:11] == route[3:11]:
            if kind == "CUS":
                if customer_pending or (meter and meter_readings != integer(meter[11:14], "meter reading count")):
                    raise ValueError(f"Line {number}: incomplete preceding meter")
                meter, customer_pending = None, True
            elif kind == "MTR" and customer_pending:
                meter, meter_readings, customer_pending = line, 0, False
                route_meters += 1
            elif kind == "RDG" and meter:
                item = {"cycle": line[3:5], "wire_route": line[5:11], "meter_id": integer(meter[69:89].strip(), "meter ID", 2147483647),
                        "sequence": integer(meter[61:69], "sequence"), "wire_meter": meter[45:57].strip(),
                        "text_prompt": line[11:15].strip(), "channel": str(integer(line[24:26].strip(), "channel", 99)).zfill(2),
                        "read_direction": line[16], "num_dials": integer(line[26:28], "dials"),
                        "num_decimals": integer(line[28:30], "decimals"), "keyed": line[30],
                        "previous": integer(line[31:41], "previous reading"), "meter_constant": str(Decimal(line[61:67].strip())),
                        "read_type_code": line[76:78]}
                key = (item["meter_id"], item["text_prompt"].upper())
                if key in seen:
                    raise ValueError(f"Line {number}: duplicate physical meter/prompt")
                seen.add(key)
                channels.append(item)
                route_readings += 1
                meter_readings += 1
            elif kind not in {"MTS", "RFF"} or not meter:
                raise ValueError(f"Line {number}: unexpected {kind}")
        elif kind == "RTR" and route and line == "RTR" + route[3:]:
            if customer_pending or not meter or meter_readings != integer(meter[11:14], "meter reading count"):
                raise ValueError(f"Line {number}: incomplete meter")
            if route_readings != integer(route[17:21], "route reading count") or route_meters != integer(route[37:41], "route meter count"):
                raise ValueError(f"Line {number}: route counts do not match records")
            route = meter = None
        elif kind == "CTR" and cycle and route is None and line == "CTR" + cycle[3:]:
            if cycle_routes != integer(cycle[5:9], "cycle route count"):
                raise ValueError(f"Line {number}: cycle counts do not match records")
            cycle = None
        else:
            raise ValueError(f"Line {number}: unexpected or mismatched {kind}")
    if cycle or route or len(cycles) != integer(lines[0][13:15], "file cycle count") or not channels:
        raise ValueError("Incomplete export or mismatched file counts")
    return channels


def validate_binding(raw: bytes, binding: dict, source: dict) -> list[dict]:
    exported = parse_export(raw)
    if binding.get("schema") != SCHEMA or binding.get("purpose") != "controlled-pilot":
        raise ValueError("Only the v1 controlled-pilot binding contract is supported")
    for key in ("environment_id", "database"):
        ascii_text(binding.get(key), key, 120)
    instant(binding.get("verified_at"))
    if binding.get("export_sha256") != digest(raw):
        raise ValueError("Export hash differs from checked binding manifest")
    if binding.get("source") != source:
        raise ValueError("Source release/model/seed/assumptions differs from the mounted source; obtain a matching manifest")
    channels = binding.get("channels")
    if not isinstance(channels, list) or not 1 <= len(channels) <= 2:
        raise ValueError("First slice accepts one or both master channels only")
    selected, seen = [], set()
    for channel in channels:
        route = channel.get("route")
        if route not in ROUTES or route in seen:
            raise ValueError("Unsupported or duplicate master route")
        seen.add(route)
        cycle, prompt, unit, codec, profile, read_key, dials, code = ROUTES[route]
        for field in ("channel_key", "reading_channel_key", "company", "meter_number", "meter_description", "delivery_target"):
            ascii_text(channel.get(field), field, 160)
        if not re.fullmatch(r"[a-z0-9_-]+", channel["delivery_target"]):
            raise ValueError("Invalid delivery target identifier")
        for field in ("meter_id", "reading_pt_id", "usage_pt_id", "hmr_meter_id", "hmr_reading_id", "gateway_id"):
            if not integer(channel.get(field), field, 2147483647):
                raise ValueError(f"Unresolved {field}")
        if channel["reading_pt_id"] == channel["usage_pt_id"]:
            raise ValueError("Register and usage point IDs must differ")
        expected = {"cycle": cycle, "text_prompt": prompt, "display_unit": unit, "usage_unit": unit,
                    "return_format": codec, "gateway_profile": profile, "raw_unit": "Reading"}
        if any(channel.get(k) != v for k, v in expected.items()):
            raise ValueError(f"{route}: route, units, prompt or gateway contract mismatch")
        if Decimal(str(channel.get("meter_constant"))) != 1 or Decimal(str(channel.get("delta_multiplier"))) != 1:
            raise ValueError(f"{route}: both multipliers must be one")
        rt = channel.get("read_type", {})
        if rt != {"key": read_key, "num_dials": dials, "num_decimals": 0, "read_type_code": code,
                  "read_direction": "L", "demand_read": "N", "truncation_factor": 0}:
            raise ValueError(f"{route}: unsupported read type")
        matches = [x for x in exported if x["meter_id"] == channel["meter_id"] and x["text_prompt"] == prompt]
        if len(matches) != 1:
            raise ValueError(f"{route}: physical meter/prompt not found exactly once in export")
        record = matches[0]
        if record["wire_meter"] != channel["meter_number"][:12]:
            raise ValueError(f"{route}: exported meter number differs from checked binding")
        comparisons = {"cycle": cycle, "wire_route": route.zfill(6), "sequence": channel.get("sequence"),
                       "channel": channel.get("channel"), "keyed": "K", "num_dials": dials,
                       "num_decimals": 0, "read_type_code": code, "read_direction": "L"}
        if any(record[k] != v for k, v in comparisons.items()) or Decimal(record["meter_constant"]) != 1:
            raise ValueError(f"{route}: exported configuration differs from checked binding")
        opening = channel.get("opening", {})
        if type(opening.get("value")) is not int:
            raise ValueError("Opening value must be a JSON integer")
        integer(opening.get("value"), "opening value", 10 ** dials - 1)
        native_time(opening.get("observed_at"))
        if opening.get("basis") != "controlled-pilot":
            raise ValueError("Opening must explicitly identify controlled-pilot provenance")
        ascii_text(opening.get("reason"), "opening reason", 300)
        selected.append({**channel, "export_previous": record["previous"], "export_meter": record["wire_meter"]})
    return selected


def validate_observation(channel, observation):
    if observation.get("reader") not in READERS:
        raise ValueError("Select a fictional reader")
    if observation.get("action") not in {"read", "skip"}:
        raise ValueError("Select an actual read or explicit skip")
    timestamp = native_time(observation.get("observed_at"))
    if timestamp < instant(channel["opening"]["observed_at"]):
        raise ValueError("Observation cannot precede the known opening")
    note = ascii_text(observation.get("note", ""), "Visit note", 40 if channel["return_format"] == "mvrs" else 128, empty=True)
    previous = channel["opening"]["value"]
    if observation["action"] == "read":
        value = integer(observation.get("value"), "Register value", 10 ** channel["read_type"]["num_dials"] - 1)
        if value < previous:
            raise ValueError("Rollover/reset is outside this pilot; reading cannot be below opening")
        if timestamp == instant(channel["opening"]["observed_at"]) and value != previous:
            raise ValueError("A reading at the opening instant must equal the known opening")
    else:
        value = previous  # valid native placeholders, never an accepted read
        if not note.strip():
            raise ValueError("An explicit skip requires a visit note")
    result = {"reader": observation["reader"], "action": observation["action"], "observed_at": timestamp.isoformat(),
              "value": value, "note": note, "previous": previous,
              "usage": value - previous if observation["action"] == "read" else None}
    return {**result, **_mvrs_codes(channel, observation)}


def _mvrs_codes(channel, observation):
    """MVRS read, audit and skip codes; an observation saved before codes existed reads as N, 0 and 01."""
    read_code = observation.get("read_code") or "N"
    audit_code = observation.get("audit_code") or "0"
    skip_code = observation.get("skip_code") or "01"
    if channel["return_format"] != "mvrs":
        if (read_code, audit_code, skip_code) != ("N", "0", "01"):
            raise ValueError("Read, audit and skip codes are MVRS fields; a Neptune return carries none")
        return {}
    if read_code not in MVRS_READ_CODES:
        raise ValueError("Select read code N, O or C")
    if audit_code not in MVRS_AUDIT_CODES:
        raise ValueError("The audit code is one digit, 0 for none")
    if skip_code not in MVRS_SKIP_CODES:
        raise ValueError("Select a skip code from 01 to 09")
    if observation["action"] == "skip":
        return {"skip_code": skip_code}
    return {"read_code": read_code, "audit_code": audit_code}
