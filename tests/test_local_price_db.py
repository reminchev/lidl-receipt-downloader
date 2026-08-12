import unittest

from receipt_analysis import ReceiptAnalyzer


class LocalPriceDatabaseTests(unittest.TestCase):
    def test_record_price_updates_existing_value_for_same_date(self):
        analyzer = ReceiptAnalyzer(log=lambda msg: None, db_path=":memory:")

        analyzer.record_price("Мляко", "2025-07-10", 2.40, "€/л")
        analyzer.record_price("Мляко", "2025-07-10", 2.60, "€/л")

        history = analyzer.get_price_history("Мляко")
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]["price"], 2.5)
        self.assertEqual(history[0]["unit"], "€/л")

    def test_compare_years_merges_product_variants_with_brand_and_weight(self):
        analyzer = ReceiptAnalyzer(log=lambda msg: None, db_path=":memory:")
        products_data = {
            "Кашкавал Вианга 250г": {
                "2025-01-10": 6.50,
                "2026-01-12": 7.20,
            },
            "Кашкавал": {
                "2025-02-05": 6.10,
                "2026-02-07": 7.00,
            },
        }

        rows = analyzer.compare_years(products_data)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product"], "КАШКАВАЛ")
        self.assertEqual(rows[0]["basis"], "€/кг")


if __name__ == "__main__":
    unittest.main()
