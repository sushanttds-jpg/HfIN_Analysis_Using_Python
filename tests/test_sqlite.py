"""Tests for hfin_sqlite storage and queries."""

import csv
import tempfile
import unittest
from pathlib import Path

from hfin_sqlite import load_csv_to_db, monthly_avg_close, summary

FIXTURE_ROWS = [
    {
        "BUSINESS DATE": "2026-03-15",
        "CLOSE PRICE": "122.9",
        "HIGH PRICE": "122.9",
        "LOW PRICE": "110.7",
        "TOTAL TRADED QUANTITY": "140",
        "TOTAL TRADED VALUE": "16688",
        "TOTAL TRADES": "14",
    },
    {
        "BUSINESS DATE": "2026-03-16",
        "CLOSE PRICE": "135.1",
        "HIGH PRICE": "135.1",
        "LOW PRICE": "121.7",
        "TOTAL TRADED QUANTITY": "150",
        "TOTAL TRADED VALUE": "19828",
        "TOTAL TRADES": "15",
    },
    {
        "BUSINESS DATE": "2026-03-17",
        "CLOSE PRICE": "MARKET CLOSED",
        "HIGH PRICE": "WEEKEND",
        "LOW PRICE": "WEEKEND",
        "TOTAL TRADED QUANTITY": "0",
        "TOTAL TRADED VALUE": "0",
        "TOTAL TRADES": "0",
    },
    {
        "BUSINESS DATE": "2026-03-18",
        "CLOSE PRICE": "148.6",
        "HIGH PRICE": "148.6",
        "LOW PRICE": "137.8",
        "TOTAL TRADED QUANTITY": "90",
        "TOTAL TRADED VALUE": "13107",
        "TOTAL TRADES": "9",
    },
]

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestLoadCsv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.tmp.name) / "fixture.csv"
        self.db_path = Path(self.tmp.name) / "test.db"
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(FIXTURE_ROWS[0]))
            writer.writeheader()
            writer.writerows(FIXTURE_ROWS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_skips_market_closed_rows(self):
        stored = load_csv_to_db(self.csv_path, self.db_path)
        self.assertEqual(stored, 3)

    def test_reload_is_idempotent(self):
        load_csv_to_db(self.csv_path, self.db_path)
        stored = load_csv_to_db(self.csv_path, self.db_path)
        self.assertEqual(stored, 3)
        self.assertEqual(summary(self.db_path)["trading_days"], 3)

    def test_summary_and_monthly_average(self):
        load_csv_to_db(self.csv_path, self.db_path)
        stats = summary(self.db_path)
        self.assertEqual(stats["first_date"], "2026-03-15")
        self.assertEqual(stats["last_date"], "2026-03-18")
        self.assertEqual(stats["peak_close"], 148.6)
        self.assertEqual(stats["peak_date"], "2026-03-18")
        self.assertEqual(stats["latest_close"], 148.6)
        monthly = monthly_avg_close(self.db_path)
        self.assertEqual(monthly, [("2026-03", 135.53)])


class TestRealDataset(unittest.TestCase):
    def test_real_csv_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "hfin.db"
            stored = load_csv_to_db(REPO_ROOT / "hfin_stock_data.csv", db_path)
            self.assertEqual(stored, 106)
            stats = summary(db_path)
            self.assertEqual(stats["first_date"], "2026-03-15")
            self.assertEqual(stats["last_date"], "2026-11-06")
            self.assertEqual(stats["peak_close"], 1386.0)
            self.assertEqual(stats["peak_date"], "2026-04-21")
            self.assertEqual(stats["latest_close"], 514.9)


if __name__ == "__main__":
    unittest.main()
