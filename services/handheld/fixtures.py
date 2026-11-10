"""Small synthetic protocol examples. IDs are deliberately not installed bindings."""
from pathlib import Path

from .codecs import encode, record
from .contracts import ROUTES, SCHEMA, digest, json_bytes, validate_binding

FIXTURE_SOURCE = {"release_id": "handheld-fixture-only", "model_version": "controlled-v1", "source_hash": "0" * 64,
                  "seed": 104729, "assumptions_version": 1}


def demo(source=None):
    source = source or FIXTURE_SOURCE
    channels, lines = [], []
    header = record(126, (0, 5, "FHDNN"), (13, 2, "02"), (15, 3, "NNN"))
    lines.append(header)
    for i, (route, settings) in enumerate(ROUTES.items(), 1):
        cycle, prompt, unit, codec, profile, key, dials, code = settings
        prefix = cycle + route.zfill(6)
        chd = record(126, (0, 3, "CHD"), (3, 2, cycle), (5, 4, "0001"))
        rhd = record(126, (0, 3, "RHD"), (3, 8, prefix), (11, 6, "NN0000"), (17, 28, "0001000000010000000000010001"),
                     (45, 6, "000000"), (51, 12, "000000010000" if i == 1 else "000100000000"))
        lines.extend([chd, rhd, record(126, (0, 3, "CUS"), (3, 8, prefix), (11, 3, "001")),
                      record(126, (0, 3, "MTR"), (3, 8, prefix), (11, 3, "001"), (29, 2, "CA"),
                             (45, 12, f"DEMO-METER-{i}"), (61, 8, "00000001"), (69, 20, 900000 + i)),
                      record(126, (0, 3, "RDG"), (3, 8, prefix), (11, 4, prompt), (15, 2, "YL"), (20, 3, "099"),
                             (24, 2, "01"), (26, 2, str(dials).zfill(2)), (28, 3, "00K"), (31, 30, "0" * 30),
                             (61, 6, "     1"), (67, 9, "0000000  "), (76, 2, code), (78, 17, "02000000300000000")),
                      "RTR" + rhd[3:], "CTR" + chd[3:]])
        channels.append({"channel_key": f"fixture_{route}", "reading_channel_key": f"fixture_{route}_register", "company": "Northlake fixture",
                         "meter_number": f"DEMO-METER-{i}", "meter_description": f"{route} demonstration master", "meter_id": 900000 + i,
                         "reading_pt_id": 901000 + i, "usage_pt_id": 902000 + i, "hmr_meter_id": 903000 + i, "hmr_reading_id": 904000 + i,
                         "cycle": cycle, "route": route, "sequence": 1, "text_prompt": prompt, "channel": "01",
                         "read_type": {"key": key, "num_dials": dials, "num_decimals": 0, "read_type_code": code, "read_direction": "L", "demand_read": "N", "truncation_factor": 0},
                         "meter_constant": "1", "delta_multiplier": "1", "raw_unit": "Reading", "display_unit": unit, "usage_unit": unit,
                         "gateway_profile": profile, "gateway_id": 905000 + i, "return_format": codec, "delivery_target": "fixture-only",
                         "opening": {"value": 1000, "observed_at": "2026-10-01T12:00:00-07:00", "basis": "controlled-pilot",
                                     "reason": "Known demonstration opening; these IDs do not identify installed Northlake objects"}})
    lines.append("FTR" + header[3:])
    raw = ("\r\n".join(lines) + "\r\n").encode()
    binding = {"schema": SCHEMA, "environment_id": "fixture-only", "database": "NOT-AN-INSTALLED-DATABASE",
               "verified_at": "2026-11-04T00:00:00Z", "export_sha256": digest(raw), "purpose": "controlled-pilot", "source": source, "channels": channels}
    return raw, binding


def write_fixtures(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    raw, binding = demo()
    channels = validate_binding(raw, binding, FIXTURE_SOURCE)
    (root / "route-export.txt").write_bytes(raw)
    (root / "bindings.json").write_bytes(json_bytes(binding))
    cases = []
    for c in channels:
        for name, timestamp, action, value, note in (
            ("opening", "2026-10-01T12:00:00-07:00", "read", 1000, "Known opening"),
            ("normal", "2026-10-15T12:00:00-07:00", "read", 1125, "Access clear"),
            ("skip", "2026-10-20T12:00:00-07:00", "skip", None, "Access locked"),
            ("later", "2026-11-04T12:00:00-08:00", "read", 1180, "Access restored"),
            ("correction", "2026-10-15T12:00:00-07:00", "read", 1127, "Corrected transcription"),
        ):
            o = {"reader": "NLR001", "observed_at": timestamp, "action": action, "value": value, "note": note}
            data = encode(c, o)
            filename = f"{c['return_format']}-{name}.imp"
            (root / filename).write_bytes(data)
            runtime = {"gatewayId": c["gateway_id"], "gatewayName": "Controlled handheld", "gatewayGuid": "fixture-only",
                       "nodes": [{"values": {"GwNodeID": "-1", "IsEnabled": "1", "Name": "HMR"}}],
                       "points": [{"values": {"GwNodeID": "-1", "MetaWorldID": str(c["meter_id"]), "TextPrompt": c["text_prompt"],
                                   "PtID_Reading": str(c["reading_pt_id"]), "PtID_Usage": str(c["usage_pt_id"]), "TimeZoneID": "33",
                                   "Interval": "1440", "MeterConstant": "1", "NumDecimals": "0", "UN_Units": "CurRead"}}]}
            cases.append({"id": filename, "format": c["return_format"], "source": filename, "sha256": digest(data), "runtime": runtime,
                          "action": action, "value": value, "usage": None if value is None else value - 1000,
                          "timestamp": timestamp, "readingPtId": c["reading_pt_id"], "usagePtId": c["usage_pt_id"], "note": note})
    (root / "manifest.json").write_bytes(json_bytes({"schema": "northlake.handheld-fixtures.v1", "cases": cases}))
