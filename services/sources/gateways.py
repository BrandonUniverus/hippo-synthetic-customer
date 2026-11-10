"""Native gateway files from authoritative source readings; no EEM or database writes.

Partitions contain interval ends in (start, end]. Each binary/XML delivery is
self-contained. Published bytes are immutable; delivery/state belongs to service.py.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import re
import struct
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import yaml

UTC = timezone.utc
PACIFIC = ZoneInfo("America/Los_Angeles")
FIG_FORMATS = ("FIG", "SIEMANSREPORT", "MEDIATOR", "EATON", "XML", "FIXEDNETWORKS", "CMEP")
FILE_PROFILES = {
    "gw_acquisuite_student_electric": "ACQUISUITE",
    "gw_mv90_valley_mdef": "MDEF",
    "gw_mv90_helios_mv9": "MV9",
    "gw_spinwave_science_lab": "SPINWAVE",
    "gw_fig_multi_format": "FIG",
    "gw_fig_fixed_network_submeters": "FIXEDNETWORKS",
    "gw_fig_ridgeline_scada": "FIG",
}
PROVIDERS = {
    "gw_acquisuite_student_electric": "valley_electric_district",
    "gw_mv90_valley_mdef": "valley_electric_district",
    "gw_mv90_helios_mv9": "helios_onsite_solar",
    "gw_fig_multi_format": "river_city_utilities",
    "gw_fig_ridgeline_scada": "ridgeline_wind",
}


def gateway_bindings(source_root):
    """Expand only direct file inputs; never return aggregates or generated points."""
    root = Path(source_root)
    point_doc = yaml.safe_load((root / "implementation/stage-2-hierarchy/04-points.yaml").read_text(encoding="utf-8"))
    points = {row["key"]: row for row in point_doc["records"]}
    gateway_doc = yaml.safe_load((root / "implementation/stage-3-gateways-and-data/02-gateways.yaml").read_text(encoding="utf-8"))
    bindings = []
    for profile in gateway_doc["records"]:
        if profile["key"] not in FILE_PROFILES:
            continue
        for node in profile["Nodes"]:
            for entry in node.get("Points", []):
                expanded = []
                if entry.get("pointTemplate"):
                    match = re.fullmatch(r"(.+) for (\w+) in ((?:\d+\.\.\d+)(?:,\d+\.\.\d+)*)", entry["channelPattern"])
                    if not match:
                        raise ValueError(f"Unsupported channel pattern: {entry['channelPattern']}")
                    pattern, variable, ranges = match.groups()
                    numbers = []
                    for span in ranges.split(","):
                        first, last = span.split("..")
                        numbers.extend(str(n).zfill(len(first)) if first.startswith("0") else str(n)
                                       for n in range(int(first), int(last) + 1))
                    if len(numbers) != entry["count"] or len(numbers) != len(set(numbers)):
                        raise ValueError(f"Invalid template range: {entry['channelPattern']}")
                    for number in numbers:
                        replacements = {variable: number}
                        params = dict(field.split(": ", 1) for field in entry.get("Point Parameters pattern", "").split(", ") if field)
                        expanded.append({"channel": pattern.format(**replacements),
                                         "Point Parameters": {key: value.format(**replacements) for key, value in params.items()}})
                else:
                    expanded.append(entry)
                for item in expanded:
                    point = points[item["channel"]]
                    definition = point["Point Definition"]
                    if definition["Reading Type"] not in ("Analog", "Digital"):
                        raise ValueError(f"Not a direct input: {item['channel']}")
                    bindings.append({
                        "channel": item["channel"], "profile": profile["key"], "node": node["key"],
                        "params": dict(item.get("Point Parameters", {})),
                        "node_params": dict(node.get("Node Parameters", {})),
                        "interval_minutes": int(definition["Archive Interval"]),
                        "reading_type": definition["Reading Type"], "timezone": "America/Los_Angeles",
                        "units": definition.get("Units", ""), "description": definition["Description"],
                        "company": entry.get("Company", ""), "meter": point.get("Meter", {}),
                    })
    if len({row["channel"] for row in bindings}) != len(bindings):
        raise ValueError("A source channel is bound more than once")
    return bindings


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Source timestamps must include a UTC offset")
    return value.astimezone(UTC)


def _iso(value):
    return _utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _number(value):
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError("Gateway readings must be finite")
    return format(value, "f")


def _csv(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _runs(rows, interval):
    run = []
    for row in rows:
        if run and row[0] - run[-1][0] != timedelta(minutes=interval):
            yield run
            run = []
        run.append(row)
    if run:
        yield run


def _record(code, endian):
    record = bytearray(b" " * 216)
    struct.pack_into(endian + "HH", record, 0, 216, code)
    return record


def _text(record, offset, length, value):
    value = str(value).encode("ascii")
    if len(value) > length:
        raise ValueError(f"Binary field exceeds {length} bytes: {value!r}")
    record[offset:offset + length] = value.ljust(length, b" ")


def encode_mv90(format_name, recorder, channels):
    """Encode {channel_number: [(UTC interval end, value), ...]} independently.

    Engineering values are IEEE float32 for both dialects. MV9's record words
    are big-endian, but its engineering floats are little-endian in EEM's reader.
    A fresh channel header starts each contiguous run, so gaps stay gaps.
    """
    if format_name not in ("MDEF", "MV9"):
        raise ValueError(f"Unknown binary dialect: {format_name}")
    mv9 = format_name == "MV9"
    endian, date_format = (">", "%m%d%y%H%M") if mv9 else ("<", "%Y%m%d%H%M")
    all_rows = [row for rows in channels.values() for row in rows]
    if not all_rows:
        return b""
    if any(stamp.second or stamp.microsecond or stamp.minute % 15 for stamp, _ in all_rows):
        raise ValueError("MV90 source intervals must end on whole fifteen-minute boundaries")
    first, last = min(row[0] for row in all_rows), max(row[0] for row in all_rows)
    if mv9 and not (1970 <= first.year <= last.year <= 2069):
        raise ValueError("MV9's two-digit year supports 1970 through 2069")
    header = _record(1, endian)
    _text(header, 4, 20, recorder)
    _text(header, 24, 20, "NORTHLAKE SYNTHETIC")
    _text(header, 111, 4, f"{len(channels):04d}")
    _text(header, 119, 10 if mv9 else 12, first.strftime(date_format))
    _text(header, 129 if mv9 else 131, 10 if mv9 else 12, last.strftime(date_format))
    _text(header, 110 if mv9 else 143, 1, "N")
    result = bytearray(header)
    for channel, rows in sorted(channels.items()):
        for run in _runs(rows, 15):
            header = _record(10, endian)
            _text(header, 4, 20, recorder)
            # The legacy metadata recorder field is narrower than the customer
            # key EEM actually matches. Preserve the complete identity at 4:24.
            _text(header, 24, 14, recorder[:14])
            _text(header, 44, 12, f"SYN-{channel:02d}")
            _text(header, 56, 10 if mv9 else 12, run[0][0].strftime(date_format))
            _text(header, 66 if mv9 else 68, 10 if mv9 else 12, run[-1][0].strftime(date_format))
            _text(header, 76 if mv9 else 80, 10 if mv9 else 12, run[0][0].strftime(date_format))
            _text(header, 177, 2, "04")
            _text(header, 193, 2, "00")
            if mv9:
                _text(header, 86, 1, "N")
                _text(header, 87, 2, "01")
                _text(header, 89, 2, f"{channel:02d}")
                _text(header, 91, 2, "07")
                _text(header, 93, 2, "NN")
                _text(header, 126, 10, "0000001000")
                _text(header, 136, 10, "0000100000")
                _text(header, 146, 10, "0000000000")
                _text(header, 156, 10, "0000000000")
                _text(header, 167, 10, "0000000000")
                _text(header, 203, 6, run[0][0].strftime("%m%d%y"))
                _text(header, 215, 1, "E")
            else:
                _text(header, 93, 2, "01")
                struct.pack_into("<H", header, 95, channel)
                _text(header, 97, 2, "07")
                _text(header, 99, 2, "NN")
                _text(header, 126, 10, "000001.00")
                struct.pack_into("<H", header, 211, 1)
            result.extend(header)
            for offset in range(0, len(run), 48):
                record = _record(1000 if mv9 else 1010, endian)
                record[24:] = b"\x7f\xff" * 96 if mv9 else b"\xff\x7f\xff\x7f" * 48
                for index, (_, value) in enumerate(run[offset:offset + 48]):
                    numeric = float(value)
                    if not math.isfinite(numeric):
                        raise ValueError("Binary readings must be finite")
                    struct.pack_into("<f", record, 24 + index * 4, numeric)
                result.extend(record)
    return bytes(result)


def encode_fig(format_name, series):
    """Serialize [(binding, [(UTC timestamp, final value), ...])]."""
    if format_name not in FIG_FORMATS:
        raise ValueError(f"Unsupported FIG format: {format_name}")
    prepared = []
    for binding, rows in series:
        params = binding["params"]
        multiplier = Decimal(str(params.get("Multiplier", 1)))
        if multiplier == 0:
            raise ValueError("A zero point multiplier cannot encode an authoritative value")
        offset = timedelta(minutes=int(params.get("OffsetTimeMinutes", 0)))
        prepared.append((binding, [(stamp - offset, Decimal(str(value)) / multiplier) for stamp, value in rows]))
    if format_name in ("XML", "FIXEDNETWORKS"):
        root = ET.Element("DataRecords" if format_name == "XML" else "MeterReadingDocument")
        for binding, rows in prepared:
            alias = binding["params"]["Point Alias"]
            if format_name == "XML":
                for stamp, value in rows:
                    record = ET.SubElement(root, "Record")
                    for name, text in (("PointID", alias), ("TimeStamp", _iso(stamp)), ("Value", _number(value)), ("Status", "0")):
                        ET.SubElement(record, name).text = text
            else:
                channel = ET.SubElement(root, "Channel", IntervalLength=str(binding["interval_minutes"]), PressureCompensationFactor="1")
                ET.SubElement(channel, "ChannelID", EndPointChannelID=alias)
                for run in _runs(rows, binding["interval_minutes"]):
                    interval_set = ET.SubElement(channel, "ContiguousIntervalSet")
                    ET.SubElement(interval_set, "TimePeriod", StartTime=_iso(run[0][0]), EndTime=_iso(run[-1][0]))
                    for _, value in run:
                        ET.SubElement(interval_set, "Reading", Value=_number(value))
        return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    if format_name == "FIG":
        return _csv([["BEGINDATA"], *[[binding["params"]["Point Alias"], stamp.strftime("%Y-%m-%d %H:%M:%S"), _number(value)]
                                     for binding, rows in prepared for stamp, value in rows], ["ENDDATA"]])
    if format_name == "CMEP":
        records = []
        for binding, rows in prepared:
            params = binding["params"]
            for run in _runs(rows, binding["interval_minutes"]):
                header = ["MEPMD01", "NORTHLAKE", "", "", "", "", "", f"{params['Point Alias']}|{params.get('Channel', '')}",
                          "", "", params.get("UOM", ""), "1", str(binding["interval_minutes"]), str(len(run))]
                for stamp, value in run:
                    header.extend([stamp.strftime("%Y%m%d%H%M"), "0", _number(value)])
                records.append(header)
        return _csv(records)
    if format_name == "EATON":
        # Eaton's four-part aliases are a fixed contract, not arbitrary CSV headers.
        if any(len(binding["params"]["Point Alias"].split("_", 3)) != 4 for binding, _ in prepared):
            raise ValueError("EATON compatibility requires a four-part underscore alias")
        records = []
        for binding, rows in prepared:
            site, device, meter, field = binding["params"]["Point Alias"].split("_", 3)
            if records:
                raise ValueError("EATON compatibility encodes one source alias per artifact")
            records.append(["Date", "Time", "Site", "Device", "Meter", field])
            records.extend([[stamp.strftime("%Y-%m-%d"), stamp.strftime("%H:%M:%S"), site, device, meter, _number(value)] for stamp, value in rows])
        return _csv(records)
    stamps = sorted({stamp for _, rows in prepared for stamp, _ in rows})
    values = [dict(rows) for _, rows in prepared]
    aliases = [binding["params"]["Point Alias"] for binding, _ in prepared]
    if format_name == "MEDIATOR":
        return _csv([["timestamp", *aliases], *[[stamp.strftime("%Y-%m-%dT%H:%M:%S"),
                                               *[_number(value[stamp]) if stamp in value else "" for value in values]] for stamp in stamps]])
    keys = [f"Point_{index + 1}" for index in range(len(aliases))]
    return _csv([["Northlake synthetic Siemens report"], *[[key + ":", alias] for key, alias in zip(keys, aliases)],
                 ["<>Date", "Time", *keys], *[[stamp.strftime("%Y-%m-%d"), stamp.strftime("%H:%M:%S"),
                                             *[_number(value[stamp]) if stamp in value else "" for value in values]] for stamp in stamps]])


def encode_partition(model, start_utc, end_utc, *, compatibility=False):
    """Yield immutable artifact dictionaries; this does not publish or write them."""
    start, end = _utc(start_utc), _utc(end_utc)
    if end <= start:
        raise ValueError("A partition end must follow its start")
    bindings = getattr(model, "bindings", None)
    if bindings is None:
        bindings = gateway_bindings(model.root)
    groups = defaultdict(list)
    for binding in bindings:
        profile = binding["profile"]
        if profile not in FILE_PROFILES:
            continue
        rows = []
        for item in model.readings(binding, start, end):
            stamp, value = _utc(item["timestamp_utc"]), item["value"]
            if not start < stamp <= end:
                raise ValueError(f"Reading outside partition: {binding['channel']}")
            _number(value)
            if rows and stamp <= rows[-1][0]:
                raise ValueError(f"Unordered or duplicate reading: {binding['channel']}")
            rows.append((stamp, value))
        if not rows:
            continue
        format_name = FILE_PROFILES[profile]
        group = (profile, binding["node"])
        if format_name in ("MDEF", "MV9"):
            group = (profile, binding["params"]["RecorderID"])
        elif format_name == "ACQUISUITE":
            group = (profile, f"{binding['node_params']['Serial Number']}_{binding['params']['DeviceID']}")
        groups[group].append((binding, rows))
    window = start.strftime("%Y%m%dT%H%M%SZ") + "_" + end.strftime("%Y%m%dT%H%M%SZ")
    for (profile, group), series in sorted(groups.items()):
        format_name = FILE_PROFILES[profile]
        formats = FIG_FORMATS if compatibility and profile == "gw_fig_multi_format" else (format_name,)
        for selected_format in formats:
            relative_input = f"{group}_{window}"
            if selected_format == "ACQUISUITE":
                stamps = sorted({stamp for _, rows in series for stamp, _ in rows})
                columns = {int(binding["params"]["Row Number"]): dict(rows) for binding, rows in series}
                records = [["'" + stamp.strftime("%Y-%m-%d %H:%M:%S") + "'", *[
                    _number(columns[index][stamp]) if index in columns and stamp in columns[index] else ""
                    for index in range(1, max(columns) + 1)]] for stamp in stamps]
                content = gzip.compress(_csv(records), mtime=0)
                relative_input += ".log.gz"
            elif selected_format in ("MDEF", "MV9"):
                content = encode_mv90(selected_format, group, {int(binding["params"]["Channel"]): rows for binding, rows in series})
                relative_input += ".mv9" if selected_format == "MV9" else ".mde"
            elif selected_format == "SPINWAVE":
                devices = defaultdict(list)
                for binding, rows in series:
                    devices[binding["params"]["Device Address"]].append((binding, rows))
                records = [["utctime", "device", "channel0", "channel1", "channel2"]]
                for device, device_series in sorted(devices.items()):
                    columns = {int(binding["params"]["Channel Number"]): dict(rows) for binding, rows in device_series}
                    for stamp in sorted({stamp for rows in columns.values() for stamp in rows}):
                        records.append([stamp.strftime("%Y-%m-%d %H:%M:%S"), device, *[
                            _number(columns[index][stamp]) if index in columns and stamp in columns[index] else ""
                            for index in range(0, max(columns) + 1)]])
                content = _csv(records)
                relative_input = series[0][0]["node_params"]["Folder Name"] + "/" + relative_input + ".csv"
            else:
                content = encode_fig(selected_format, series)
                relative_input += ".xml" if selected_format in ("XML", "FIXEDNETWORKS") else ".csv"
            required = {"TimeStampType": "utc"}
            if selected_format in ("MDEF", "MV9"):
                required = {"Node.TimeStampType": "utc"}
            elif selected_format in ("ACQUISUITE", "SPINWAVE"):
                required = {}
            if selected_format in FIG_FORMATS or selected_format in ("MDEF", "MV9"):
                required["Format"] = selected_format
            offsets = {str(binding["params"].get("OffsetTimeMinutes", 0)) for binding, _ in series}
            if selected_format in FIG_FORMATS and offsets != {"0"}:
                required["Point.OffsetTimeMinutes"] = ",".join(sorted(offsets))
            prefix = "compatibility" if compatibility and profile == "gw_fig_multi_format" else "gateways"
            artifact_path = f"{prefix}/{profile}/{selected_format.lower()}/{relative_input}"
            yield {"path": artifact_path, "content": content, "media_type": "application/octet-stream",
                   "metadata": {"kind": "gateway", "feed": profile, "source": profile, "provider": PROVIDERS.get(profile, "northlake_university"),
                                "period_start": _iso(start), "period_end": _iso(end), "case": "normal",
                                "ordinary_delivery": prefix != "compatibility", "delivery_path": relative_input,
                                "format": selected_format,
                                "start": _iso(start), "end": _iso(end), "records": sum(len(rows) for _, rows in series),
                                "channels": [binding["channel"] for binding, _ in series], "input_path": relative_input,
                                "requiredSettings": required, "sha256": hashlib.sha256(content).hexdigest(),
                                "compatibilityOnly": prefix == "compatibility", "timestampConvention": "interval-end"},
                   "_bindings": [binding for binding, _ in series], "_expected": series}


def acceptance_samples(source_root):
    """Return the unchanged three start-stamped customer acceptance deliveries."""
    bindings = [binding for binding in gateway_bindings(source_root)
                if binding["profile"] == "gw_acquisuite_student_electric" and binding["params"]["DeviceID"] == "STUDENT"]
    root = Path(source_root) / "documents/intake-package/sample-data/acquisuite"
    expected = json.loads((root / "expected-results.json").read_text(encoding="utf-8"))
    for case in ("complete", "gap", "backfill"):
        path = root / case / "ASQVED01_STUDENT.log"
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected["cases"][case]["sha256"]:
            raise ValueError(f"Immutable AcquiSuite {case} sample hash changed")
        rows = list(csv.reader(io.StringIO(content.decode("utf-8"))))
        series = [(binding, [(datetime.strptime(row[0], "'%Y-%m-%d %H:%M:%S'").replace(tzinfo=UTC),
                              Decimal(row[int(binding["params"]["Row Number"])])) for row in rows]) for binding in bindings]
        yield {"path": f"acceptance/acquisuite/{case}/{path.name}", "content": content, "media_type": "text/plain",
               "metadata": {"kind": "acceptance", "feed": "gw_acquisuite_student_electric", "source": "gw_acquisuite_student_electric",
                            "provider": "valley_electric_district", "case": case, "ordinary_delivery": False,
                            "delivery_path": path.name, "period_start": "2024-01-15T08:00:00Z", "period_end": "2024-01-16T08:00:00Z",
                            "input_path": path.name, "format": "ACQUISUITE", "sha256": digest,
                            "records": len(rows) * len(bindings), "channels": [binding["channel"] for binding in bindings],
                            "requiredSettings": {}, "timestampConvention": "interval-start", "expected": expected["cases"][case]},
               "_bindings": bindings, "_expected": series}


def encode_compatibility(model, start_utc, end_utc):
    """Only the seven alternate Cedar Row artifacts, without redelivering feeds."""
    bindings = getattr(model, "bindings", None)
    if bindings is None:
        bindings = gateway_bindings(model.root)
    source = SimpleNamespace(bindings=[binding for binding in bindings if binding["profile"] == "gw_fig_multi_format"],
                             readings=model.readings)
    yield from encode_partition(source, start_utc, end_utc, compatibility=True)


def write_fixture_manifest(artifacts, output_directory):
    """Write explicit offline collector inputs and expectations, never delivery files.

    Synthetic integer IDs exist only in this manifest. Values originate in the
    authoritative model before serialization; C# checks the real decoder output.
    """
    root = Path(output_directory)
    root.mkdir(parents=True, exist_ok=True)
    cases = []
    for index, artifact in enumerate(artifacts):
        bindings = artifact.get("_bindings")
        if not bindings:
            continue
        case_id = f"{index:04d}-{artifact['metadata']['format'].lower()}"
        case_root = root / case_id
        path = case_root / "source" / artifact["metadata"]["input_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(artifact["content"])
        nodes = {key: number + 1 for number, key in enumerate(sorted({binding["node"] for binding in bindings}))}
        point_ids = {binding["channel"]: number + 1 for number, binding in enumerate(bindings)}
        runtime = {"gatewayId": 1, "gatewayName": "Northlake offline source proof", "gatewayGuid": "northlake-offline",
                   "nodes": [], "points": []}
        for key, node_id in nodes.items():
            binding = next(binding for binding in bindings if binding["node"] == key)
            values = {name: str(value) for name, value in binding["node_params"].items()}
            values.update({"GwNodeID": str(node_id), "IsEnabled": "1", "TimeStampType": "utc"})
            runtime["nodes"].append({"values": values})
        for binding in bindings:
            values = {name: str(value) for name, value in binding["params"].items()}
            values.update({"PtID": str(point_ids[binding["channel"]]), "GwNodeID": str(nodes[binding["node"]]),
                           "IsEnabled": "1", "Disabled": "0", "TimeZoneID": "33", "Interval": str(binding["interval_minutes"])})
            runtime["points"].append({"values": values})
        expected = []
        for binding, rows in artifact["_expected"]:
            for stamp, value in rows:
                expected.append({"ptId": point_ids[binding["channel"]], "utcTimeStamp": _iso(stamp),
                                 "localTimeStamp": stamp.astimezone(PACIFIC).replace(tzinfo=None).isoformat(timespec="seconds"),
                                 "value": float(value)})
        metadata = artifact["metadata"]
        cases.append({"id": case_id, "format": metadata["format"], "source": str(path.relative_to(root)).replace("\\", "/"),
                      "inputPath": metadata["input_path"], "runtime": runtime, "expected": expected,
                      "sha256": metadata["sha256"], "parameters": {"TimeStampType": "utc", "Format": metadata["format"]}})
    manifest = {"schema": "northlake.gateway-fixtures.v1", "cases": cases}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
