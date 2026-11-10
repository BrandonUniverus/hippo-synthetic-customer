"""Consumer proof against the implementation chat's actual manifest builder."""
import unittest

from generators.handheld_bindings import make_manifest, pilot_expectations
from services.handheld.contracts import validate_binding
from services.handheld.fixtures import FIXTURE_SOURCE, demo


class BindingInteropTests(unittest.TestCase):
    def test_readonly_manifest_builder_matches_native_export_consumer(self):
        raw, original = demo()
        expected = pilot_expectations(["CRBMW", "SCGAS"])
        rows = []
        for index, wanted in enumerate(expected):
            fixture = original["channels"][index]
            # Only test-owned synthetic IDs: this test never queries SQL.
            rows.append({"channel_key": wanted["Key"], **{key: fixture[key] for key in
                         ("meter_id", "reading_pt_id", "usage_pt_id", "hmr_meter_id", "hmr_reading_id", "gateway_id")},
                         "cycle": wanted["Cycle"], "route": wanted["Route"], "sequence": wanted["Sequence"],
                         "text_prompt": wanted["Prompt"], "channel": wanted["Channel"], "active": True,
                         "type_description": wanted["ReadType"], "ert_type": None,
                         **{key: fixture["read_type"][key] for key in ("num_dials", "num_decimals", "read_type_code", "read_direction", "demand_read", "truncation_factor")},
                         "raw_unit": "Reading", "usage_unit": wanted["DisplayUnit"], "meter_constant": 1, "delta_multiplier": 1})
            # Match SQL char(12) serial and char(2) channel, retaining its trailing space.
            raw = raw.replace(fixture["meter_number"].ljust(12).encode(), wanted["MeterNumber"][:12].ljust(12).encode())
        lines = raw.decode().splitlines()
        sequence_by_wire_route = {c["Route"].zfill(6): c["Sequence"] for c in expected}
        lines = [line[:61] + str(sequence_by_wire_route[line[5:11]]).zfill(8) + line[69:] if line.startswith("MTR") else line for line in lines]
        lines = [line[:24] + "1 " + line[26:] if line.startswith("RDG") else line for line in lines]
        raw = ("\r\n".join(lines) + "\r\n").encode()
        manifest = make_manifest(expected, rows, export_bytes=raw, source=FIXTURE_SOURCE,
                                 openings={c["route"]: c["opening"] for c in original["channels"]},
                                 environment_id="fixture-only", verified_at="2026-11-04T20:00:00Z")
        selected = validate_binding(raw, manifest, FIXTURE_SOURCE)
        self.assertEqual(["neptune", "mvrs"], [c["return_format"] for c in selected])
        self.assertEqual(["01", "01"], [c["channel"] for c in selected])
        self.assertEqual([c["Key"] for c in expected], [c["channel_key"] for c in selected])
