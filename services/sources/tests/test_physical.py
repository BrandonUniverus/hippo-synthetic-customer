"""Dependent source readings conserve their master meters and stated checkpoints."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from services.sources.model import SourceModel, utc_boundary

ROOT = Path(__file__).resolve().parents[3]
UTC = timezone.utc


class PhysicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = SourceModel(ROOT)
        cls.by_channel = {binding["channel"]: binding for binding in cls.model.bindings}

    def test_cedar_unit_and_house_energy_exactly_conserve_quarter_hour_master_readings(self):
        for end in (datetime(2025, 1, 15, 20, tzinfo=UTC), datetime(2024, 11, 3, 8, tzinfo=UTC), datetime(2024, 11, 3, 9, tzinfo=UTC)):
            for building in ("a", "b"):
                bindings = [binding for key, binding in self.by_channel.items()
                            if key.startswith(f"ch_cedar_row_{building}_") and binding["profile"] == "gw_fig_fixed_network_submeters"]
                master = f"ved_cedar_row_{building}_master"
                total = sum((self.model.meter_value(master, "electric_kwh", end - timedelta(minutes=minute), 15)
                             for minute in (0, 15, 30, 45)), Decimal(0))
                actual = [(binding, self.model._binding_value(binding, end)) for binding in bindings]
                self.assertEqual(total, sum((value for _, value in actual), Decimal(0)))
                self.assertTrue(all(0 <= value <= total for _, value in actual))
                unit_total = sum((value for binding, value in actual if "_unit_" in binding["channel"]), Decimal(0))
                self.assertEqual((total * Decimal("0.75")).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), unit_total)

    def test_campus_submeters_are_declared_shares_of_the_actual_parent(self):
        end = datetime(2025, 1, 15, 20, tzinfo=UTC)
        for key in ("ch_lakeview_hall_laundry_kwh_60m", "ch_parking_structure_ev_kwh_60m"):
            binding = self.by_channel[key]
            meter = self.model.channels[key]["meter"]
            parent = self.model.meters[meter]["behindMeterId"]
            total = sum((self.model.meter_value(parent, "electric_kwh", end - timedelta(minutes=minute), 15)
                         for minute in (0, 15, 30, 45)), Decimal(0))
            share = Decimal(str(self.model.assumptions["profiles"]["electric_submeter_shares"][meter]))
            self.assertEqual((total * share).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), self.model._binding_value(binding, end))

    def test_interconnection_july_and_august_parts_preserve_the_first_bill(self):
        meter = "ved_ridgeline_interconnection"
        expected = {"received_kwh": (Decimal(2208612), Decimal(288000)),
                    "delivered_kwh": (Decimal(3876), Decimal(552))}
        for metric, targets in expected.items():
            observed = []
            for start, stop in ((utc_boundary("2024-07-01"), utc_boundary("2024-08-01")),
                                (utc_boundary("2024-08-01"), utc_boundary("2024-08-05"))):
                values = []
                end = start + timedelta(minutes=15)
                while end <= stop:
                    value = self.model.meter_value(meter, metric, end, 15)
                    if metric == "received_kwh":
                        gross = Decimal(str(self.model.wind_energy(end, 15)))
                        self.assertLessEqual(value, gross + Decimal("0.000001"), str(end))
                    values.append(value)
                    end += timedelta(minutes=15)
                observed.append(sum(values, Decimal(0)))
            self.assertEqual(targets, tuple(observed))
        self.assertEqual(Decimal(2496612), sum(expected["received_kwh"]))
        self.assertEqual(Decimal(4428), sum(expected["delivered_kwh"]))

    def test_july_possible_power_integrates_to_the_source_statement_and_bounds_actual(self):
        start, stop = utc_boundary("2024-07-01"), utc_boundary("2024-08-01")
        total = Decimal(0)
        for binding in self.model.bindings:
            if "possible_kw" not in binding["channel"]:
                continue
            actual_binding = self.by_channel[binding["channel"].replace("possible_kw", "kw")]
            end = start + timedelta(minutes=10)
            while end <= stop:
                possible = self.model._binding_value(binding, end)
                self.assertGreaterEqual(possible, self.model._binding_value(actual_binding, end))
                total += possible
                end += timedelta(minutes=10)
        self.assertEqual(Decimal(2327960), total / 6)

    def test_fault_is_present_zero_production_with_nonzero_possible_power(self):
        end = datetime(2025, 2, 12, 20, tzinfo=UTC)
        for suffix in ("kwh", "kw"):
            self.assertEqual(0, self.model._binding_value(self.by_channel[f"ch_rwl_wtg07_{suffix}_10m"], end))
        self.assertEqual(2, self.model._binding_value(self.by_channel["ch_rwl_wtg07_state_10m"], end))
        self.assertGreater(self.model._binding_value(self.by_channel["ch_rwl_wtg07_possible_kw_10m"], end), 0)
        self.assertEqual(1, self.model._binding_value(self.by_channel["ch_rwl_wtg06_state_10m"], end))


if __name__ == "__main__":
    unittest.main()
