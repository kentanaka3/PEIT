# PEIT Signed Transaction Ledger System

This document is the authoritative technical reference for the Personal Economic Inflation Tracker (PEIT) signed transaction ledger architecture, storage engine, deduplication protocol, command-line interface, and test automation.

---

## 1. Architecture Overview & Core Principles

PEIT analyzes personal expenditure and personal price change over time. While macroeconomic indices like the Consumer Price Index (CPI) aggregate population-level averages over rigid baskets, PEIT calculates personalized inflation from point-of-sale receipt observations and household cash-flow records.

To provide auditability, provenance, and high-performance querying, the ledger subsystem (`src/peit/ledger.py`) implements a **dual-storage architecture**:

```text
┌───────────────────────────────────────────────────────────────────────┐
│                             Input Sources                             │
│  • Receipt CSV Ingestion (peit --import <csv>)                        │
│  • Direct Cash Flow Events (peit --add ...)                           │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                        compute_entry_id(SHA-256)
                                    │
               ┌────────────────────┴─────────────────────┐
               ▼                                          ▼
┌───────────────────────────┐               ┌───────────────────────────┐
│ Authoritative JSONL Log   │               │ Sibling SQLite Cache      │
│ (<ledger>.jsonl)          │               │ (<ledger>.db)             │
├───────────────────────────┤               ├───────────────────────────┤
│ • Append-only audit trail │               │ • Indexed query engine    │
│ • Source of truth         │◄──(rebuild)───┤ • Fast balances/breakdown │
│ • Git-friendly line diffs │   staleness   │ • Foreign & unique keys   │
│ • Portable UTF-8 JSON     │   detection   │ • Auto-healing projection │
└───────────────────────────┘               └───────────────────────────┘
```

### 1.1 Dual-Storage Synchronization Model

1. **Authoritative JSON Lines Log (`<name>.jsonl`)**:
   - Every line represents a fully validated, self-contained `LedgerEntry` serialized as JSON.
   - The file is **append-only**. Entries are never mutated in place.
   - Preserves complete provenance: receipt identifier (`receipt_id`), transaction date (`receipt_date`), raw description (`description`), normalized key (`item`), brand (`brand`), pack size (`pack_size`), unit price (`unit_price`), and the UTC recording timestamp (`recorded_at`).
   - Serves as the ultimate source of truth for version control, backups, and data migration.

2. **Automatic Sibling SQLite Projection Cache (`<name>.db`)**:
   - Resides in the exact same directory alongside the `.jsonl` file (e.g. `data/ledger.jsonl` projections cache is `data/ledger.db`).
   - Contains an indexed `entries` table and a synchronization metadata table `meta`.
   - Dedicated indexes on `month`, `receipt_date`, `account`, `category`, `merchant`, and `event_type` allow sub-millisecond aggregations and filter operations.

3. **Cache Synchronization Lifecycle & Self-Healing**:
   - **On Write (`append_entries`, `--import`, `--add`)**: Dual-write pattern. Entries are appended to the JSONL log, inserted into SQLite, and file metadata (`jsonl_size`, `jsonl_mtime`, `entry_count`) is atomically recorded in `meta`.
   - **On Read (`get_balance`, `list_entries`, `get_category_breakdown`)**: The cache freshness is verified before query execution. If `<name>.db` is missing, corrupted, or if the `.jsonl` file size or modification time has changed (e.g. out-of-band edit or git pull), `LedgerDatabase` transparently recreates the SQLite schema and reprojects the entire JSONL log into the database without data loss.
   - **Explicit Maintenance**: Users can force a complete reconstruction of the cache from the JSONL log at any time using `peit --ledger <path> --rebuild-cache`.

---

## 2. Signed Financial Accounting Convention

PEIT employs a single-entry signed cash-flow accounting model that clearly separates money leaving a consumer's accounts from money entering:

| Event Type (`event_type`) | Flow Direction | Sign Convention (`paid_total`) | Example |
|---|---|---|---|
| `recurring` | Outflow (Expense) | **Negative** (`paid_total < 0`) | Monthly milk subscription: `-2.50 MXN` |
| `one_off` | Outflow (Expense) | **Negative** (`paid_total < 0`) | Dining out, electronics: `-45.50 MXN` |
| `income` | Inflow (Revenue) | **Positive** (`paid_total > 0`) | Salary, dividend, gift: `+3000.00 MXN` |
| `refund` | Inflow (Reimbursement) | **Positive** (`paid_total > 0`) | Returned merchandise: `+12.00 MXN` |
| `transfer` | Account Transfer | **Signed** (Account-relative) | Outflow from checking: `-500.00 MXN` |

### 2.1 Balance Reporting Semantics

When running `peit --ledger <path> --balance`:
- **Total Income**: Sum of all `income` events (`paid_total > 0`).
- **Total Expenditure**: Reported as a positive display magnitude representing the absolute sum of all consumption outflows (`recurring` and `one_off`).
- **Net Transfers**: Algebraic sum of `transfer` events for the selected account.
- **Net Refunds**: Sum of all `refund` events.
- **Ending Net Balance**: The exact algebraic sum of all signed transactions:
  $$\text{Net Balance} = \sum \text{paid\_total} = \text{Total Income} - \text{Total Expenditure} + \text{Net Transfers} + \text{Net Refunds}$$

---

## 3. Schema & Field Reference

Every transaction in the ledger conforms to the `LedgerEntry` schema, combining raw receipt line observations with tracking metadata:

| Field | Python Type | SQLite Type | Description |
|---|---|---|---|
| `entry_id` | `str` | `TEXT PRIMARY KEY` | Deterministic SHA-256 hash (64 hex characters) computed from transaction identity 4-tuple. |
| `month` | `str` (`@property`) | `TEXT NOT NULL` | Expenditure month in `YYYY-MM` format derived from `receipt_date[:7]` (indexed in SQLite). |
| `receipt_id` | `str` | `TEXT NOT NULL` | Origin receipt code or unique transaction ID (`TXN-YYYYMMDD-...`). |
| `receipt_date` | `str` | `TEXT NOT NULL` | Transaction date in `YYYY-MM-DD` ISO format (indexed). |
| `account` | `str` | `TEXT NOT NULL` | Target financial account, e.g. `default:checking` or `savings:emergency` (indexed). |
| `merchant` | `str` | `TEXT NOT NULL` | Merchant or counterparty name (indexed). |
| `item` | `str` | `TEXT NOT NULL` | Normalized lowercase descriptor used for basket matching across periods. |
| `brand` | `str` | `TEXT NOT NULL` | Manufacturer or brand name (e.g., `Lala`, `Alpura`). |
| `category` | `str` | `TEXT NOT NULL` | Consumption or budget category, e.g. `Food and beverages` (indexed). |
| `quantity` | `float` | `REAL NOT NULL` | Quantity purchased (defaults to `1.0` for manual events). |
| `pack_size` | `float` | `REAL NOT NULL` | Units per pack (e.g. `1.0`, `6.0`, `12.0`, defaults to `1.0`). |
| `unit` | `str` | `TEXT NOT NULL` | Unit of measure (`L`, `kg`, `piece`, `unit`). |
| `unit_price` | `float` | `REAL NOT NULL` | Unit price within pack before discounts/taxes. |
| `currency` | `str` | `TEXT NOT NULL` | Standard 3-letter currency code (e.g. `MXN`, `USD`). |
| `discount` | `float` | `REAL NOT NULL` | Applied discount amount. |
| `fee` | `float` | `REAL NOT NULL` | Applied surcharge or service fee. |
| `tax` | `float` | `REAL NOT NULL` | Value-added or sales tax. |
| `deposit` | `float` | `REAL NOT NULL` | Deposit amount (e.g. bottle deposit). |
| `paid_total` | `float` | `REAL NOT NULL` | Signed net transaction total (negative for outflows, positive for inflows). |
| `event_type` | `str` | `TEXT NOT NULL` | One of: `recurring`, `one_off`, `income`, `transfer`, `refund` (indexed). |
| `store_tier` | `str` | `TEXT NOT NULL` | Store quality or tier bracket (`A`, `B`, `C`, `D`, `E`). |
| `store_rating` | `float` | `REAL NOT NULL` | Store satisfaction rating (`1.0` to `5.0`). |
| `brand_tier` | `str` | `TEXT NOT NULL` | Brand quality or tier bracket (`A`, `B`, `C`, `D`, `E`). |
| `brand_rating` | `float` | `REAL NOT NULL` | Brand satisfaction rating (`1.0` to `5.0`). |
| `product_tier` | `str` | `TEXT NOT NULL` | Product quality or tier bracket (`A`, `B`, `C`, `D`, `E`). |
| `product_rating` | `float` | `REAL NOT NULL` | Product satisfaction rating (`1.0` to `5.0`). |
| `availability` | `str` | `TEXT NOT NULL` | Item stock availability status (`in_stock`, `low_stock`, `out_of_stock`, `discontinued`). |
| `notes` | `str` | `TEXT NOT NULL` | Optional user annotations or transaction details. |
| `recorded_at` | `str` | `TEXT NOT NULL` | ISO 8601 UTC timestamp when the record entered the ledger. |

### 3.1 SQLite Projection Cache Schema

The sibling database projection cache (`<name>.db`) maintains the following table structure:

```sql
CREATE TABLE IF NOT EXISTS entries (
    entry_id TEXT PRIMARY KEY,
    month TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    receipt_date TEXT NOT NULL,
    account TEXT NOT NULL,
    merchant TEXT NOT NULL,
    item TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity REAL NOT NULL,
    pack_size REAL NOT NULL,
    unit TEXT NOT NULL,
    unit_price REAL NOT NULL,
    currency TEXT NOT NULL,
    discount REAL NOT NULL,
    fee REAL NOT NULL,
    tax REAL NOT NULL,
    deposit REAL NOT NULL,
    paid_total REAL NOT NULL,
    event_type TEXT NOT NULL,
    store_tier TEXT NOT NULL,
    store_rating REAL NOT NULL,
    brand_tier TEXT NOT NULL,
    brand_rating REAL NOT NULL,
    product_tier TEXT NOT NULL,
    product_rating REAL NOT NULL,
    availability TEXT NOT NULL,
    notes TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_month ON entries(month);
CREATE INDEX IF NOT EXISTS idx_entries_receipt_date ON entries(receipt_date);
CREATE INDEX IF NOT EXISTS idx_entries_account ON entries(account);
CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category);
CREATE INDEX IF NOT EXISTS idx_entries_merchant ON entries(merchant);
CREATE INDEX IF NOT EXISTS idx_entries_event_type ON entries(event_type);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

---

## 4. Deduplication & Idempotency Protocol

To prevent double-counting when CSV receipt files are re-imported or when multiple batches overlap, PEIT generates a deterministic identity hash for every entry using a normalized 4-tuple:

$$\text{entry\_id} = \text{SHA-256}\Big(\text{receipt\_id} \mid \text{item} \mid \text{paid\_total}_{(\text{norm})} \mid \text{receipt\_date}\Big)$$

### 4.1 Numeric and Text Normalization

The `compute_entry_id` implementation normalizes components as follows:
```python
def compute_entry_id(
    receipt_id: str,
    item: str,
    paid_total: float | str,
    receipt_date: str,
) -> str:
  try:
    num_val = float(paid_total)
    norm_amount = f"{num_val:.6f}"
  except (ValueError, TypeError):
    norm_amount = str(paid_total).strip()

  raw = f"{str(receipt_id).strip()}|{str(item).strip()}|{norm_amount}|{str(receipt_date).strip()}"
  return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- Float amounts are normalized to six decimal places (`-2.500000`). Consequently, representations like `-2.5`, `-2.50`, and `-2.500` yield identical hashes.
- String components (`receipt_id`, `item`, `receipt_date`) are stripped of leading and trailing whitespace.
- Receipt identity is independent of the filename or staging path.

### 4.2 Ingestion Guarantees
- **First Import**: All rows in the CSV are hashed, written to the JSONL log, and indexed in SQLite (`imported=N, skipped=0`).
- **Duplicate Import (Idempotency)**: Re-running import on the same CSV detects that all `entry_id` values exist in the cache. Zero bytes are written to the JSONL log or SQLite database (`imported=0, skipped=N`).
- **Partial Overlap**: When an import contains both new and previously ingested items, only the novel entries are appended (`imported=K, skipped=M`).
- **Forced Re-import (`--force`)**: Replaces records in the SQLite cache using `INSERT OR REPLACE` and logs the imported items without failing on primary key conflicts.

---

## 5. Command-Line Interface (CLI) Guide

PEIT provides a clean, unified command-line tool accessible via `peit`:

### 5.1 Inflation Index Calculations (`--index`)

Computes fixed-basket price index, changing-basket expenditure index, item coverage,cand month-over-month (MoM) inflation from a standardized receipt CSV:

```bash
# Columnar terminal report
peit --index data/example_month.csv

# Machine-readable JSON output
peit --index data/example_month.csv --json
```

Sample output:
```text
month   | fixed_basket | changing_expenditure | coverage | MoM
--------+--------------+----------------------+----------+----
2026-01 |       100.00 |               100.00 |   100.0% | None
```

### 5.2 Ingesting Receipts into the Ledger (`--import`)

Imports receipt items from CSV into the designated ledger file with automatic deduplication:

```bash
# Ingest with default checking account
peit --ledger data/ledger.jsonl --import data/example_month.csv

# Ingest into specific account with force overwrite
peit --ledger data/ledger.jsonl --import data/example_month.csv \
  --account "credit:visa" \
  --force
```

Sample output:
```text
Import complete: 7 imported, 0 skipped.
Ledger: data/ledger.jsonl
```

### 5.3 Direct Transaction Addition (`--add`)

Appends ad-hoc transactions, salaries, refunds, or transfers directly to the ledger with full Schema attribute support:

```bash
# Add an expense with Schema attributes (amount automatically signed negative)
peit --ledger data/ledger.jsonl --add \
  --date 2026-03-05 \
  --amount -45.50 \
  --event-type one_off \
  --merchant "Corner Cafe" \
  --item "coffee and lunch" \
  --brand "Artisan Roasters" \
  --pack-size 1 \
  --store-tier "A" \
  --store-rating 5.0 \
  --brand-tier "A" \
  --brand-rating 5.0 \
  --product-tier "A" \
  --product-rating 5.0 \
  --category "Food and beverages"

# Add an income deposit
peit --ledger data/ledger.jsonl --add \
  --date 2026-03-01 \
  --amount 3000.00 \
  --event-type income \
  --merchant "Employer Inc" \
  --category "Income" \
  --notes "Monthly salary"
```

### 5.4 Financial Balance Inquiries (`--balance`)

Summarizes income, consumption expenditure, transfers, refunds, and net balance:

```bash
# Overall balance summary
peit --ledger data/ledger.jsonl --balance

# Balance filtered by month and account (with JSON output)
peit --ledger data/ledger.jsonl --balance \
  --month 2026-01 \
  --account "default:checking" \
  --json
```

Sample output:
```text
=== Financial Balance Summary ===
Total Income:            3000.00
Total Expenditure:        245.50
Net Transfers:           -500.00
Net Refunds:                0.00
---------------------------------
Net Balance:             2254.50

Monthly Breakdown:
  2026-01: Income=    3000.00, Exp=     245.50, Net=    2254.50
```

### 5.5 Filterable Transaction Inquiries (`--list`)

Retrieves chronological records filtered across any combination of criteria:

```bash
# List all transactions in a specific month and category
peit --ledger data/ledger.jsonl --list \
  --month 2026-01 \
  --category "Food and beverages"

# Filter by merchant and output as JSON
peit --ledger data/ledger.jsonl --list \
  --merchant "Example Market" \
  --json
```

Sample output:
```text
Date       | Receipt ID   | Merchant       | Category           | Type      |  Amount | Account
-----------+--------------+----------------+--------------------+-----------+---------+-----------------
2026-01-15 | receipt-001  | Example Market | Food and beverages | recurring |   -2.50 | default:checking
```

### 5.6 Category Expenditure Breakdown (`--breakdown`)

Aggregates consumption spending (`recurring` and `one_off` events only) by category,
computing percentage shares of household consumption:

```bash
peit --ledger data/ledger.jsonl --breakdown --month 2026-01
```

Sample output:
```text
Category           | Total Spent | Share (%) | Count
-------------------+-------------+-----------+------
Food and beverages |      150.00 |     61.10 |     4
Transport          |       95.50 |     38.90 |     2
-------------------+-------------+-----------+------
Total Expenditure  |      245.50 |    100.0% |     6
```

### 5.7 Cache Maintenance (`--rebuild-cache`)

Forces a full recreation of the sibling SQLite database projection from the JSONL log:

```bash
peit --ledger data/ledger.jsonl --rebuild-cache
```

### 5.8 Interactive HTML Dashboard on Demand (`--html` / `--dashboard`)

Generates an interactive, self-contained HTML5 analytics dashboard with cash-flow analysis, category spending distributions, Bennett economic decomposition, and a real-time searchable transaction ledger:

```bash
# Generate dashboard at default path (<ledger_stem>_dashboard.html)
peit --ledger data/ledger.jsonl --html

# Specify custom output path and open automatically in browser
peit --ledger data/ledger.jsonl --html -o reports/dashboard.html --open

# Filter by month and category
peit --ledger data/ledger.jsonl --html \
  --month 2026-01 \
  --category "Food and beverages"
```

> [!NOTE]
> HTML visualizers are strictly generated on-demand by calling the PEIT CLI with `--html` (or `--dashboard`). They are never generated automatically during standard data operations. See [`doc/dashboard.md`](dashboard.md) for full visualizer details.

---

## 6. Testing & Quality Assurance Architecture

PEIT maintains an extensive, scientific test suite adhering to zero-regression
and evidence-based verification standards.

### 6.1 The 8 Ledger Test Suites (`test/test_ledger.py`)

The ledger test matrix is divided into eight discrete functional suites:

1. **Suite 1: Deterministic Identity & Serialization**:
  - Tests `compute_entry_id` 4-tuple SHA-256 hash stability (`receipt_id|item|paid_total|receipt_date`), float formatting normalization (`-2.5` vs `-2.500`), hash sensitivity to field changes, and lossless dictionary serialization roundtrips for Schema `LedgerEntry`.
2. **Suite 2: Storage Engine & Self-Healing Synchronization**:
  - Tests initial creation of dual storage, dual-write atomicity, staleness detection upon external JSONL appends, corrupted/deleted SQLite cache recovery, and explicit rebuilds. Validates SQLite table schema alignment for `item`, `brand`, `pack_size`, and `unit_price`.
3. **Suite 3: CSV Ingestion, Deduplication & Idempotency**:
  - Tests complete CSV imports of Schema receipts, exact duplicate re-import idempotency (`skipped=N`), partial duplicate handling, forced overwrites (`--force`), schema validation rejections, and custom account routing.
4. **Suite 4: Cash Flow, Balances & Account Isolation**:
   - Tests signed arithmetic invariants, single-month balance calculations, multi-month running balance rollups, multi-account isolation, and zeroed metrics on empty ledgers.
5. **Suite 5: Querying & Search Filters**:
   - Tests multi-attribute conjunctive filtering (`month`, `category`, `merchant`, `event_type`, `account`) and chronological ordering (`ORDER BY receipt_date ASC, receipt_id ASC`).
6. **Suite 6: Expenditure Analytics & Breakdown**:
   - Tests strict exclusion of non-consumption flows (income, transfers) from expenditure calculations, percentage precision summing to 100.0%, month isolation, and zero-expense edge cases.
7. **Suite 7: Manual Cash Flow Entry (`--add`)**:
  - Tests direct addition of one-off expenses and income events with Schema fields (`--brand`, `--pack-size`, `--unit-price`), UUID receipt generation, and input validation invariants (date format, numeric values, allowed event types).
8. **Suite 8: End-to-End Command-Line Interface (`test/test_cli.py`)**:
   - Tests CLI argument parsing, `--index` calculation in table and JSON formats, `--import`, `--balance`, `--list`, `--breakdown`, `--add`, `--rebuild-cache`, error handling, and standard exit codes.

Additionally, `test/test_core.py` validates underlying price index formulas (`core.py` computes an unweighted Carli price index and changing-basket expenditure index, while `dashboard.py` computes base-weighted Laspeyres index for personal MoM inflation), and receipt schema parsing.

### 6.2 The Scientific Test Runner (`test/run_tests.sh`)

PEIT provides a standardized Bash runner script executing **142 unit and integration tests** across 10 suites:

```bash
# View usage and options
bash test/run_tests.sh --help

# List available suites and test counts
bash test/run_tests.sh --list

# Execute all 142 test cases
bash test/run_tests.sh --all

# Execute a specific suite
bash test/run_tests.sh --suite profiler      # Profile generator, market dynamics & CLI (40 tests)
bash test/run_tests.sh --suite ledger        # Signed ledger, SQLite cache, balances & filters (26 tests)
bash test/run_tests.sh --suite dashboard     # Multi-graph dashboard visualizer & KPI metrics (14 tests)
bash test/run_tests.sh --suite cli           # Command-line interface parsing & commands (14 tests)
bash test/run_tests.sh --suite server        # Desktop sync daemon & REST endpoints (11 tests)
bash test/run_tests.sh --suite core          # Core Schema validation & index algorithms (10 tests)
bash test/run_tests.sh --suite ocr           # Heuristic spatial OCR parser & models (9 tests)
bash test/run_tests.sh --suite ocr_canvas    # Synthetic thermal canvas & distortions (7 tests)
bash test/run_tests.sh --suite ocr_benchmark # Real receipt photo evaluation harness (6 tests)
bash test/run_tests.sh --suite mobile        # Mobile chunked sync & mDNS discovery (5 tests)

# Filter tests by keyword pattern
bash test/run_tests.sh -k "deterministic"
bash test/run_tests.sh -k "balance"

# Verbose output mode
bash test/run_tests.sh -v --suite ledger
```

The test runner automatically configures `PYTHONPATH=src`, tracks elapsed duration,
renders formatted colored status summaries, and preserves pytest exit codes for CI/CD.

---

## 7. Synthetic Dataset & Profile Generation

PEIT provides two simulation mechanisms: the new modular stochastic **Profile × Market simulation engine** (`src/peit/profiler/`) and the legacy procedural generator (`util/generate_dataset.py`).

### 7.1 Profile × Market Engine (`peit.profiler`)

The profiler cleanly decouples consumer behavior (Profile) from price dynamics (Market):

$$\text{Profile (Consumer)} \times \text{Market (Prices)} \times \text{Seed (Randomness)} \longrightarrow \text{Receipts (CSV v2)} + \text{Ground Truth (JSON)}$$

- **Profile JSON (`config/profiles/`)**: Defines consumer identity, spending baskets, brand preferences, store loyalty weights, co-living scheduling policies (purchase count, deterministic periodic intervals, and Weibull renewal depletion hazard), and income sources with Gaussian volatility.
- **Market JSON (`config/markets/`)**: Defines catalog base prices, latent Gaussian inflation drift, $(s, S)$ menu-cost sticky price bands, Calvo hazard price reviews, dual-mode charm pricing (grid step quantization + psychological endings like `.99`), and volume discount pack tiers (`pack_size` $\to$ `unit_price` multiplier).
- **Ground Truth Manifest (`ground_truth.json`)**: Exports a complete configuration and seed snapshot ensuring 100% deterministic simulation reproducibility.

#### Profiler CLI Commands:
```bash
# Generate Schema receipts and ground truth manifest
python -m peit.profiler generate \
  --profile config/profiles/alice.json \
  --market config/markets/mexico_2024.json \
  --seed 42 \
  -o data/Alice/receipts.csv \
  --manifest data/Alice/ground_truth.json

# Generate and directly import into the signed ledger
python -m peit.profiler generate \
  --profile config/profiles/alice.json \
  --market config/markets/mexico_2024.json \
  --seed 42 \
  -o data/Alice/receipts.csv \
  --manifest data/Alice/ground_truth.json \
  --import-ledger data/Alice/ledger.jsonl
```

### 7.2 Legacy Dataset Generator (`util/generate_dataset.py`)

PEIT also preserves the legacy monolithic generator (`util/generate_dataset.py`) for existing benchmark datasets:

```bash
# 1. Canonical 10,000-row demonstration dataset (60 months, 10 categories, 3% inflation)
python3 util/generate_dataset.py --profile default

# 2. Alice persona simulation (24 months, bi-weekly salary, Aguinaldo, rent increases)
python3 util/generate_dataset.py --profile alice --import-ledger

# 3. Custom parameterized generation
python3 util/generate_dataset.py --profile alice -o data/custom.csv --start-year 2025 --months 12 --account "personal:checking"
```

### 7.3 Available Profiles Comparison

| Feature | `default` Profile | `alice` Profile |
|---|---|---|
| **Purpose** | Canonical large-scale index demonstration & edge-case test suite | Realistic individual cash-flow & macroeconomic life simulation |
| **Default Volume** | 10,000 transaction rows | 960 transaction rows (40 transactions/month) |
| **Default Horizon** | 60 months (`2021-01` through `2025-12`) | 24 months (`2024-01` through `2025-12`) |
| **Annual Inflation** | 3.0% compound annual index | 4.5% compound annual index with seasonal sine volatility |
| **Income Modeling** | Semi-annual family gift transfers (`+3000.00 MXN`) | Bi-weekly payroll deposits (`+22500.00 MXN` on 15th & 30th) + December statutory bonus (*Aguinaldo*, `+45000.00 MXN`) |
| **Housing & Utilities**| Fixed rent & maintenance | Annual lease step-increases (`12000.00` → `12600.00`), bimonthly CFE electricity, and pipeline natural gas |
| **Consumption Goods** | 10 canonical categories (catalog of 30+ goods/services) | 12 weekly grocery staples, specialty oat milk coffee, bistro dining, gym membership, video/audio 4K streaming |
| **Healthcare** | General prescriptions & routine doctor visits | Monthly multivitamins & annual June dental cleaning prophylaxis |
| **Transport** | Transit passes, tolls, parking, vehicle maintenance | Bi-weekly integrated Metro passes & ride-hailing with service fees and value-added tax |
| **Financial Transfers**| Generic inter-account movements | Monthly automatic savings allocation to CETES treasury funds (`-10000.00 MXN`) |
| **Adjustments & Refunds**| Explicit signed discount, deposit, fee, and tax rows | Promotional coupon discounts and occasional apparel return credits (`+650.00 MXN`) |
| **Default Output Path** | `data/example_month.csv` | `data/Alice/receipts.csv` |
