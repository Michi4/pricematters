"""Unit tests for the quantity extractor — the core business logic.
Run: cd backend && python -m pytest tests/  (or: python -m unittest discover tests)
Every case here is a once-live bug or an adversarial title; do not weaken them.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractor import extract_quantity, unit_price


def qty_of(title, desc=""):
    q = extract_quantity(title, desc)
    return (round(q.value, 3), q.unit, q.kind) if q else None


class TestClaimTitles(unittest.TestCase):
    """Nutrient/claim sizes must never win over the real pack size."""

    def test_polyphenol_claim_500ml(self):
        self.assertEqual(
            qty_of("Das Olivenöl mit Gesundheitswert – extra hoher Polyphenol-Gehalt "
                   "950 mg/kg – Bio-Qualität – nur 1 Esslöffel/Tag – O'liv PLUS – 500 ml – 50 Portionen"),
            (500.0, "ml", "volume"))

    def test_polyphenol_claim_daily(self):
        self.assertEqual(
            qty_of("Abverkauf: Bio Olivenöl 400mg/kg Polyphenole - senkt Cholesterin* - "
                   "Extra Nativ High Phenolic kaltgepresst - O'Liv Daily - 500 ml"),
            (500.0, "ml", "volume"))

    def test_morocco_gold_claim(self):
        self.assertEqual(
            qty_of("Morocco Gold Extra natives Olivenöl – kaltgepresst – reich an "
                   "Polyphenol 652 mg/kg – EVOO – Rein und natürlich. 500 ml"),
            (500.0, "ml", "volume"))

    def test_unit_price_of_claim_title(self):
        q = extract_quantity("O'liv PLUS – 950 mg/kg – 500 ml")
        per, base = unit_price(2629, q)
        self.assertEqual(base, "l")
        self.assertAlmostEqual(per, 5258.0, places=1)  # 26.29 EUR / 0.5 l


class TestBasics(unittest.TestCase):
    def test_multipack(self):
        self.assertEqual(qty_of("Bio Basmati Reis, 2 x 1kg"), (2.0, "kg", "mass"))

    def test_grams(self):
        self.assertEqual(qty_of("Bio Kaffee Bohnen 500g"), (500.0, "g", "mass"))

    def test_liters(self):
        self.assertEqual(qty_of("Extra Natives Olivenöl Picual 5 Liter Oleo Estrella"),
                         (5.0, "l", "volume"))

    def test_count(self):
        q = extract_quantity("HOYSET Kurkuma Kapseln, 180 Kapseln")
        self.assertIsNotNone(q)
        self.assertEqual((q.value, q.unit), (180.0, "pcs"))

    def test_empty_and_none(self):
        self.assertIsNone(extract_quantity(""))
        self.assertIsNone(extract_quantity("   "))
        self.assertIsNone(extract_quantity(None))

    def test_unit_price_math(self):
        per, base = unit_price(1299, extract_quantity("Reis 2kg"))
        self.assertEqual(base, "kg")
        self.assertAlmostEqual(per, 649.5)
        per, base = unit_price(899, extract_quantity("Kaffee 500g"))
        self.assertEqual(base, "kg")
        self.assertAlmostEqual(per, 1798.0)

    def test_unit_price_zero_safe(self):
        from extractor import Qty
        self.assertIsNone(unit_price(100, Qty(0, "g", "mass")))


class TestStorage(unittest.TestCase):
    def test_tb(self):
        q = extract_quantity("SanDisk 1 TB SSD")
        self.assertEqual((q.value, q.unit), (1.0, "tb"))
        per, base = unit_price(10000, q)  # 100 EUR / 1 TB
        self.assertEqual(base, "gb")
        self.assertAlmostEqual(per, 10.0)  # 10 ct per GB

    def test_gb(self):
        q = extract_quantity("Karte 512 GB")
        per, base = unit_price(5120, q)
        self.assertEqual(base, "gb")
        self.assertAlmostEqual(per, 10.0)

    def test_mb(self):
        q = extract_quantity("Stick 1000 MB")
        per, base = unit_price(10000, q)  # 100 EUR / 1000 MB = 100 EUR / GB
        self.assertEqual(base, "gb")
        self.assertAlmostEqual(per, 10000.0)


class TestAdversarial(unittest.TestCase):
    def test_price_per_claim_ignored(self):
        # "3,49 €/kg" printed in the title is a claim, not the pack size
        q = extract_quantity("Kaffee 500g (3,49 €/kg) Sonderangebot")
        self.assertEqual((q.value, q.unit), (500.0, "g"))

    def test_serving_size_not_pack(self):
        q = extract_quantity("Protein 1000g – 30g pro Portion – 33 Portionen")
        self.assertEqual((q.value, q.unit), (1000.0, "g"))

    def test_bundle_picks_total(self):
        q = extract_quantity("Oliv PLUS – 1.500 ml – 150 Portionen")
        self.assertEqual((q.value, q.unit), (1500.0, "ml"))


if __name__ == "__main__":
    unittest.main()
