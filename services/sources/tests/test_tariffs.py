import copy
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from services.sources.tariffs import generate_tariff_artifacts, tariff_for, tariff_rate

ROOT = Path(__file__).resolve().parents[3]


class TariffTests(unittest.TestCase):
    def provider(self, name):
        return yaml.safe_load((ROOT / f"data/providers/{name}.yaml").read_text(encoding="utf-8"))

    def test_historical_step_and_future_extension_are_separate(self):
        provider = self.provider("valley-electric-district")
        original = copy.deepcopy(provider)
        self.assertEqual(Decimal("0.241"), tariff_rate(provider, "VED-TOU-GS", "energy.peak", 2024))
        self.assertEqual(Decimal("0.258"), tariff_rate(provider, "VED-TOU-GS", "energy.peak", 2025))
        self.assertEqual(Decimal("0.265740"), tariff_rate(provider, "VED-TOU-GS", "energy.peak", 2026))
        self.assertEqual(provider, original)

    def test_contract_escalators_and_signed_credits_are_preserved(self):
        solar = self.provider("helios-onsite-solar")
        self.assertEqual(Decimal("0.121380"), tariff_rate(solar, "HOS-PPA-2024", "ppaEnergy", 2025))
        self.assertEqual(Decimal("0.123808"), tariff_rate(solar, "HOS-PPA-2024", "ppaEnergy", 2026))
        self.assertEqual(Decimal("0.092000"), tariff_rate(solar, "HOS-PPA-2024", "netMeteringCredit", 2030))
        wind = self.provider("ridgeline-wind")
        self.assertEqual(Decimal("-1250"), tariff_rate(wind, "RWL-XFER-2024", "researchCredit", 2030))
        electric = self.provider("valley-electric-district")
        self.assertLess(tariff_rate(electric, "VED-GEN-IC", "generationCredit", 2026), 0)

    def test_annual_pdf_and_json_are_reproducible_without_source_writes(self):
        first = list(generate_tariff_artifacts(date(2026, 1, 2), ROOT, since_date=date(2026, 1, 1)))
        second = list(generate_tariff_artifacts(date(2026, 1, 2), ROOT, since_date=date(2026, 1, 1)))
        self.assertEqual(12, len(first))
        self.assertEqual([(item["path"], item["content"]) for item in first], [(item["path"], item["content"]) for item in second])
        self.assertTrue(all(item["content"].startswith(b"%PDF-") for item in first if item["path"].endswith(".pdf")))


if __name__ == "__main__":
    unittest.main()
