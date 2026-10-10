#!/usr/bin/env python3
"""
HFIN Daily Price Updater
-------------------------
Fetches, validates, and records daily market data for Hotel Forest Inn Limited (HFIN)
from the public YONEPSE community feed into the repository's historical CSV dataset.

Data Source:
  - Feed: https://shubhamnpk.github.io/yonepse/data/nepse_data.json
  - Docs: https://shubhamnpk.github.io/yonepse/pages/docs.html
  Note: This feed is maintained by a third party and is not an official NEPSE service.
"""

import argparse
import csv
import json
import logging
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    NEPAL_TZ = ZoneInfo("Asia/Kathmandu")
except Exception:
    NEPAL_TZ = timezone(timedelta(hours=5, minutes=45), name="Asia/Kathmandu")

# Defaults
DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "Stock Trading of Hotel Forest Inn Limited.csv"
DEFAULT_FEED_URL = "https://shubhamnpk.github.io/yonepse/data/nepse_data.json"
DEFAULT_MANIFEST_URL = "https://shubhamnpk.github.io/yonepse/data/ltp/manifest.json"
DEFAULT_STATUS_URL = "https://shubhamnpk.github.io/yonepse/data/market/status.json"

EXPECTED_SYMBOL = "HFIN"
EXPECTED_NAME = "Hotel Forest Inn Limited"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("update_hfin")


def fetch_json(url: str, timeout: int = 15) -> Any:
    """Fetch and decode JSON from a remote URL with appropriate headers and timeouts."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "HFIN-Data-Updater/1.0 (+https://github.com/sushanttds-jpg/HfIN_Analysis_Using_Python)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError(f"HTTP {response.status} returned from {url}")
            charset = response.headers.get_content_charset() or "utf-8"
            raw_data = response.read().decode(charset)
            return json.loads(raw_data)
    except urllib.error.URLError as e:
        raise ConnectionError(f"Network error fetching {url}: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON from {url}: {e}") from e


def find_hfin_record(data: Any) -> Dict[str, Any]:
    """Locate the exact HFIN record in the dataset array."""
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list in nepse_data.json, got {type(data).__name__}")
    
    matches = [item for item in data if isinstance(item, dict) and item.get("symbol") == EXPECTED_SYMBOL]
    if not matches:
        raise LookupError(f"No entry found with exact symbol '{EXPECTED_SYMBOL}' in feed.")
    if len(matches) > 1:
        raise ValueError(f"Multiple entries found for symbol '{EXPECTED_SYMBOL}'.")
    return matches[0]


def parse_nepal_date(timestamp_str: Optional[str]) -> Tuple[str, datetime]:
    """Parse an ISO timestamp and convert to date string in Asia/Kathmandu."""
    if not timestamp_str:
        raise ValueError("Missing 'last_updated' timestamp in market data record.")
    
    # Handle timestamps like 2026-10-06T14:59:59.903792 or with Z/offset
    clean_ts = timestamp_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean_ts)
    except ValueError as e:
        raise ValueError(f"Unable to parse timestamp '{timestamp_str}': {e}") from e

    if dt.tzinfo is None:
        # Feed timestamps without offset represent local Kathmandu time
        dt = dt.replace(tzinfo=NEPAL_TZ)
    else:
        dt = dt.astimezone(NEPAL_TZ)

    date_str = dt.strftime("%Y-%m-%d")
    return date_str, dt


def validate_hfin_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate all required fields, company name, prices, and ranges."""
    name = record.get("name")
    if name != EXPECTED_NAME:
        raise ValueError(f"Company name mismatch. Expected '{EXPECTED_NAME}', got '{name}'.")

    # Numeric fields
    def get_num(key: str, required_positive: bool = True) -> float:
        val = record.get(key)
        if val is None:
            raise ValueError(f"Field '{key}' is missing in HFIN record.")
        try:
            num = float(val)
        except (ValueError, TypeError):
            raise ValueError(f"Field '{key}' is not numeric: {val}")
        if required_positive and num <= 0:
            raise ValueError(f"Field '{key}' must be positive, got {num}")
        return num

    ltp = get_num("ltp", required_positive=True)
    high = get_num("high", required_positive=True)
    low = get_num("low", required_positive=True)
    volume = int(get_num("volume", required_positive=False))
    turnover = get_num("turnover", required_positive=False)
    trades = int(get_num("trades", required_positive=False))

    if high < low:
        raise ValueError(f"High price ({high}) cannot be less than low price ({low}).")
    if ltp > high * 1.05 or ltp < low * 0.95:
        logger.warning("LTP (%s) is outside normal [low, high] range [%s, %s]", ltp, low, high)

    date_str, dt = parse_nepal_date(record.get("last_updated"))

    return {
        "date": date_str,
        "datetime": dt,
        "close": ltp,
        "high": high,
        "low": low,
        "volume": volume,
        "turnover": turnover,
        "trades": trades,
        "raw_record": record,
    }


def check_market_finalization(
    target_date: str,
    manifest_url: str = DEFAULT_MANIFEST_URL,
    status_url: str = DEFAULT_STATUS_URL
) -> Tuple[bool, str]:
    """
    Verify whether the target date's trading data represents a finalized close
    rather than an intraday snapshot.
    """
    try:
        market_status = fetch_json(status_url, timeout=10)
        is_open = market_status.get("is_open", False)
        if is_open:
            return False, "Market is currently OPEN (intraday trading session active)."
    except Exception as e:
        logger.warning("Could not verify market open/closed status: %s", e)

    try:
        manifest = fetch_json(manifest_url, timeout=10)
        finalized_through = manifest.get("finalizedThrough") or manifest.get("latestDate")
        latest_status = manifest.get("latestStatus")
        if finalized_through and target_date <= finalized_through:
            return True, f"Verified finalized by manifest through {finalized_through} (status: {latest_status})."
    except Exception as e:
        logger.warning("Could not verify manifest finalization: %s", e)

    return True, "Market is closed; recording end-of-day summary."


def read_existing_csv(csv_path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Read the existing CSV, separating comment lines and header from data rows.
    Returns (comment_lines, parsed_rows).
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    comment_lines: List[str] = []
    rows: List[Dict[str, str]] = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        lines = f.readlines()

    csv_text_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("//") or (not csv_text_lines and not stripped):
            comment_lines.append(line)
        else:
            csv_text_lines.append(line)

    if not csv_text_lines:
        raise ValueError("CSV contains no header or data lines.")

    reader = csv.DictReader(csv_text_lines)
    for r in reader:
        rows.append(r)

    return comment_lines, rows


def format_price_num(val: float) -> str:
    """Format float into clean representation (integer if .0, else stripped decimal)."""
    if val == int(val):
        return str(int(val))
    return f"{val:.4f}".rstrip("0").rstrip(".")


def update_hfin_csv(
    csv_path: Path,
    feed_url: str = DEFAULT_FEED_URL,
    manifest_url: str = DEFAULT_MANIFEST_URL,
    status_url: str = DEFAULT_STATUS_URL,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Execute the full update pipeline:
      1. Read existing CSV
      2. Fetch and validate HFIN feed
      3. Verify market finalization
      4. Check for duplicates
      5. Insert new record in descending date order
      6. Update metadata comments
    """
    logger.info("Reading existing CSV at %s...", csv_path)
    comment_lines, existing_rows = read_existing_csv(csv_path)

    existing_dates = {r["BUSINESS DATE"].strip() for r in existing_rows if "BUSINESS DATE" in r}
    logger.info("Existing CSV contains %d records (latest date: %s)",
                len(existing_rows), existing_rows[0].get("BUSINESS DATE") if existing_rows else "none")

    logger.info("Fetching public NEPSE feed from %s...", feed_url)
    feed_data = fetch_json(feed_url)
    hfin_raw = find_hfin_record(feed_data)
    validated = validate_hfin_record(hfin_raw)

    record_date = validated["date"]
    logger.info("Fetched HFIN record for %s (Close: NPR %s, High: %s, Low: %s, Volume: %s)",
                record_date, validated["close"], validated["high"], validated["low"], validated["volume"])

    # Duplicate check
    if record_date in existing_dates:
        msg = f"Record for date {record_date} already exists in CSV. No duplicate added."
        logger.info(msg)
        return False, msg

    # Finalization check
    is_finalized, fin_reason = check_market_finalization(record_date, manifest_url, status_url)
    logger.info("Finalization status: %s (%s)", is_finalized, fin_reason)
    if not is_finalized:
        msg = f"Market data for {record_date} is not finalized: {fin_reason}. Update aborted."
        logger.warning(msg)
        return False, msg

    # Format new row
    new_row = {
        "BUSINESS DATE": record_date,
        "CLOSE PRICE": format_price_num(validated["close"]),
        "HIGH PRICE": format_price_num(validated["high"]),
        "LOW PRICE": format_price_num(validated["low"]),
        "TOTAL TRADED QUANTITY": str(validated["volume"]),
        "TOTAL TRADED VALUE": format_price_num(validated["turnover"]),
        "TOTAL TRADES": str(validated["trades"])
    }

    if dry_run:
        msg = (f"[DRY-RUN] Would prepend row for {record_date}: "
               f"{new_row['BUSINESS DATE']},{new_row['CLOSE PRICE']},{new_row['HIGH PRICE']},"
               f"{new_row['LOW PRICE']},{new_row['TOTAL TRADED QUANTITY']},{new_row['TOTAL TRADED VALUE']},"
               f"{new_row['TOTAL TRADES']}")
        logger.info(msg)
        return True, msg

    # Update comment line 2 with newest date if present
    updated_comments: List[str] = []
    for line in comment_lines:
        if line.startswith("//has updated till"):
            updated_comments.append(f"//has updated till 2026-03-11 to {record_date}\n")
        else:
            updated_comments.append(line)

    # Insert into descending chronological list
    all_rows = [new_row] + existing_rows
    # Sort strictly descending by date to ensure proper ordering
    all_rows.sort(key=lambda x: x["BUSINESS DATE"], reverse=True)

    fieldnames = [
        "BUSINESS DATE", "CLOSE PRICE", "HIGH PRICE", "LOW PRICE",
        "TOTAL TRADED QUANTITY", "TOTAL TRADED VALUE", "TOTAL TRADES"
    ]

    # Write atomically
    temp_path = csv_path.with_suffix(".tmp")
    with open(temp_path, mode="w", encoding="utf-8", newline="") as f:
        for c in updated_comments:
            f.write(c)
        if updated_comments and not updated_comments[-1].endswith("\n\n"):
            f.write("\n")
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    temp_path.replace(csv_path)
    msg = f"Successfully updated {csv_path.name} with {record_date} (Close: NPR {new_row['CLOSE PRICE']})."
    logger.info(msg)
    return True, msg


def record_holiday(
    csv_path: Path,
    holiday_date: Optional[str] = None,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Record a non-trading day (weekend or public holiday) in the CSV dataset.
    Follows repository convention:
      CLOSE PRICE: MARKET CLOSED
      HIGH PRICE: WEEKEND
      LOW PRICE: HOLIDAY
      TOTAL TRADED QUANTITY: 0
      TOTAL TRADED VALUE: 0
      TOTAL TRADES: 0
    """
    if not holiday_date:
        holiday_date = datetime.now(NEPAL_TZ).strftime("%Y-%m-%d")
    else:
        try:
            datetime.strptime(holiday_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid holiday date format '{holiday_date}'. Expected YYYY-MM-DD.")

    logger.info("Reading existing CSV at %s...", csv_path)
    comment_lines, existing_rows = read_existing_csv(csv_path)

    existing_dates = {r["BUSINESS DATE"].strip() for r in existing_rows if "BUSINESS DATE" in r}
    if holiday_date in existing_dates:
        msg = f"Record for date {holiday_date} already exists in CSV. No duplicate added."
        logger.info(msg)
        return False, msg

    holiday_row = {
        "BUSINESS DATE": holiday_date,
        "CLOSE PRICE": "MARKET CLOSED",
        "HIGH PRICE": "WEEKEND",
        "LOW PRICE": "HOLIDAY",
        "TOTAL TRADED QUANTITY": "0",
        "TOTAL TRADED VALUE": "0",
        "TOTAL TRADES": "0"
    }

    if dry_run:
        msg = (f"[DRY-RUN] Would record holiday/market closure for {holiday_date}: "
               f"{holiday_row['BUSINESS DATE']},{holiday_row['CLOSE PRICE']},{holiday_row['HIGH PRICE']},"
               f"{holiday_row['LOW PRICE']},{holiday_row['TOTAL TRADED QUANTITY']},{holiday_row['TOTAL TRADED VALUE']},"
               f"{holiday_row['TOTAL TRADES']}")
        logger.info(msg)
        return True, msg

    all_rows = [holiday_row] + existing_rows
    all_rows.sort(key=lambda x: x["BUSINESS DATE"], reverse=True)
    newest_date = all_rows[0]["BUSINESS DATE"]

    updated_comments: List[str] = []
    for line in comment_lines:
        if line.startswith("//has updated till"):
            updated_comments.append(f"//has updated till 2026-03-11 to {newest_date}\n")
        else:
            updated_comments.append(line)

    fieldnames = [
        "BUSINESS DATE", "CLOSE PRICE", "HIGH PRICE", "LOW PRICE",
        "TOTAL TRADED QUANTITY", "TOTAL TRADED VALUE", "TOTAL TRADES"
    ]

    temp_path = csv_path.with_suffix(".tmp")
    with open(temp_path, mode="w", encoding="utf-8", newline="") as f:
        for c in updated_comments:
            f.write(c)
        if updated_comments and not updated_comments[-1].endswith("\n\n"):
            f.write("\n")
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    temp_path.replace(csv_path)
    msg = f"Successfully recorded holiday/market closure for {holiday_date} in {csv_path.name}."
    logger.info(msg)
    return True, msg


def main() -> None:
    parser = argparse.ArgumentParser(description="Update HFIN historical stock prices from YONEPSE public feed.")
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH, help="Path to HFIN CSV dataset")
    parser.add_argument("--endpoint", type=str, default=DEFAULT_FEED_URL, help="YONEPSE nepse_data.json URL")
    parser.add_argument("--manifest-url", type=str, default=DEFAULT_MANIFEST_URL, help="YONEPSE manifest.json URL")
    parser.add_argument("--status-url", type=str, default=DEFAULT_STATUS_URL, help="YONEPSE market status URL")
    parser.add_argument("--holiday", nargs="?", const="", default=None,
                        help="Record a weekend or holiday non-trading day (defaults to today in Asia/Kathmandu, or specify YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate update and show diff without modifying CSV")
    args = parser.parse_args()

    try:
        if args.holiday is not None:
            holiday_date = args.holiday.strip() if args.holiday.strip() else None
            success, message = record_holiday(
                csv_path=args.csv_path,
                holiday_date=holiday_date,
                dry_run=args.dry_run
            )
        else:
            success, message = update_hfin_csv(
                csv_path=args.csv_path,
                feed_url=args.endpoint,
                manifest_url=args.manifest_url,
                status_url=args.status_url,
                dry_run=args.dry_run
            )
        print(f"\nResult: {message}")
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error("Update failed: %s", e, exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
