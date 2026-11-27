"""Store the HFIN dataset in SQLite and answer simple SQL queries.

Standard library only (sqlite3 + csv) — no pandas needed. This is the
repo's SQL layer: the CSV stays the source of truth, the database is a
queryable mirror rebuilt from it at any time.

Usage:
    python3 hfin_sqlite.py                  # build hfin.db from the CSV
    python3 hfin_sqlite.py --summary        # build, then print a summary
    python3 hfin_sqlite.py --db prices.db   # build a differently named DB
"""

import argparse
import csv
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS hfin_prices (
    business_date TEXT PRIMARY KEY,
    close REAL NOT NULL,
    high REAL,
    low REAL,
    volume INTEGER,
    traded_value REAL,
    trades INTEGER
)
"""

SUMMARY_SQL = (
    "SELECT COUNT(*), MIN(business_date), MAX(business_date) FROM hfin_prices"
)
PEAK_SQL = (
    "SELECT business_date, close FROM hfin_prices "
    "ORDER BY close DESC LIMIT 1"
)
LATEST_SQL = (
    "SELECT business_date, close FROM hfin_prices "
    "ORDER BY business_date DESC LIMIT 1"
)
MONTHLY_AVG_SQL = """
SELECT substr(business_date, 1, 7) AS month, ROUND(AVG(close), 2) AS avg_close
FROM hfin_prices
GROUP BY month
ORDER BY month
"""


def _to_float(value):
    """Float or None for a CSV cell (non-trading rows say MARKET CLOSED)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    """Int or None for a CSV cell."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def load_csv_to_db(csv_path, db_path):
    """Load trading-day rows from the HFIN CSV into SQLite.

    Returns the number of trading days stored. Non-trading rows
    (CLOSE PRICE = MARKET CLOSED) are skipped. Re-running replaces
    rows by date, so the load is idempotent.
    """
    with Path(csv_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        stored = 0
        for row in rows:
            close = _to_float(row.get("CLOSE PRICE"))
            if close is None:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO hfin_prices VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row["BUSINESS DATE"],
                    close,
                    _to_float(row.get("HIGH PRICE")),
                    _to_float(row.get("LOW PRICE")),
                    _to_int(row.get("TOTAL TRADED QUANTITY")),
                    _to_float(row.get("TOTAL TRADED VALUE")),
                    _to_int(row.get("TOTAL TRADES")),
                ),
            )
            stored += 1
        conn.commit()
    return stored


def summary(db_path):
    """Trading days, date range, peak and latest close from the database."""
    with sqlite3.connect(db_path) as conn:
        days, first, last = conn.execute(SUMMARY_SQL).fetchone()
        peak_date, peak_close = conn.execute(PEAK_SQL).fetchone()
        latest_date, latest_close = conn.execute(LATEST_SQL).fetchone()
    return {
        "trading_days": days,
        "first_date": first,
        "last_date": last,
        "peak_date": peak_date,
        "peak_close": peak_close,
        "latest_date": latest_date,
        "latest_close": latest_close,
    }


def monthly_avg_close(db_path):
    """Average close per calendar month, as (YYYY-MM, avg_close) pairs."""
    with sqlite3.connect(db_path) as conn:
        return conn.execute(MONTHLY_AVG_SQL).fetchall()


def main():
    """Build the database from the CSV and optionally print a summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", default="hfin_stock_data.csv",
        help="source CSV (default: hfin_stock_data.csv)",
    )
    parser.add_argument(
        "--db", default="hfin.db",
        help="SQLite file to build (default: hfin.db)",
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="print a summary after building",
    )
    args = parser.parse_args()
    stored = load_csv_to_db(args.csv, args.db)
    print(f"Stored {stored} trading days in {args.db}")
    if args.summary:
        stats = summary(args.db)
        print(
            f"{stats['trading_days']} trading days, "
            f"{stats['first_date']} to {stats['last_date']}"
        )
        print(f"Peak: NPR {stats['peak_close']} on {stats['peak_date']}")
        print(f"Latest: NPR {stats['latest_close']} on {stats['latest_date']}")
        for month, avg in monthly_avg_close(args.db):
            print(f"  {month}: avg close NPR {avg}")


if __name__ == "__main__":
    main()
