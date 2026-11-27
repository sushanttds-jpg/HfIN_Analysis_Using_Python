# HFIN — NEPSE Market Analysis & Automated Price Tracking
### Hotel Forest Inn Ltd | Nepal Stock Exchange (NEPSE) | Reliable Market Dataset

A data science analysis and reproducible tracking project for **Hotel Forest Inn Limited (HFIN)** on the Nepal Stock Exchange. This repository maintains a verified historical price dataset and analyzes how market speculation, political events, and thin-float trading dynamics affect stock behavior.

---

## 📊 The Story In Numbers

| Event | Date | Price (NPR) |
|---|---|---|
| Data starts (post-election) | Mar 12, 2026 | 111.8 |
| Balen Shah sworn in (RSP majority) | Mar 29, 2026 | 289.1 |
| Peak price | Apr 21, 2026 | 1,386.0 |
| Consolidated post-correction | Oct 6, 2026 | 550.5 |
| Latest close in dataset | Nov 6, 2026 | 514.9 |
| **Total peak gain** | | **+1,140%** |
| Current correction from peak | | -62.9% |

*The swearing-in was Fri Mar 27, 2026, a NEPSE non-trading day — NPR 289.1 is the close of the first trading session after it (Sun Mar 29).*

---

## 📁 Repository Structure

```
HfIN_Analysis_Using_Python/
├── .github/workflows/
│   ├── daily_stock_sync.yml                       # Scheduled GitHub Actions cron for daily market sync
│   └── ci.yml                                     # Continuous integration (Ruff linting + tests)
├── assets/                                        # Generated charts & reference figures
├── docs/
│   └── about_hfin.md                              # Company background & dataset metadata
├── hfin_stock_data.csv                            # Core historical OHLCV dataset
├── Stock Trading of Hotel Forest Inn Limited.csv  # Legacy raw file (see Data Freshness note)
├── hfin_analysis.py                               # Event study visualization & return analysis script
├── hfin_stats.py                                  # Return statistics (mean, volatility, t-test) — stdlib only
├── hfin_sqlite.py                                 # SQLite mirror of the dataset + SQL queries — stdlib only
├── hfin_event_study.png                           # Exported 5-panel dashboard chart
├── scripts/
│   └── update_hfin.py                             # Automated daily price updater CLI
├── tests/
│   ├── test_updater.py                            # Comprehensive test suite (unittest)
│   └── test_stats.py                              # Return-statistics unit tests
│   └── test_sqlite.py                             # SQLite storage + query tests
├── requirements.txt                               # Minimal Python dependencies
├── .gitignore                                     # Clean VCS exclusions
└── README.md                                      # Documentation & usage guide
```

---

## 🗄️ Dataset Schema

The primary dataset file is [`hfin_stock_data.csv`](./hfin_stock_data.csv), stored in reverse chronological order (newest date first):

| Column | Type | Description |
|---|---|---|
| `BUSINESS DATE` | `string (YYYY-MM-DD)` | Trading date in Nepal Standard Time (`Asia/Kathmandu`) |
| `CLOSE PRICE` | `numeric / text` | Finalized closing price (or `MARKET CLOSED` on non-trading days) |
| `HIGH PRICE` | `numeric / text` | Highest intraday traded price |
| `LOW PRICE` | `numeric / text` | Lowest intraday traded price |
| `TOTAL TRADED QUANTITY` | `integer` | Total shares exchanged during the session |
| `TOTAL TRADED VALUE` | `numeric` | Total transaction turnover in NPR |
| `TOTAL TRADES` | `integer` | Total executed trade count |

---

## 🗄️ SQLite Mirror

The dataset can be mirrored into SQLite for SQL queries — no pandas needed:

```bash
python3 hfin_sqlite.py --summary
```

This builds `hfin.db` (gitignored) from `hfin_stock_data.csv` and prints trading days, date range, peak and latest close, plus average close per month. `hfin_sqlite.py` is standard library only (`sqlite3` + `csv`); the CSV stays the source of truth and the database is rebuilt from it at any time.

---

## 🔄 Automated Daily Price Updater

The updater script ([`scripts/update_hfin.py`](./scripts/update_hfin.py)) automatically updates the dataset with verifiable market data.

### Features
- **Strict Symbol & Company Validation:** Verifies symbol `HFIN` and exact name `Hotel Forest Inn Limited`.
- **Timezone Awareness:** Uses `Asia/Kathmandu` (UTC+5:45) for all record dates.
- **Finalization Verification:** Queries market open/closed status and manifest finalization status so intraday snapshots are never recorded as official daily closing prices.
- **Duplicate Prevention:** Detects existing business dates and exits safely without mutating the CSV.
- **Atomic File Writing:** Writes to a temporary buffer before replacing the target file to avoid corruption.

### Usage

**1. Dry-Run (Preview what would change without modifying the file):**
```bash
python3 scripts/update_hfin.py --dry-run
```

**2. Live Update:**
```bash
python3 scripts/update_hfin.py
```

**3. Record Weekend / Public Holiday:**
```bash
# Record today as non-trading / holiday:
python3 scripts/update_hfin.py --holiday

# Or record a specific date:
python3 scripts/update_hfin.py --holiday 2026-10-11
```

---

## 🧪 Running Tests

The test suite requires no third-party test runners and runs directly with Python's built-in `unittest`:

```bash
python3 -m unittest discover tests
```

Tests cover:
- Successful record insertion and header metadata update
- Duplicate date prevention
- Missing HFIN symbol and company name mismatch detection
- Malformed JSON handling
- Price range sanity checks (negative prices, inverted high/low)
- Market-open / unfinalized state protection
- SQLite storage and queries (`hfin_sqlite.py`)
- Network connection error handling
- Dry-run non-mutation guarantee

---

## 📈 Running the Event Study Analysis

To regenerate the 5-panel analytical dashboard (`hfin_event_study.png`):

```bash
pip install -r requirements.txt
python3 hfin_analysis.py
```

---

## 🌐 Data Sources & Disclaimer

- **Official Source:** [Nepal Stock Exchange (NEPSE)](https://nepalstock.com.np) historical trading records.
- **Automated Feed:** [YONEPSE Public JSON Data Feed](https://shubhamnpk.github.io/yonepse) ([docs](https://shubhamnpk.github.io/yonepse/pages/docs.html)).
  > *Disclaimer: The YONEPSE data feed is a community-maintained third-party scraper feed and is not an official service of NEPSE. The updater cross-checks finalization status and market closure before recording data.*

### ⚠️ Data Freshness (as of Nov 26, 2026)

- The YONEPSE feed **froze on Nov 6, 2026 (last update 14:59 NPT)** — every symbol, not just HFIN. The latest close in `hfin_stock_data.csv` is therefore Nov 6 (NPR 514.9).
- The updater (`scripts/update_hfin.py`) and the daily GitHub Actions sync are **not broken**: the updater's duplicate guard correctly sees Nov 6 already recorded and adds nothing, so the workflow has nothing to commit.
- A second file, `Stock Trading of Hotel Forest Inn Limited.csv`, holds manually added rows through Nov 24 (latest close NPR 475) and matches the core dataset on all 104 overlapping dates — but its Nov 7–24 rows are **not yet verified** (they record closes on Fri Nov 13 and Fri Nov 20 while marking Mon–Thu Nov 9–12 closed, which conflicts with NEPSE's Sun–Thu trading week), so they are **not merged** into `hfin_stock_data.csv` until cross-checked against a second source.
- Next step: evaluate a replacement live source (e.g. the `nepsepy` client for nepalstock.com.np) and backfill Nov 7–25 from trading days only.

---

## 💡 Key Research Findings

1. **Pre-Event Speculation:** The stock price surged 2.3× *before* the government was formally sworn in—the market priced political anticipation rather than earnings fundamentals.
2. **Distribution Signal at Peak:** April 20 recorded the highest single-day volume (292,797 shares) right at the price peak, matching a classic institutional distribution pattern into retail momentum buying.
3. **Thin-Float Behavior:** Normal daily trading volume was 10,000–40,000 shares; daily return volatility is 5.90% (full-sample standard deviation over 105 trading days), confirming thin-float manipulation susceptibility.
4. **Sentiment Driven:** Movement was driven by sentiment surrounding Nepal's first majority government since 1999 rather than changes in hotel revenue or tourism fundamentals.

---

## 👤 About

Built as part of my data science portfolio  
**Sushant Singh Thapa** — School of Mathematical Sciences, Tribhuvan University  
📍 Kathmandu, Nepal | 🎯 Building toward Erasmus Mundus EMJM
