import copy
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from services.sources.model import SourceModel, utc_boundary

ROOT = Path(__file__).resolve().parents[3]
UTC = timezone.utc


class HistoricalModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = SourceModel(ROOT)

    def binding(self, channel):
        return next(b for b in self.model.bindings if b["channel"] == channel)

    def test_source_constraints_resolve_without_changing_anchors(self):
        result = self.model.validate_anchors()
        self.assertEqual(24, result["bills"])
        self.assertEqual(215, result["file_points"])
        self.assertEqual(215, len({b["channel"] for b in self.model.bindings}))

    def test_independent_science_quantities_and_peak_match_supplier_statement(self):
        actual = self.model.period_metrics("ved_science_center", date(2024, 7, 5), date(2024, 8, 4))
        self.assertEqual({"peak": Decimal(16200), "part_peak": Decimal(17600), "off_peak": Decimal(21200)}, actual["electric_tou_kwh"])
        self.assertEqual(268, actual["electric_peak_kw"])

    def test_winter_supplier_window_supports_existing_demand_limit(self):
        actual = self.model.period_metrics("ved_student_center", date(2024, 12, 5), date(2025, 1, 4))
        self.assertEqual(15950, actual["electric_tou_kwh"]["part_peak"])
        self.assertEqual(20690, actual["electric_tou_kwh"]["off_peak"])
        self.assertEqual(156, actual["electric_peak_kw"])
        assumptions = copy.deepcopy(self.model.assumptions)
        assumptions["tou"]["winter_part_peak"] = [[17, 21]]
        incompatible = SourceModel(ROOT, assumptions=assumptions)
        with self.assertRaises(ValueError):
            incompatible.validate_anchors()

    def test_dst_counts_and_repeated_instants_remain_distinct(self):
        binding = self.binding("ch_ved_science_center_kwh_15m")
        for day, count in ((date(2024, 3, 10), 92), (date(2024, 11, 3), 100)):
            rows = list(self.model.readings(binding, utc_boundary(day), utc_boundary(day + timedelta(days=1))))
            self.assertEqual(count, len(rows))
            self.assertEqual(count, len({r["timestamp_utc"] for r in rows}))
            self.assertTrue(all(r["timestamp_utc"].utcoffset() == timedelta(0) for r in rows))

    def test_solar_raw_gap_and_billed_adjustment_are_separate(self):
        binding = self.binding("ch_hos_science_center_gen_kwh_15m")
        start, end = utc_boundary(date(2025, 3, 1)), utc_boundary(date(2025, 4, 1))
        raw = sum((r["value"] for r in self.model.readings(binding, start, end)), Decimal(0))
        metrics = self.model.period_metrics("hos_science_center", date(2025, 3, 1), date(2025, 3, 31))
        self.assertEqual(38210, raw)
        self.assertEqual(40350, metrics["generated_kwh"])
        self.assertEqual(2140, metrics["generated_kwh"] - raw)
        self.assertEqual(5980, metrics["exported_kwh"])

    def test_cooling_only_anchor_has_no_manufactured_steam(self):
        actual = self.model.period_metrics("ntp_science_center", date(2024, 7, 1), date(2024, 7, 31))
        self.assertEqual(180860, actual["chilled_water_ton_hours"])
        self.assertEqual(542, actual["chilled_water_peak_tons"])
        self.assertEqual(0, actual["steam_klb"])

    def test_logical_and_unmetered_services_do_not_duplicate_physical_usage(self):
        actual = self.model.period_metrics("rwl_ridgeline_transfer", date(2024, 7, 1), date(2024, 7, 31))
        self.assertEqual(10, len(actual["meters"]))
        self.assertEqual(2251384, actual["generated_kwh"])
        for account in self.model.accounts.values():
            if all(not meter.get("channels") for meter in account.get("meters", [])):
                self.assertEqual([], self.model.period_metrics(account["id"], date(2026, 4, 1), date(2026, 4, 30))["meters"])

    def test_outage_preserves_state_and_available_power_without_generation(self):
        start = datetime(2025, 3, 1, 8, tzinfo=UTC)
        rows = {}
        for channel in ("ch_rwl_wtg07_kwh_10m", "ch_rwl_wtg07_kw_10m", "ch_rwl_wtg07_possible_kw_10m", "ch_rwl_wtg07_state_10m"):
            rows[channel] = next(self.model.readings(self.binding(channel), start, start + timedelta(minutes=10)))["value"]
        self.assertEqual(0, rows["ch_rwl_wtg07_kwh_10m"])
        self.assertEqual(0, rows["ch_rwl_wtg07_kw_10m"])
        self.assertGreater(rows["ch_rwl_wtg07_possible_kw_10m"], 0)
        self.assertEqual(2, rows["ch_rwl_wtg07_state_10m"])

    def test_unanchored_district_plant_remains_largest_estate_electric_load(self):
        start = datetime(2026, 4, 15, 16, tzinfo=UTC)
        stop = start + timedelta(hours=1)
        plant = list(self.model.readings(self.binding("ch_ved_central_plant_kw_15m"), start, stop))
        science = list(self.model.readings(self.binding("ch_ved_science_center_kw_15m"), start, stop))
        self.assertTrue(all(a["value"] > b["value"] for a, b in zip(plant, science)))


if __name__ == "__main__":
    unittest.main()
