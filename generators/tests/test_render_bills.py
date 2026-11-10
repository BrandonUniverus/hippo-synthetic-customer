"""Every bill reconciles, uses its tariff's own rates, follows its provider's read cycle, names Stage 2's
meters, and matches its checked-in PDF."""

import copy
import os
import unittest
from decimal import Decimal
from pathlib import Path

import yaml

from generators.render_bills import ROOT, check_bills, load_bills, money, rendered_bills

# BILLS_ONLY=data/bills/<file>.yaml limits the run to one source file while it is being written.
ONLY = os.environ.get("BILLS_ONLY")
ITEMIZED = Path("data/bills/northlake-itemized-bills-v1.yaml")

STAGE1_PROVIDERS = "implementation/stage-1-foundation/02-utility-providers.yaml"
STAGE2_METERS = "implementation/stage-2-hierarchy/03-meters.yaml"
ENTRY_PLAN = "data/eem/northlake-bill-entry-v1.yaml"
SCENARIO = "data/scenarios/demo-university-v1.yaml"

# Charge code -> the tariff component that prices it: a dotted path under a schedule's components, "*" for any
# key, "SCHEDULE:path" where two schedules share a name. A line without a rate (a percentage, a bare amount, a
# transfer) has nothing to look up.
COMPONENTS = {
    "valley_electric_district": {
        "energy_peak": "energy.peak", "energy_part_peak": "energy.part_peak", "energy_off_peak": "energy.off_peak",
        "demand_charge": "demand", "facility_charge": "facilityCharge",
        "generator_customer_charge": "customerCharge", "station_service_energy": "stationServiceEnergy",
        "reactive_power_charge": "reactivePower", "generation_credit": "generationCredit",
        "bct_administrative_fee": "administrativeFee",
    },
    "sierra_gas_utility": {"customer_charge": "customerCharge", "gas_commodity": "commodity.*", "gas_transport": "transport"},
    "river_city_utilities": {
        "water_meter_charge": "meterCharge.*", "water_tier1": "tiers.0", "water_tier2": "tiers.1", "water_tier3": "tiers.2",
        "sewer_base": "baseCharge", "sewer_volume": "volume", "stormwater_eru": "eruCharge",
    },
    "northlake_thermal_plant": {
        "chilled_water_consumption": "NTP-ALLOC-CHW:consumption", "chilled_water_demand": "NTP-ALLOC-CHW:demand",
        "steam_consumption": "NTP-ALLOC-STEAM:consumption",
    },
    "helios_onsite_solar": {"ppa_energy": "ppaEnergy", "net_metering_credit": "netMeteringCredit"},
    "ridgeline_wind": {"transfer_energy": "transferEnergy", "research_credit": "researchCredit"},
}
WINTER_MONTHS = {11, 12, 1, 2, 3}   # Sierra Gas's winter commodity rate, by the month a period posts to
ESCALATING = {"ppaEnergy"}          # the components an annualEscalator grows (Helios's net-metering credit stays put)


def read(path):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def provider(provider_id):
    return read(f"data/providers/{provider_id.replace('_', '-')}.yaml")


def component_rates(schedule, path):
    """Every rate at a dotted path under a schedule's components."""
    nodes = [schedule["components"]]
    for part in path.split("."):
        if part == "*":
            nodes = [child for node in nodes if isinstance(node, dict) for child in node.values()]
        else:
            nodes = [node[int(part)] if isinstance(node, list) else node.get(part) for node in nodes if isinstance(node, (dict, list))]
    return {Decimal(str(node["rate"])) for node in nodes if isinstance(node, dict) and "rate" in node}


class BillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bills = [bill for bill, source in load_bills() if ONLY is None or source == Path(ONLY)]
        cls.by_id = check_bills(cls.bills)

    def setUp(self):
        if ONLY and Path(ONLY) != ITEMIZED and self._testMethodName in {"test_meter_summaries_carry_the_billed_quantities", "test_the_credit_transfer_is_counted_once", "test_a_split_description_or_a_wrong_total_is_rejected"}:
            self.skipTest("about the Ridgeline-era bills")

    def test_every_rate_on_a_bill_is_the_tariffs_own(self):
        """A 2025 PPA energy rate (Helios) is the 2024 rate grown by its annual escalator."""
        for bill in self.bills:
            tariff = provider(bill["providerId"])
            schedules = {schedule["id"]: schedule for schedule in tariff["rateSchedules"]}
            codes = {charge["code"] for charge in tariff["billCharges"]}
            for line in bill["lines"]:
                self.assertIn(line["code"], codes, f"{bill['id']}: {line['code']} is not one of the provider's charge codes")
                if "rate" not in line:
                    continue
                path = COMPONENTS[bill["providerId"]][line["code"]]
                if line["code"] == "gas_commodity":
                    path = "commodity.winter" if bill["period"]["end"].month in WINTER_MONTHS else "commodity.summer"
                wanted, _, path = path.rpartition(":")
                rates = set()
                for schedule_id in [wanted] if wanted else bill["rateSchedules"]:
                    self.assertIn(schedule_id, bill["rateSchedules"], (bill["id"], line["code"]))
                    schedule = schedules[schedule_id]
                    escalator = schedule["components"].get("annualEscalator", {}).get("rate", 0) if path in ESCALATING else 0
                    growth = (1 + Decimal(str(escalator)) / 100) ** (bill["period"]["end"].year - 2024)
                    rates |= {abs(rate * growth).quantize(Decimal("0.00001")) for rate in component_rates(schedule, path)}
                self.assertIn(abs(Decimal(str(line["rate"]))), rates, (bill["id"], line["code"]))

    def test_every_bill_follows_its_providers_read_cycle(self):
        """A bill covers one Stage 1 period of its meters' cycle (an account's first bill starts when it opened), is
        dated after the period, and is dated no later than Stage 5 enters it (data/eem's entry lag)."""
        stage1 = {record["key"]: record for record in read(STAGE1_PROVIDERS)["records"]}
        cycle_of = {record["Meter Definition"]["Meter Number"]: record["Meter Definition"]["Bill Cycle"] for record in read(STAGE2_METERS)["records"]}
        lags = read(ENTRY_PLAN)["statusHistory"]["entryLagDays"]
        scenario = read(SCENARIO)
        accounts = {account["id"]: account for account in scenario["accounts"]}
        cedar_row = {building["id"] for site in scenario["sites"] if site["id"] == "cedar_row_apartments" for building in site["buildings"]}
        for bill in self.bills:
            cycles = {cycle_of[meter["meterNumber"]] for meter in bill["meters"]}
            self.assertEqual(1, len(cycles), f"{bill['id']}: its meters are on different cycles")
            number = cycles.pop()
            periods = {period["End Date"]: period for cycle in stage1[bill["providerId"]]["Bill Cycles"] if cycle["Cycle"] == number for period in cycle["Periods"]}
            self.assertIn(bill["period"]["end"], periods, f"{bill['id']}: the period does not end on a cycle {number} read")
            account = accounts[bill["accountId"]]
            self.assertIn(bill["period"]["start"], {periods[bill["period"]["end"]]["Start Date"], account.get("effectiveStart")}, f"{bill['id']}: the period does not start where the cycle's period does")
            if bill["providerId"] == "ridgeline_wind":
                continue                                   # generated by EEM, never entered; the hand-made statement is a reference
            lag = lags["cedar_row"] if account["buildingId"] in cedar_row else lags[bill["providerId"]]
            self.assertGreater(bill["billDate"], bill["period"]["end"], bill["id"])
            if bill.get("supersedes"):                     # a correction follows the bill it replaces, whenever the actual read comes
                self.assertGreater(bill["billDate"], self.by_id[bill["supersedes"]]["billDate"], bill["id"])
            else:
                self.assertLessEqual((bill["billDate"] - bill["period"]["end"]).days, lag, f"{bill['id']}: dated after Stage 5 enters it")
            if bill["dueDate"]:
                self.assertGreater(bill["dueDate"], bill["billDate"], bill["id"])
            for meter in bill["meters"]:
                if meter.get("readPeriod"):
                    self.assertGreaterEqual(meter["readPeriod"]["start"], bill["period"]["start"], bill["id"])
                    self.assertLessEqual(meter["readPeriod"]["end"], bill["period"]["end"], bill["id"])

    def test_meters_badges_and_multipliers_are_stage_2s(self):
        meters = {record["Meter Definition"]["Meter Number"]: record["Meter Definition"] for record in read(STAGE2_METERS)["records"]}
        providers = {record["key"]: record["Definitions"]["Name"] for record in read(STAGE1_PROVIDERS)["records"]}
        for bill in self.bills:
            for meter in bill["meters"]:
                definition = meters[meter["meterNumber"]]
                self.assertEqual(definition["Provider Meter Number"] or None, meter.get("badge"), (bill["id"], meter["meterNumber"]))
                if "multiplier" in meter:
                    self.assertEqual(definition["Meter Multiplier"] or 1, meter["multiplier"], (bill["id"], meter["meterNumber"]))
                self.assertEqual(providers[bill["providerId"]], definition["Utility Provider"], (bill["id"], meter["meterNumber"]))
                if "present" in meter:
                    usage = Decimal(str(meter["present"])) - Decimal(str(meter["previous"]))
                    expected = usage * Decimal(str(meter.get("factor", 1))) * Decimal(str(meter.get("multiplier", 1)))
                    self.assertEqual(round(expected), round(Decimal(str(meter["quantity"]))), f"{bill['id']}: {meter['meterNumber']} reads do not give its quantity")

    def test_meter_summaries_carry_the_billed_quantities(self):
        for bill_id in ("ved_ridgeline_generator_2024_07", "ved_ridgeline_generator_2025_01"):
            bill = self.by_id[bill_id]
            meters = {meter["channel"]: meter for meter in bill["meters"]}
            lines = {line["code"]: line for line in bill["lines"]}
            export = meters["Received (export)"]
            self.assertEqual(export["quantity"], lines["generation_credit"]["quantity"])
            self.assertEqual(f"{export['quantity'] / 1000:.3f} MWh", export["statedAs"])           # the bill states export in MWh
            self.assertEqual(meters["Delivered (station service)"]["quantity"], lines["station_service_energy"]["quantity"])
            allowed = round(export["quantity"] * 0.3286841)                                         # kWh x tan(acos(0.95))
            self.assertEqual(max(0, meters["Reactive"]["quantity"] - allowed), lines["reactive_power_charge"]["quantity"])
            self.assertIn(f"{meters['Reactive']['quantity']:,} kVArh measured; {allowed:,} allowed", lines["reactive_power_charge"]["description"])
            self.assertTrue(all(meter["quantity"] % 12 == 0 for meter in bill["meters"]))           # 12,000 multiplier, 0.001 register
        statement = self.by_id["rwl_transfer_2024_07"]
        self.assertEqual(10, len(statement["meters"]))
        self.assertEqual(sum(meter["quantity"] for meter in statement["meters"]), statement["lines"][0]["quantity"])
        central = self.by_id["ved_central_plant_2024_09"]
        energy = sum(line["quantity"] for line in central["lines"] if line["code"].startswith("energy_"))
        self.assertEqual(central["meters"][0]["quantity"], energy)

    def test_the_credit_transfer_is_counted_once(self):
        out = next(line for line in self.by_id["ved_ridgeline_generator_2024_07"]["lines"] if line["code"] == "bct_credit_transferred")
        credit = next(line for line in self.by_id["ved_ridgeline_generator_2024_07"]["lines"] if line["code"] == "generation_credit")
        arrived = next(line for line in self.by_id["ved_central_plant_2024_09"]["lines"] if line["code"] == "bct_credit_received")
        self.assertEqual(money(out["amount"]), -money(credit["amount"]))      # the generator account keeps none of its credit
        self.assertEqual(money(arrived["amount"]), money(credit["amount"]))   # and the Central Plant receives all of it
        self.assertEqual(Decimal("1077.45"), money(self.by_id["ved_ridgeline_generator_2024_07"]["total"]))  # what the generator account still pays

    def test_a_split_description_or_a_wrong_total_is_rejected(self):
        bills = copy.deepcopy(self.bills)
        next(bill for bill in bills if bill["id"] == "ved_central_plant_2024_09")["lines"][0]["on-peak (summer)"] = None   # what an unquoted comma does
        with self.assertRaisesRegex(AssertionError, "unknown line keys"):
            check_bills(bills)
        bills = copy.deepcopy(self.bills)
        next(bill for bill in bills if bill["id"] == "rwl_transfer_2024_07")["total"] = 129330.28
        with self.assertRaisesRegex(AssertionError, "lines sum to"):
            check_bills(bills)

    def test_checked_in_bills_match_regeneration(self):
        for path, content in rendered_bills(only=ONLY).items():
            self.assertTrue((ROOT / path).read_bytes() == content, f"{path} is stale; run python generators/render_bills.py")


if __name__ == "__main__":
    unittest.main()
