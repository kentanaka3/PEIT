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

Each row from receipt CSV or direct entry maps to a `LedgerEntry`:

| Field | Type | Description |
|---|---|---|
| `entry_id` | `str` | Deterministic SHA-256 hash of `(source_file, receipt_id, item_normalized, paid_total, receipt_date)`. Used for deduplication. |
| `month` | `str` | Format `YYYY-MM`. |
| `receipt_id` | `str` | Receipt identifier or generated event ID (e.g. `TXN-YYYYMMDD-...`). |
| `receipt_date` | `str` | Format `YYYY-MM-DD`. |
| `account` | `str` | Target account (defaults to `"default:checking"`). |
| `merchant` | `str` | Merchant name or counterparty. |
| `item_raw` | `str` | Raw item description. |
| `item_normalized` | `str` | Normalized item name. |
| `category` | `str` | Spending/budget category (e.g., `"Food and beverages"`, `"Transfers and gifts"`). |
| `quantity` | `float` | Quantity (defaults to `1.0` for non-item events). |
| `unit` | `str` | Unit of measure (e.g., `L`, `kg`, `piece`, `unit`). |
| `shelf_unit_price`| `float` | Unit price before taxes/discounts. |
| `currency` | `str` | 3-letter currency code (e.g., `MXN`, `USD`). |
| `discount` | `float` | Applied discount. |
| `fee` | `float` | Associated fee. |
| `tax` | `float` | Tax amount. |
| `deposit` | `float` | Deposit amount. |
| `paid_total` | `float` | **Signed net amount**: negative for expenses/outflows, positive for income/refunds/inflows. |
| `event_type` | `str` | One of `recurring`, `one_off`, `transfer`, `refund`, `income`. |
| `source_file` | `str` | Origin CSV filename or `"manual_entry"`. |
| `notes` | `str` | Additional context or annotations. |
| `recorded_at` | `str` | ISO 8601 timestamp of when the entry was written to the ledger. |

### 2.3 Dual Backend Persistence

1. **Authoritative JSONL Log** (`<name>.jsonl`):
   - Every line is a valid JSON object matching `LedgerEntry.to_dict()`.
   - Append-only. Source of truth for audit, version control, and provenance.
2. **Sibling SQLite Cache** (`<name>.db`):
   - Table `entries`: Indexed by `entry_id` (PRIMARY KEY), `month`, `receipt_date`, `account`, `category`, `merchant`, `event_type`.
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
2. Implement JSONL reader/writer with deterministic entry ID generation.
3. Implement `LedgerDatabase` using Python standard library `sqlite3`:
   - Schema creation (`entries` and `meta` tables).
   - Fast batch upsert with `INSERT OR IGNORE` (or `INSERT OR REPLACE` when `--force`).
   - Cache staleness validation (`check_cache_valid()`, `sync_cache()`, `rebuild_cache()`).
4. Implement query methods:
   - `get_balance(account=None, month=None)`
   - `list_entries(month=None, category=None, merchant=None, event_type=None, account=None)`
   - `get_category_breakdown(month=None, account=None)`
5. Implement `import_csv(csv_path, account, force=False)` reusing `peit.core.read_csv`.
6. Implement `add_entry(...)` for direct event creation.

### Phase 2: CLI Integration in `peit/cli.py`
1. Rebuild argparse options:
   - Group 1: `--index <csv>` for inflation calculation.
   - Group 2: `--ledger <path>` with actions `--import`, `--rebuild-cache`, `--add`, `--balance`, `--list`, `--breakdown`.
   - Filter flags: `--month`, `--category`, `--merchant`, `--event-type`, `--account`, `--force`.
   - Output flag: `--json`.
2. Formatters for terminal tables (clean columnar alignment) and JSON serialization.

### Phase 3: Testing & Verification
1. `test/test_ledger.py`:
   - Test `compute_entry_id` determinism and collision avoidance.
   - Test CSV import with deduplication (skipping duplicate entries, `--force` behavior).
   - Test non-purchase event types (`income`, `transfer`, `refund`).
   - Test balance calculation accuracy across months and accounts.
   - Test SQLite cache rebuild and staleness detection.
   - Test category breakdown aggregation and percentages.
2. `test/test_cli.py`:
   - Test `peit --index` produces price indices.
   - Test `peit --ledger <path> --import <csv>` creates both `.jsonl` and `.db`.
   - Test `peit --ledger <path> --balance` and `--json`.
   - Test `peit --ledger <path> --list` with filters.
   - Test `peit --ledger <path> --add`.
3. Validate repository health and documentation scripts:
   - `bash LLM/scripts/handler.sh validate --root "$PWD"`
   - `git status --short`

---

## 6. Verification Checklist

- [ ] `pytest test/` passes 100% with high coverage.
- [ ] Ingesting `data/example_month.csv` imports recurring, one-off, income, and transfer rows correctly.
- [ ] Re-importing `data/example_month.csv` reports 0 new entries imported (idempotent).
- [ ] `ledger.db` matches `ledger.jsonl` row counts and validates without errors.
- [ ] `peit --index data/example_month.csv` correctly outputs inflation statistics.
- [ ] No external dependencies introduced (pure standard library: `sqlite3`, `json`, `csv`, `hashlib`, `argparse`).

