#!/usr/bin/env python3
"""
Unit tests for HFIN Daily Price Updater.
Covers:
  - Successful updates
  - Duplicate prevention
  - Malformed responses
  - Missing HFIN data
  - Company name mismatches
  - Stale / market-open data handling
  - Network errors
  - Dry-run safety
"""

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.update_hfin import (
    update_hfin_csv,
    validate_hfin_record,
    find_hfin_record,
    fetch_json,
    read_existing_csv,
)

SAMPLE_CSV_CONTENT = """//Data taken From : https://nepalstock.com.np/stock-trading
//has updated till 2026-03-11 to 2026-07-31

BUSINESS DATE,CLOSE PRICE,HIGH PRICE,LOW PRICE,TOTAL TRADED QUANTITY,TOTAL TRADED VALUE,TOTAL TRADES
2026-07-31,720,722,668.8,22713,16114369,527
2026-07-30,704,722,695,28853,20312512,510
"""

SAMPLE_VALID_FEED = [
    {
        "symbol": "HFIN",
        "name": "Hotel Forest Inn Limited",
        "ltp": 550.5,
        "previous_close": 544.1,
        "change": 6.4,
        "percent_change": 1.18,
        "high": 565.0,
        "low": 544.0,
        "volume": 17308,
        "turnover": 9546324.5,
        "trades": 418,
        "last_updated": "2026-10-06T14:59:59.903792",
        "market_cap": 11010.0
    },
    {
        "symbol": "NABIL",
        "name": "Nabil Bank Limited",
        "ltp": 620.0,
        "high": 625.0,
        "low": 615.0,
        "volume": 50000,
        "turnover": 31000000,
        "trades": 800,
        "last_updated": "2026-10-06T14:59:59.000000"
    }
]

SAMPLE_STATUS_CLOSED = {"is_open": False, "last_checked": "2026-10-06T15:00:00"}
SAMPLE_STATUS_OPEN = {"is_open": True, "last_checked": "2026-10-06T12:00:00"}
SAMPLE_MANIFEST_FINAL = {
    "version": 1,
    "latestDate": "2026-10-06",
    "latestStatus": "final",
    "finalizedThrough": "2026-10-06"
}


class TestHfinUpdater(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "test_hfin.csv"
        self.csv_path.write_text(SAMPLE_CSV_CONTENT, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("scripts.update_hfin.fetch_json")
    def test_successful_update(self, mock_fetch):
        def side_effect(url, timeout=15):
            if "status.json" in url:
                return SAMPLE_STATUS_CLOSED
            if "manifest.json" in url:
                return SAMPLE_MANIFEST_FINAL
            return SAMPLE_VALID_FEED

        mock_fetch.side_effect = side_effect

        success, msg = update_hfin_csv(self.csv_path, dry_run=False)
        self.assertTrue(success)
        self.assertIn("Successfully updated", msg)

        # Verify content
        comments, rows = read_existing_csv(self.csv_path)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["BUSINESS DATE"], "2026-10-06")
        self.assertEqual(rows[0]["CLOSE PRICE"], "550.5")
        self.assertEqual(rows[0]["HIGH PRICE"], "565")
        self.assertEqual(rows[0]["LOW PRICE"], "544")
        self.assertEqual(rows[0]["TOTAL TRADED QUANTITY"], "17308")
        self.assertEqual(rows[0]["TOTAL TRADED VALUE"], "9546324.5")
        self.assertEqual(rows[0]["TOTAL TRADES"], "418")

        # Verify header comment update
        has_updated_line = [c for c in comments if "//has updated till" in c]
        self.assertTrue(has_updated_line)
        self.assertIn("2026-10-06", has_updated_line[0])

    @patch("scripts.update_hfin.fetch_json")
    def test_duplicate_prevention(self, mock_fetch):
        # Return record for 2026-07-31 which is already in SAMPLE_CSV_CONTENT
        stale_feed = [
            {
                "symbol": "HFIN",
                "name": "Hotel Forest Inn Limited",
                "ltp": 720.0,
                "high": 722.0,
                "low": 668.8,
                "volume": 22713,
                "turnover": 16114369,
                "trades": 527,
                "last_updated": "2026-07-31T15:00:00.000000"
            }
        ]
        mock_fetch.side_effect = lambda url, timeout=15: (
            SAMPLE_STATUS_CLOSED if "status.json" in url else
            SAMPLE_MANIFEST_FINAL if "manifest.json" in url else
            stale_feed
        )

        initial_content = self.csv_path.read_text(encoding="utf-8")
        success, msg = update_hfin_csv(self.csv_path, dry_run=False)
        self.assertFalse(success)
        self.assertIn("already exists", msg)

        # File must remain untouched
        self.assertEqual(self.csv_path.read_text(encoding="utf-8"), initial_content)

    @patch("scripts.update_hfin.fetch_json")
    def test_dry_run_mode(self, mock_fetch):
        mock_fetch.side_effect = lambda url, timeout=15: (
            SAMPLE_STATUS_CLOSED if "status.json" in url else
            SAMPLE_MANIFEST_FINAL if "manifest.json" in url else
            SAMPLE_VALID_FEED
        )

        initial_content = self.csv_path.read_text(encoding="utf-8")
        success, msg = update_hfin_csv(self.csv_path, dry_run=True)
        self.assertTrue(success)
        self.assertIn("[DRY-RUN]", msg)

        # File must remain unchanged in dry run
        self.assertEqual(self.csv_path.read_text(encoding="utf-8"), initial_content)

    @patch("scripts.update_hfin.fetch_json")
    def test_missing_hfin_data(self, mock_fetch):
        # Feed missing HFIN
        feed_without_hfin = [{"symbol": "OTHER", "name": "Other Company Ltd"}]
        mock_fetch.return_value = feed_without_hfin

        initial_content = self.csv_path.read_text(encoding="utf-8")
        with self.assertRaises(LookupError):
            update_hfin_csv(self.csv_path, dry_run=False)

        self.assertEqual(self.csv_path.read_text(encoding="utf-8"), initial_content)

    def test_company_name_mismatch(self):
        mismatched_record = {
            "symbol": "HFIN",
            "name": "Different Hotel Inn Limited",
            "ltp": 500,
            "high": 510,
            "low": 490,
            "volume": 100,
            "turnover": 50000,
            "trades": 5,
            "last_updated": "2026-10-06T15:00:00"
        }
        with self.assertRaises(ValueError) as ctx:
            validate_hfin_record(mismatched_record)
        self.assertIn("Company name mismatch", str(ctx.exception))

    def test_invalid_prices(self):
        # High lower than Low
        inverted = {
            "symbol": "HFIN",
            "name": "Hotel Forest Inn Limited",
            "ltp": 500,
            "high": 480,
            "low": 520,
            "volume": 100,
            "turnover": 50000,
            "trades": 5,
            "last_updated": "2026-10-06T15:00:00"
        }
        with self.assertRaises(ValueError):
            validate_hfin_record(inverted)

        # Negative price
        negative = {
            "symbol": "HFIN",
            "name": "Hotel Forest Inn Limited",
            "ltp": -10,
            "high": 10,
            "low": 5,
            "volume": 100,
            "turnover": 50000,
            "trades": 5,
            "last_updated": "2026-10-06T15:00:00"
        }
        with self.assertRaises(ValueError):
            validate_hfin_record(negative)

    @patch("scripts.update_hfin.fetch_json")
    def test_market_open_unfinalized_prevents_update(self, mock_fetch):
        # If market is OPEN, do not record as finalized closing price
        mock_fetch.side_effect = lambda url, timeout=15: (
            SAMPLE_STATUS_OPEN if "status.json" in url else
            SAMPLE_MANIFEST_FINAL if "manifest.json" in url else
            SAMPLE_VALID_FEED
        )

        initial_content = self.csv_path.read_text(encoding="utf-8")
        success, msg = update_hfin_csv(self.csv_path, dry_run=False)
        self.assertFalse(success)
        self.assertIn("not finalized", msg)
        self.assertEqual(self.csv_path.read_text(encoding="utf-8"), initial_content)

    @patch("scripts.update_hfin.urllib.request.urlopen")
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        initial_content = self.csv_path.read_text(encoding="utf-8")
        with self.assertRaises(ConnectionError):
            update_hfin_csv(self.csv_path, dry_run=False)
        self.assertEqual(self.csv_path.read_text(encoding="utf-8"), initial_content)


if __name__ == "__main__":
    unittest.main()
