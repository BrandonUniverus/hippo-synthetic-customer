import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from services.sources.model import SourceModel, utc_boundary
from services.sources.registers import RegisterConstraintError, enrich_meter

ROOT = Path(__file__).resolve().parents[3]


def measured(model, meter_id, metric, start, end, step):
    total = Decimal(0)
    stamp = utc_boundary(start) + timedelta(minutes=step)
    stop = utc_boundary(end + timedelta(days=1))
    while stamp <= stop:
        total += model.meter_value(meter_id, metric, stamp, step)
        stamp += timedelta(minutes=step)
    return total


class RegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = SourceModel(ROOT)

    def test_actual_water_anchor_and_following_month_are_one_cumulative_series(self):
        model = self.model
        meter = model.meter_numbers["SYN-RCU-M-0060001"]
        first = (date(2025, 2, 1), date(2025, 2, 28))
        first_total = measured(model, meter, "water_kgal", *first, 60)
        anchor = enrich_meter(model, meter, "water_kgal", *first, first_total)
        self.assertEqual(Decimal(1284), anchor["previous"])
        self.assertEqual(Decimal(1524), anchor["present"])
        next_total = measured(model, meter, "water_kgal", date(2025, 3, 1), date(2025, 3, 31), 60)
        following = enrich_meter(model, meter, "water_kgal", date(2025, 3, 1), date(2025, 3, 31), next_total)
        self.assertEqual(anchor["present"], following["previous"])
        self.assertEqual(next_total, following["present"] - following["previous"])

    def test_lab_wing_multiplier_applies_to_each_tou_dial_once(self):
        model = self.model
        meter = model.meter_numbers["SYN-VED-M-0040007"]
        start, end = date(2024, 7, 5), date(2024, 8, 4)
        total = measured(model, meter, "electric_kwh", start, end, 15)
        rows = enrich_meter(model, meter, "electric_kwh", start, end, total)["register_channels"]
        self.assertEqual(3, len(rows))
        self.assertEqual(total, sum(row["quantity"] for row in rows))
        for row in rows:
            self.assertEqual(Decimal(40), row["multiplier"])
            self.assertEqual(row["quantity"], (row["present"] - row["previous"]) * 40)
        self.assertEqual(Decimal(20455), rows[0]["previous"])
        self.assertEqual(Decimal(20575), rows[0]["present"])

    def test_library_new_meter_starts_at_zero_and_respects_installation_date(self):
        model = self.model
        meter = model.meter_numbers["SYN-VED-M-0040103"]
        start, end = date(2024, 8, 5), date(2024, 9, 4)
        total = measured(model, meter, "electric_kwh", start, end, 15)
        rows = enrich_meter(model, meter, "electric_kwh", start, end, total)["register_channels"]
        self.assertTrue(all(row["previous"] == 0 for row in rows))
        self.assertTrue(all(row["readPeriod"]["start"] == date(2024, 8, 15) for row in rows))
        self.assertEqual(total, sum(row["present"] for row in rows))

    def test_gas_raw_ccf_and_heat_factor_are_not_multiplied_twice(self):
        model = self.model
        meter = model.meter_numbers["SYN-SGU-M-0050001"]
        start, end = date(2025, 3, 15), date(2025, 4, 14)
        total = measured(model, meter, "gas_ccf", start, end, 60)
        result = enrich_meter(model, meter, "gas_ccf", start, end, total)
        self.assertEqual(Decimal(1210), total)
        self.assertEqual(total, result["present"] - result["previous"])
        self.assertEqual(Decimal("1.027"), result["factor"])

    def test_incompatible_anchor_delta_is_rejected(self):
        model = SourceModel(ROOT)
        meter = model.meter_numbers["SYN-RCU-M-0060001"]
        start, end = date(2025, 2, 1), date(2025, 2, 28)
        key = (meter, "water_kgal", None, start)
        previous, multiplier, _, present = model.register_anchors[key]
        model.register_anchors[key] = (previous, multiplier, end, present + 1)
        with self.assertRaisesRegex(RegisterConstraintError, "anchored read delta"):
            enrich_meter(model, meter, "water_kgal", start, end, measured(model, meter, "water_kgal", start, end, 60))

    def test_pre_anchor_usage_cannot_create_negative_opening_read(self):
        model = SourceModel(ROOT)
        meter = model.meter_numbers["SYN-RCU-M-0060001"]
        # Deliberately incompatible producer: 240 kgal/day before an opening
        # anchor of 1,284. The register adapter must report, never silently scale.
        model.meter_value = lambda *args: Decimal(10)
        with self.assertRaisesRegex(RegisterConstraintError, "negative read"):
            enrich_meter(model, meter, "water_kgal", date(2024, 1, 1), date(2024, 1, 31), Decimal(7440))


if __name__ == "__main__":
    unittest.main()
