import copy
import csv
import io
import unittest
from unittest.mock import patch
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

from generators.render_bills import load_bills
from services.sources.billing import billing_periods, import_items, invoices, generate_billing_artifacts, _bill_xml, _provider_csv, _bif, provider_schema
from services.sources.tariffs import json_bytes

ROOT = Path(__file__).resolve().parents[3]


class MeasurementFixture:
    """A known measurement boundary for arithmetic tests; no filesystem or SQL state."""
    def __init__(self):
        self.root = ROOT
        self.scenario = yaml.safe_load((ROOT / "data/scenarios/demo-university-v1.yaml").read_text(encoding="utf-8"))
        self.accounts = {item["id"]: item for item in self.scenario["accounts"]}
        self.providers = {item["id"]: item for item in (yaml.safe_load(path.read_text(encoding="utf-8")) for path in (ROOT / "data/providers").glob("*.yaml"))}

    def period_metrics(self, account_id, start, end):
        days = Decimal((end - start).days + 1)
        return {"electric_tou_kwh": {"peak": days * 3 if start.month in (6, 7, 8, 9) else 0, "part_peak": days * 2, "off_peak": days * 5},
                "electric_peak_kw": Decimal(80), "delivered_kwh": days * 10, "received_kwh": days * 100,
                "reactive_kvarh": days * 10, "gas_ccf": days * 10, "gas_therms": days * Decimal("10.27"),
                "water_kgal": days * 5, "chilled_water_ton_hours": days * 100, "chilled_water_peak_tons": Decimal(300),
                "steam_klb": days * 5, "generated_kwh": days * 100, "exported_kwh": days * 10, "meters": []}


class BillingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = MeasurementFixture()

    def test_full_supplier_period_coverage_and_correction_versions(self):
        bills = list(invoices(self.model, date(2026, 1, 8)))
        supplier = [bill for bill in bills if bill["providerId"] != "ridgeline_wind"]
        self.assertEqual(50, len({bill["accountId"] for bill in supplier}))
        # January 2026 VED/SGU cycles are not all issued on this cutoff; count the fixed historic postings.
        historic = [bill for bill in supplier if bill["fiscalYear"] <= 2025]
        self.assertEqual(1193, len(historic))
        self.assertEqual(1192, len({(bill["accountId"], bill["fiscalYear"], bill["fiscalPeriod"]) for bill in historic}))
        self.assertEqual(24, sum(bool(bill.get("anchor")) for bill in bills))
        self.assertEqual(len(bills), len({bill["id"] for bill in bills}))
        generator = [bill for bill in bills if bill["accountId"] == "ved_ridgeline_generator" and bill["fiscalYear"] == 2025]
        january = next(bill for bill in generator if bill["fiscalPeriod"] == 1)
        february = next(bill for bill in generator if bill["fiscalPeriod"] == 2)
        self.assertNotEqual(january["id"], february["id"])
        self.assertEqual("ved_ridgeline_generator_2025_01", february["id"])
        corrections = [bill for bill in historic if bill["accountId"] == "sgu_student_center" and bill["fiscalYear"] == 2024 and bill["fiscalPeriod"] == 11]
        self.assertEqual(2, len(corrections))
        self.assertEqual(2, len({bill["id"] for bill in corrections}))
        self.assertTrue(any(bill.get("supersedes") in {item["id"] for item in corrections} for bill in corrections))
        by_id = {bill["id"]: bill for bill in bills}
        for bill in bills:
            for line in bill["lines"]:
                for target in (line.get("transfer", {}).get("appearsOn"), line.get("transfer", {}).get("leftOn")):
                    if target:
                        self.assertIn(target, by_id)
        self.assertTrue({bill["id"] for bill, _ in load_bills(ROOT)} <= set(by_id))
        for bill in supplier:
            self.assertEqual(Decimal(str(bill["total"])).quantize(Decimal(".01")), sum(Decimal(str(line["amount"])) for line in bill["lines"]))

    def test_cycles_lead_in_and_incomplete_periods(self):
        periods = billing_periods(self.model.accounts["ved_admin_hall"], date(2024, 1, 6))
        self.assertEqual(date(2023, 12, 5), periods[0]["start"])
        self.assertEqual(1, len(periods))
        generator = billing_periods(self.model.accounts["ved_ridgeline_generator"], date(2026, 1, 1))
        self.assertEqual(17, len(generator))
        self.assertEqual(date(2024, 7, 1), generator[0]["start"])
        self.assertEqual(date(2024, 8, 4), generator[0]["end"])

    def test_library_native_xml_retains_meter_periods_and_cents(self):
        bill = next(copy.deepcopy(bill) for bill, _ in load_bills(ROOT) if bill["id"] == "ved_library_2024_09")
        bill.update(anchor=True, fiscalYear=2024, fiscalPeriod=9, providerCode="VED")
        items = import_items(bill, self.model.accounts[bill["accountId"]])
        self.assertEqual(10, len(items))
        xml = ET.fromstring(_bill_xml(bill, items))
        rows = xml.findall("Bill/BillItems/BillItem")
        self.assertEqual(Decimal("5114.37"), sum(Decimal(row.findtext("Amount")) for row in rows))
        old = [row for row in rows if row.findtext("Meter") == "SYN-VED-M-0040003"]
        self.assertEqual(3, len(old))
        self.assertTrue(all(row.findtext("BIEndDate") == "2024-08-14" for row in old))
        self.assertEqual("118420", old[0].findtext("PreviousReading"))

    def test_provider_csv_preserves_repeated_lines_and_signed_credits(self):
        for target in ("ved_student_center_2025_01", "ved_central_plant_2024_09"):
            bill = next(copy.deepcopy(bill) for bill, _ in load_bills(ROOT) if bill["id"] == target)
            bill.update(anchor=True, fiscalYear=bill["period"]["end"].year, fiscalPeriod=bill["period"]["end"].month, providerCode="VED")
            items = import_items(bill, self.model.accounts[bill["accountId"]])
            rows = list(csv.DictReader(io.StringIO(_provider_csv(bill, items).decode())))
            self.assertEqual(1, len(rows))
            amounts = [Decimal(value) for key, value in rows[0].items() if key.startswith("line_") and key.endswith("_amount") and value]
            self.assertEqual(Decimal(str(bill["total"])), sum(amounts))
            if "central" in target:
                self.assertIn(Decimal("-152792.65"), amounts)
        schema = ET.fromstring(provider_schema("VED"))
        self.assertEqual(16, len(schema.findall("BillItem")))

    def test_real_measurements_price_to_existing_summer_and_water_anchors(self):
        from services.sources.model import SourceModel
        from services.sources.billing import _generated_bill
        model = SourceModel(ROOT)
        source = {bill["id"]: bill for bill, _ in load_bills(ROOT)}
        for bill_id in ("ved_science_center_2024_08", "ved_library_2024_09", "rcu_admin_hall_2025_02"):
            anchor = source[bill_id]
            account = model.accounts[anchor["accountId"]]
            period = next(period for period in billing_periods(account, date(2025, 4, 1)) if period["end"] == anchor["period"]["end"])
            generated = _generated_bill(model, account, period, {})
            self.assertEqual(Decimal(str(anchor["total"])), generated["total"], bill_id)

    def test_daily_batches_reuse_immutable_pdf_anchors_and_skip_empty_work(self):
        from generators.render_bills import rendered_bills
        model = MeasurementFixture()
        with patch("generators.render_bills.rendered_bills", wraps=rendered_bills) as renderer:
            empty = list(generate_billing_artifacts(model, date(2024, 1, 1)))
            self.assertFalse(any(item["metadata"].get("artifact") == "pdf" for item in empty))
            renderer.assert_not_called()
            first = list(generate_billing_artifacts(model, date(2024, 4, 5), since_date=date(2024, 4, 5)))
            replay = list(generate_billing_artifacts(model, date(2024, 4, 5), since_date=date(2024, 4, 5)))
            self.assertEqual([(item["path"], item["content"]) for item in first], [(item["path"], item["content"]) for item in replay])
            self.assertEqual(1, renderer.call_count)

    def test_wrapped_rendering_preserves_the_existing_anchor_pdf_contract(self):
        from generators.render_bills import render_bill, rendered_bills
        bill, source = load_bills(ROOT)[0]
        original = copy.deepcopy(bill)
        model = MeasurementFixture()
        wrapped = io.BytesIO()
        render_bill(bill, model.providers[bill["providerId"]], model.scenario, source, wrapped, wrap_meter_cells=True)
        self.assertTrue(wrapped.getvalue().startswith(b"%PDF-"))
        self.assertEqual(original, bill)
        for relative_path, content in rendered_bills(ROOT).items():
            self.assertEqual((ROOT / relative_path).read_bytes(), content, relative_path)


def write_parser_fixtures(output_root):
    """Opt-in bridge: real Python artifacts consumed by the existing C# parsers."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    model = MeasurementFixture()
    index = []
    for code in ("VED", "RCU"):
        (root / f"{code}.xml").write_bytes(provider_schema(code))
    for original, _ in load_bills(ROOT):
        if original["providerId"] not in ("valley_electric_district", "river_city_utilities"):
            continue
        bill = copy.deepcopy(original)
        bill.update(anchor=True, fiscalYear=bill["period"]["end"].year, fiscalPeriod=bill["period"]["end"].month,
                    providerCode=model.providers[bill["providerId"]]["shortName"], location=model.accounts[bill["accountId"]]["buildingId"])
        items = import_items(bill, model.accounts[bill["accountId"]])
        for suffix, content in (("csv", _provider_csv(bill, items)), ("bif", _bif(bill, items)), ("xml", _bill_xml(bill, items))):
            (root / f"{bill['id']}.{suffix}").write_bytes(content)
        index.append({"id": bill["id"], "provider": bill["providerCode"], "account": bill["accountNumber"],
                      "amount": str(bill["total"]), "items": items})
    (root / "index.json").write_bytes(json_bytes(index))


if __name__ == "__main__":
    unittest.main()
