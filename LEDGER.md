# Plan: Build PEIT Ledger System (`peit.ledger`)

This document outlines the detailed implementation plan for building the signed transaction ledger in PEIT as specified and agreed upon during the design interview.

---

## 1. Overview & Objectives

Build a typed, signed transaction ledger module in Python (`peit.ledger`) that:
- Ingests line-item receipt rows and non-purchase events (transfers, income, refunds).
- Maintains an **authoritative, append-only JSONL log** for transparency, auditability, and git friendliness.
- Maintains an **automatic sibling SQLite projection cache** (`ledger.db` next to `ledger.jsonl`) for high-performance indexed queries and balance calculations.
- Enforces **idempotency & deduplication** on import using deterministic entry hashes (`entry_id`).
- Provides clean, modern CLI flags under `peit` for:
  - Ingesting CSVs (`--import`)
  - Direct event addition (`--add`)
  - Balance summaries (`--balance`)
  - Filterable transaction inquiries (`--list`)
  - Expenditure breakdown by category (`--breakdown`)
  - Cache management (`--rebuild-cache`)
  - Standalone inflation index calculation (`--index`)
  - Machine-readable JSON output (`--json`)

---

## 2. Architecture & Data Model

### 2.1 File & Module Organization

```text
PEIT/
├── src/
│   └── peit/
│       ├── __init__.py        # Re-export ledger classes/functions
│       ├── core.py            # Core schema validation & price index calculations
│       ├── ledger.py          # [NEW] Ledger core: Entry data model, JSONL IO, SQLite projection, query engine
│       └── cli.py             # [MODIFY] Refactored clean CLI with --index and --ledger flags
├── test/
│   ├── test_core.py           # Existing core tests
│   ├── test_ledger.py         # [NEW] Unit & integration tests for ledger and SQLite cache
│   └── test_cli.py            # [NEW] CLI integration tests
└── PLAN.md                    # This plan
```

### 2.2 Data Model: `LedgerEntry`

Each row from receipt CSV or direct entry maps to a Schema `LedgerEntry`:

| Field | Type | Description |
|---|---|---|
| `entry_id` | `str` | Deterministic SHA-256 hash of `(receipt_id, item, paid_total, receipt_date)`. Used for deduplication. |
| `month` | `str` | Format `YYYY-MM` (`@property` derived from `receipt_date[:7]`). |
| `receipt_id` | `str` | Receipt identifier or generated event ID (e.g. `TXN-YYYYMMDD-...`). |
| `receipt_date` | `str` | Format `YYYY-MM-DD`. |
| `account` | `str` | Target account (defaults to `"default:checking"`). |
| `merchant` | `str` | Merchant name or counterparty. |
| `item` | `str` | Normalized lowercase item name. |
| `brand` | `str` | Brand or manufacturer name (e.g. `Lala`, `Alpura`). |
| `category` | `str` | Spending/budget category (e.g., `"Food and beverages"`, `"Transfers and gifts"`). |
| `quantity` | `float` | Quantity (defaults to `1.0` for non-item events). |
| `pack_size` | `float` | Units per pack (e.g. `1.0`, `6.0`, `12.0`, defaults to `1.0`). |
| `unit` | `str` | Unit of measure (e.g., `L`, `kg`, `piece`, `unit`). |
| `unit_price`| `float` | Unit price within pack before taxes/discounts. |
| `currency` | `str` | 3-letter currency code (e.g., `MXN`, `USD`). |
| `discount` | `float` | Applied discount amount. |
| `fee` | `float` | Associated fee. |
| `tax` | `float` | Tax amount. |
| `deposit` | `float` | Deposit amount. |
| `paid_total` | `float` | **Signed net amount**: negative for expenses/outflows, positive for income/refunds/inflows. |
| `event_type` | `str` | One of `recurring`, `one_off`, `transfer`, `refund`, `income`. |
| `store_tier` | `str` | Store quality or tier bracket (`A`, `B`, `C`, `D`, `E`). |
| `store_rating` | `float` | Store satisfaction rating (`1.0` to `5.0`). |
| `brand_tier` | `str` | Brand quality or tier bracket (`A`, `B`, `C`, `D`, `E`). |
| `brand_rating` | `float` | Brand satisfaction rating (`1.0` to `5.0`). |
| `product_tier` | `str` | Product quality or tier bracket (`A`, `B`, `C`, `D`, `E`). |
| `product_rating` | `float` | Product satisfaction rating (`1.0` to `5.0`). |
| `notes` | `str` | Additional context or annotations. |
| `recorded_at` | `str` | ISO 8601 UTC timestamp of when the entry was written to the ledger. |

### 2.3 Dual Backend Persistence

1. **Authoritative JSONL Log** (`<name>.jsonl`):
   - Every line is a valid JSON object matching `LedgerEntry.to_dict()`.
   - Append-only. Source of truth for audit, version control, and provenance.
2. **Sibling SQLite Cache** (`<name>.db`):
  - Table `entries`: Schema columns: `entry_id` (PRIMARY KEY), `month`, `receipt_id`, `receipt_date`, `account`, `merchant`, `item`, `brand`, `category`, `quantity`, `pack_size`, `unit`, `unit_price`, `currency`, `discount`, `fee`, `tax`, `deposit`, `paid_total`, `event_type`, `store_tier`, `store_rating`, `brand_tier`, `brand_rating`, `product_tier`, `product_rating`, `availability`, `notes`, `recorded_at`.
   - Indexed by: `month`, `receipt_date`, `account`, `category`, `merchant`, `event_type`.
   - Table `meta`: Stores `jsonl_mtime`, `jsonl_size`, `entry_count` to detect out-of-band modifications to the JSONL file.
   - Synchronization logic:
     - On any write operation (`--import`, `--add`), append to JSONL and insert into SQLite within a transaction.
     - On read operations (`--balance`, `--list`, `--breakdown`), compare JSONL file size and modification time with `meta`. If modified or missing, automatically re-project all rows from JSONL into SQLite.
     - Support explicit `--rebuild-cache` to force full rebuild from the JSONL log.

### 2.4 Transfer & Event Type Convention

- Outflow (purchase, fee): Negative `paid_total` (e.g., `-250.00`).
- Inflow (salary, income): Positive `paid_total` (e.g., `+3000.00`).
- Refund: Positive `paid_total` (reimbursement).
- Transfer: Single-entry on primary `account` with `event_type="transfer"`. Positive or negative `paid_total` reflecting the net change on that account.

---

## 3. Query & Reporting Features

### 3.1 Balance Summary (`--balance`)
- Aggregates by `account` and optionally `--month`.
- Computes:
  - Total Income (`event_type == 'income'`)
  - Total Expenditure (`event_type in ('recurring', 'one_off')`)
  - Net Transfers (`event_type == 'transfer'`)
  - Net Refunds (`event_type == 'refund'`)
  - Ending Net Balance = sum of all signed `paid_total`.

### 3.2 Filterable Transaction List (`--list`)
- Supports combination filters:
  - `--month YYYY-MM`
  - `--category <category>`
  - `--merchant <merchant>`
  - `--event-type <event_type>`
  - `--account <account>`
- Outputs entries chronologically by `receipt_date`, formatted as a tabular report or JSON.

### 3.3 Expenditure Breakdown (`--breakdown`)
- Aggregates spending strictly for consumption events (`recurring`, `one_off`).
- Groups by `category`, calculating total spent and percentage of total expenditure.
- Filters by `--month` or shows all-time breakdown.

### 3.4 Output Formatting
- Default: Clean ASCII terminal table.
- `--json`: Standard structured JSON output for scripting and web frontend integration.

---

## 4. CLI Interface Design (`peit/cli.py`)

No backwards compatibility needed; replaced with clean, unambiguous flags:

```bash
# Calculate inflation index
peit --index data/example_month.csv [--json]

# Ledger: Import CSV receipts/events (deduplicated by entry_id)
peit --ledger data/ledger.jsonl --import data/example_month.csv [--account default:checking] [--force]

# Ledger: Rebuild SQLite projection cache from JSONL
peit --ledger data/ledger.jsonl --rebuild-cache

# Ledger: Direct event addition
peit --ledger data/ledger.jsonl --add \
     --date 2026-03-01 \
     --amount 3000.00 \
     --event-type income \
     --merchant "Employer Inc" \
     --item "salary" \
     --brand "" \
     --pack-size 1 \
     [--category "Income"] [--account default:checking] [--notes "Monthly salary"]

# Ledger: Inquiries
peit --ledger data/ledger.jsonl --balance [--month 2026-01] [--account default:checking] [--json]
peit --ledger data/ledger.jsonl --list [--month 2026-01] [--category Food] [--json]
peit --ledger data/ledger.jsonl --breakdown [--month 2026-01] [--json]
```

---

## 5. Phased Implementation Steps

### Phase 1: `peit/ledger.py` Core & Storage Engine
1. Define `LedgerEntry` dataclass with `compute_entry_id()` and serialization helpers.
2. Implement JSONL reader/writer with deterministic 4-tuple entry ID generation.
3. Implement `LedgerDatabase` using Python standard library `sqlite3`:
  - Schema creation (`entries` with Schema fields and `meta` tables).
   - Fast batch upsert with `INSERT OR IGNORE` (or `INSERT OR REPLACE` when `--force`).
   - Cache staleness validation (`check_cache_valid()`, `sync_cache()`, `rebuild_cache()`).
4. Implement query methods:
   - `get_balance(account=None, month=None)`
   - `list_entries(month=None, category=None, merchant=None, event_type=None, account=None)`
   - `get_category_breakdown(month=None, account=None)`
5. Implement `import_csv(csv_path, account, force=False)` reusing `peit.core.read_csv`.
6. Implement `add_entry(...)` for direct event creation with Schema attributes.

### Phase 2: CLI Integration in `peit/cli.py`
1. Rebuild argparse options:
   - Group 1: `--index <csv>` for inflation calculation.
   - Group 2: `--ledger <path>` with actions `--import`, `--rebuild-cache`, `--add`, `--balance`, `--list`, `--breakdown`.
   - Filter flags: `--month`, `--category`, `--merchant`, `--event-type`, `--account`, `--force`.
   - Direct add flags: `--date`, `--amount`, `--item`, `--brand`, `--pack-size`, `--unit-price`, `--notes`.
   - Output flag: `--json`.
2. Formatters for terminal tables (clean columnar alignment) and JSON serialization.

### Phase 3: Testing & Verification
1. `test/test_ledger.py`: Unit and integration tests for data modeling, dual storage, caching, deduplication, financial calculations, and query filters.
2. `test/test_cli.py`: End-to-end command-line interface tests for all flags, formatters, and exit codes.
3. Validate repository health and documentation scripts:
   - `bash LLM/scripts/handler.sh validate --root "$PWD"`
   - `git status --short`

---

## 6. Comprehensive Test Design & Test Matrix

To guarantee scientific reliability, financial correctness, and bulletproof reproducibility, the test suite is structured into eight distinct test suites with concrete scenarios:

### Suite 1: Data Modeling, Serialization & Hashing (`test/test_ledger.py`)
- **T1.1: Deterministic Entry ID Consistency**:
  - *Given*: Fixed fields for `receipt_id`, `item`, `paid_total`, `receipt_date`.
  - *When*: `compute_entry_id()` is called multiple times.
  - *Then*: Returns the exact same 64-character SHA-256 hex string every time.
- **T1.2: Numeric Formatting Normalization in Hashing**:
  - *Given*: Amounts formatted as `-2.5`, `-2.50`, and `-2.500`.
  - *When*: Computing `entry_id`.
  - *Then*: Normalizes float strings before hashing so all three produce identical IDs.
- **T1.3: Hash Collision & Sensitivity**:
  - *Given*: An entry with base fields `("rec-01", "milk 1 l", -2.5, "2026-01-15")`.
  - *When*: Mutating one field at a time (`receipt_id`, `item`, `paid_total`, `receipt_date`).
  - *Then*: Each mutation produces a distinctly different `entry_id`.
- **T1.4: Serialization Roundtrip**:
  - *Given*: A complete Schema `LedgerEntry` with all fields populated (`description`, `item`, `brand`, `pack_size`, `unit_price`, etc.).
  - *When*: Serialized via `to_dict()` and deserialized via `from_dict()`.
  - *Then*: Output entry equals the input entry exactly, preserving types (`float`, `str`).

### Suite 2: Dual Storage Backend & SQLite Cache Projection (`test/test_ledger.py`)
- **T2.1: Initial Storage Creation**:
  - *Given*: Non-existent file paths.
  - *When*: Writing the first entry to `my_ledger.jsonl`.
  - *Then*: Both `my_ledger.jsonl` and `my_ledger.db` are created; SQLite schema has `entries` and `meta` tables with indexes.
- **T2.2: Dual-Write Atomicity & Consistency**:
  - *Given*: A batch of 10 entries written via `LedgerDatabase`.
  - *When*: Checking both storage layers.
  - *Then*: Exactly 10 JSON lines exist in `.jsonl`, exactly 10 rows exist in `entries` table, and `meta` stores correct row count and file metadata.
- **T2.3: Staleness Detection on External JSONL Append**:
  - *Given*: A synced SQLite cache.
  - *When*: An external process directly appends 3 valid JSON lines to `.jsonl`.
  - *Then*: On the next query, `LedgerDatabase` detects changed file size/mtime, automatically projects the 3 new entries into SQLite, and returns updated results.
- **T2.4: Corrupted or Deleted Cache Recovery**:
  - *Given*: A valid `ledger.jsonl` and a deleted or truncated `ledger.db`.
  - *When*: Any read query (`get_balance()`, `list_entries()`) is performed.
  - *Then*: The SQLite cache is transparently regenerated from `ledger.jsonl` without errors or data loss.
- **T2.5: Explicit Cache Rebuild (`rebuild_cache`)**:
  - *Given*: An existing ledger.
  - *When*: Calling `rebuild_cache()`.
  - *Then*: Drops all SQLite tables, recreates schema and indexes, repopulates from `ledger.jsonl`, and updates `meta`.

### Suite 3: CSV Ingestion, Deduplication & Idempotency (`test/test_ledger.py`)
- **T3.1: Full CSV Ingestion**:
  - *Given*: `data/example_month.csv` (containing recurring, one_off, income, and transfer rows).
  - *When*: `import_csv()` is executed.
  - *Then*: Returns `imported=7, skipped=0`; all rows appear in both JSONL and SQLite.
- **T3.2: Exact Duplicate Re-import (Idempotency)**:
  - *Given*: Already imported `data/example_month.csv`.
  - *When*: Re-running `import_csv()` on the exact same file.
  - *Then*: Returns `imported=0, skipped=7`; JSONL file and SQLite database remain unchanged (no duplicate entries).
- **T3.3: Partial Duplicate CSV**:
  - *Given*: A CSV containing 4 already-imported rows and 3 newly added rows.
  - *When*: Ingesting the CSV.
  - *Then*: Returns `imported=3, skipped=4`; only the 3 new rows are appended to JSONL and SQLite.
- **T3.4: Force Ingestion (`force=True`)**:
  - *Given*: Already imported rows.
  - *When*: Ingesting with `force=True`.
  - *Then*: Updates/overwrites existing records in SQLite and logs import, avoiding primary key constraint errors.
- **T3.5: Validation Failure Handling**:
  - *Given*: A CSV with missing required columns or malformed dates/currencies.
  - *When*: `import_csv()` is called.
  - *Then*: Raises `ValueError` or returns validation issues; zero rows are written to disk.
- **T3.6: Custom Account Assignment**:
  - *Given*: Ingesting a CSV with `account="savings:emergency"`.
  - *When*: Ingestion completes.
  - *Then*: All imported entries have `account == "savings:emergency"`.

### Suite 4: Financial Accounting & Balance Integrity (`test/test_ledger.py`)
- **T4.1: Signed Amount Invariant**:
  - *Given*: Expenditure rows (`recurring`, `one_off`) with negative `paid_total`, income rows with positive `paid_total`, refunds with positive `paid_total`.
  - *When*: Ingested.
  - *Then*: Signed arithmetic preserves inflows (+) and outflows (-).
- **T4.2: Single-Month Balance Aggregation**:
  - *Given*: 1 income of +3000, 2 purchases of -40 and -26, 1 transfer of -500.
  - *When*: `get_balance(month="2026-01")` is called.
  - *Then*:
    - `total_income = 3000.00`
    - `total_expenditure = 66.00` (reported as positive display amount)
    - `net_transfers = -500.00`
    - `net_refunds = 0.00`
    - `net_balance = 2434.00` (3000 - 66 - 500).
- **T4.3: Multi-Month Running Balance**:
  - *Given*: Transactions across `2026-01` and `2026-02`.
  - *When*: Calling `get_balance()` across all time.
  - *Then*: Correctly rolls over net balances across months.
- **T4.4: Multi-Account Isolation**:
  - *Given*: Transactions split between `default:checking` and `credit:visa`.
  - *When*: Calling `get_balance(account="credit:visa")`.
  - *Then*: Returns balances exclusively for `credit:visa` without pollution from checking.
- **T4.5: Empty Ledger Query**:
  - *Given*: An empty ledger file.
  - *When*: `get_balance()` is queried.
  - *Then*: Returns zeroed financial metrics rather than errors.

### Suite 5: Filterable Queries & Search (`test/test_ledger.py`)
- **T5.1: Month Filter**:
  - *Given*: Entries spanning `2026-01`, `2026-02`, and `2026-03`.
  - *When*: Querying `list_entries(month="2026-02")`.
  - *Then*: Only returns entries where `month == "2026-02"`.
- **T5.2: Category Filter**:
  - *Given*: Entries across "Food and beverages", "Transfers and gifts", and "Transport".
  - *When*: Querying `list_entries(category="Food and beverages")`.
  - *Then*: Returns only food entries.
- **T5.3: Merchant Filter**:
  - *Given*: Entries with various merchants.
  - *When*: Querying `list_entries(merchant="Example Market")`.
  - *Then*: Returns matching merchant records.
- **T5.4: Event Type Filter**:
  - *Given*: Mixed event types (`recurring`, `one_off`, `income`, `transfer`, `refund`).
  - *When*: Querying `list_entries(event_type="income")`.
  - *Then*: Returns only income events.
- **T5.5: Combined Conjunction Filtering**:
  - *Given*: A populated ledger.
  - *When*: Querying `list_entries(month="2026-01", category="Food and beverages", event_type="recurring")`.
  - *Then*: Applies logical AND across all filters.
- **T5.6: Chronological Ordering**:
  - *Given*: Entries inserted in random order.
  - *When*: Querying `list_entries()`.
  - *Then*: Results are sorted ascending by `receipt_date` and `receipt_id`.

### Suite 6: Category Breakdown & Expenditure Analytics (`test/test_ledger.py`)
- **T6.1: Non-Consumption Event Exclusion**:
  - *Given*: An income row (+3000), a transfer (-500), and three expenses (-100 Food, -50 Transport, -50 Utilities).
  - *When*: `get_category_breakdown()` is called.
  - *Then*: Total consumption is 200.00; income and transfer categories are completely excluded.
- **T6.2: Percentage Calculation Precision**:
  - *Given*: Categories with spending: Food (100), Transport (50), Utilities (50).
  - *When*: Breakdown is computed.
  - *Then*: Food = 50.0%, Transport = 25.0%, Utilities = 25.0%; sum of percentages equals 100.0%.
- **T6.3: Month-Specific Breakdown**:
  - *Given*: Spending across two months.
  - *When*: `get_category_breakdown(month="2026-01")`.
  - *Then*: Only aggregates spending from `2026-01`.
- **T6.4: Zero Expenditure Month**:
  - *Given*: A month containing only income and transfers.
  - *When*: `get_category_breakdown(month="2026-01")`.
  - *Then*: Returns empty category list with total expenditure = 0.00 without division by zero.

### Suite 7: Direct Transaction Entry (`--add`) (`test/test_ledger.py`)
- **T7.1: Add One-Off Expense**:
  - *Given*: Date `2026-03-05`, amount `-45.50`, event_type `one_off`, merchant `Corner Cafe`.
  - *When*: `add_entry()` is invoked.
  - *Then*: Creates a valid `LedgerEntry` with generated `receipt_id`, appends to JSONL, and inserts into SQLite.
- **T7.2: Add Income Event**:
  - *Given*: Date `2026-03-01`, amount `2500.00`, event_type `income`, merchant `Consulting Client`.
  - *When*: `add_entry()` is invoked.
  - *Then*: Entry is added with positive `paid_total` and category `"Income"`.
- **T7.3: Add Validation Invariants**:
  - *Given*: Invalid date (`"invalid-date"`), non-numeric amount (`"abc"`), or invalid event_type (`"invalid_type"`).
  - *When*: `add_entry()` is invoked.
  - *Then*: Raises `ValueError` before modifying files.

### Suite 8: Command-Line Interface (`test/test_cli.py`)
- **T8.1: CLI Inflation Calculation (`--index`)**:
  - *Given*: Valid `data/example_month.csv`.
  - *When*: Running `peit --index data/example_month.csv`.
  - *Then*: Outputs inflation table, exits with code 0.
- **T8.2: CLI Inflation Calculation JSON (`--index --json`)**:
  - *Given*: Valid `data/example_month.csv`.
  - *When*: Running `peit --index data/example_month.csv --json`.
  - *Then*: Emits valid JSON parseable by `json.loads()`.
- **T8.3: CLI Ledger Import (`--ledger --import`)**:
  - *Given*: A new ledger path and `data/example_month.csv`.
  - *When*: Running `peit --ledger /tmp/ledger.jsonl --import data/example_month.csv`.
  - *Then*: Prints imported row count; creates `/tmp/ledger.jsonl` and `/tmp/ledger.db`.
- **T8.4: CLI Ledger Balance (`--ledger --balance`)**:
  - *Given*: A populated ledger.
  - *When*: Running `peit --ledger /tmp/ledger.jsonl --balance` and with `--json`.
  - *Then*: Formatted table output in text mode; valid JSON dictionary in JSON mode.
- **T8.5: CLI Ledger List with Filters (`--ledger --list`)**:
  - *Given*: A populated ledger.
  - *When*: Running `peit --ledger /tmp/ledger.jsonl --list --category Food --month 2026-01`.
  - *Then*: Prints table filtered to matching transactions.
- **T8.6: CLI Ledger Breakdown (`--ledger --breakdown`)**:
  - *Given*: A populated ledger.
  - *When*: Running `peit --ledger /tmp/ledger.jsonl --breakdown`.
  - *Then*: Prints category spend and percentages.
- **T8.7: CLI Ledger Add (`--ledger --add`)**:
  - *Given*: Arguments for `--date`, `--amount`, `--event-type`, `--merchant`.
  - *When*: Running `peit --ledger /tmp/ledger.jsonl --add ...`.
  - *Then*: Appends transaction and confirms addition on stdout.
- **T8.8: CLI Ledger Rebuild Cache (`--ledger --rebuild-cache`)**:
  - *Given*: A ledger with existing JSONL.
  - *When*: Running `peit --ledger /tmp/ledger.jsonl --rebuild-cache`.
  - *Then*: Successfully rebuilds SQLite DB and exits with code 0.
- **T8.9: CLI Error Handling & Exit Codes**:
  - *Given*: Missing required flags or invalid file paths.
  - *When*: Running invalid CLI commands.
  - *Then*: Outputs clear error messages to stderr and exits with status code 2.

---

## 7. Verification Checklist

- [ ] All 8 test suites implemented and passing 100% via `pytest test/`.
- [ ] Ingesting `data/example_month.csv` imports recurring, one-off, income, and transfer rows correctly.
- [ ] Re-importing `data/example_month.csv` reports 0 new entries imported (idempotent).
- [ ] `ledger.db` matches `ledger.jsonl` row counts and validates without errors.
- [ ] `peit --index data/example_month.csv` correctly outputs inflation statistics.
- [ ] No external dependencies introduced (pure standard library: `sqlite3`, `json`, `csv`, `hashlib`, `argparse`).
- [ ] Repository documentation and scaffold validation passes:
  - `bash LLM/scripts/handler.sh validate --root "$PWD"`
  - `git diff --check`
