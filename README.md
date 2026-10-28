# Personal Economic Inflation Tracker (PEIT)

This page is the project orientation. Implementation claims should be checked
against `src/peit/`, `config/`, and `test/`.

Personal inflation is often discussed through population-level indices that may
not represent an individual's consumption pattern. PEIT (Personal Economic
Inflation Tracker) is a community-driven financial ecosystem envisioned to
shift macroeconomic tracking from centralized institutions toward individual
consumers.

## Purpose and scope

Traditional economic metrics, such as the official Consumer Price Index (CPI),
rely on a generalized and relatively rigid basket of goods and services. This
macro-level approach can smooth volatile price changes and may not reflect
different lifestyles, cultural contexts, dietary choices, or local purchasing
patterns. PEIT's motivating premise is to treat each consumer as an
independent data node, capturing localized price movements for goods and
services at the point of sale.

The current project is a local-first prototype supporting transparent
receipt-line ingestion, signed financial ledger accounting, and personalized
price index derivation. It provides a Python toolkit for importing
personal receipt data, validating its schema, maintaining an authoritative
append-only transaction log, accelerating queries via an automatic SQLite
cache, and deriving comparable monthly price and expenditure indicators.

The conceptual model is:

```text
receipt source → normalized line observations → validated ledger
       → fixed-basket price index
       → changing-basket expenditure index
       → month-over-month comparison
```

`item`, amounts, and dates remain observations (`notes` stores optional freeform context). The `brand`,
category, unit, and quality tiers are analyst-controlled matching labels. Indices are derived
values; estimates, forecasts, and hypotheses must remain explicitly labelled and
are never silently promoted to observations.

## Local Development Environment

Create a repository-local Conda environment with Python 3.13 and install PEIT
with its test dependency:

```bash
conda create --yes --prefix "$PWD/.venv/PEIT" python=3.13
conda run --prefix "$PWD/.venv/PEIT" python -m pip install --editable '.[dev]'
```

Activate the environment before running PEIT commands or tests:

```bash
conda activate "$PWD/.venv/PEIT"
export PATH="$CONDA_PREFIX/bin:$PATH"
```

## Receipt Schema

PEIT standardizes all point-of-sale receipt records and cash-flow transactions
on a strict 25-column Schema (`config/receipt_schema.csv`):

| # | Column | Type | Description |
|---|--------|------|-------------|
| 1 | `receipt_id` | str | Unique receipt identifier |
| 2 | `receipt_date` | date | Transaction date in `YYYY-MM-DD` ISO format |
| 3 | `merchant` | str | Merchant or counterparty name |
| 4 | `item` | str | Normalized item key for cross-period basket matching (e.g., `milk 1 l`) |
| 5 | `brand` | str | Brand or manufacturer name (e.g., `Lala`, `Alpura`) |
| 6 | `category` | str | COICOP/budget expenditure category (e.g., `Food and beverages`) |
| 7 | `quantity` | float/int | Quantity of packs or items purchased |
| 8 | `pack_size` | float/int | Units per pack (e.g., `1`, `6`, `12`) |
| 9 | `unit` | str | Unit of measure (`L`, `kg`, `piece`, `kWh`, `m3`) |
| 10 | `unit_price` | decimal | Unit price within pack before discounts/taxes |
| 11 | `currency` | str | ISO 3-letter currency code (`MXN`, `USD`, `EUR`) |
| 12 | `discount` | decimal | Promotional discount amount (positive = money saved) |
| 13 | `fee` | decimal | Surcharge or service fee (negative = charged) |
| 14 | `tax` | decimal | Value-added or sales tax (negative = charged) |
| 15 | `deposit` | decimal | Deposit amount (negative = paid, positive = returned) |
| 16 | `paid_total` | decimal | Signed net total (negative = expense/outflow, positive = income/refund) |
| 17 | `event_type` | str | Classification: `recurring`, `one_off`, `income`, `transfer`, `refund` |
| 18 | `store_tier` | str | Store quality or tier bracket (`A`, `B`, `C`, `D`, `E`) |
| 19 | `store_rating` | float | Store satisfaction rating (`1.0` to `5.0`) |
| 20 | `brand_tier` | str | Brand quality or tier bracket (`A`, `B`, `C`, `D`, `E`) |
| 21 | `brand_rating` | float | Brand satisfaction rating (`1.0` to `5.0`) |
| 22 | `product_tier` | str | Product quality or tier bracket (`A`, `B`, `C`, `D`, `E`) |
| 23 | `product_rating` | float | Product satisfaction rating (`1.0` to `5.0`) |
| 24 | `availability` | str | Item stock status (`in_stock`, `low_stock`, `out_of_stock`, `discontinued`) |
| 25 | `notes` | str | Optional user annotations or transaction details |

## Signed Transaction Ledger Subsystem

PEIT includes a high-performance, audit-grade transaction ledger (`src/peit/ledger.py`):
- **Dual-Storage Architecture**: Combines an **authoritative append-only JSON Lines log** (`.jsonl`) for immutable audit history and git-friendly tracking with an **automatic sibling SQLite projection cache** (`.db`) for sub-millisecond queries, indexed searches, and balance rollups.
- **Self-Healing Synchronization**: On read queries, cache freshness is verified automatically against file size and modification time. If the SQLite cache is missing, stale, or corrupted, it is transparently reconstructed from the JSONL log without data loss.
- **Idempotency & Deduplication**: Every imported line-item or event receives a deterministic 4-tuple SHA-256 identity hash (`compute_entry_id(receipt_id, item, paid_total, receipt_date)`). Re-importing identical files skips existing records (`imported=0, skipped=N`), preventing duplicate accounting.
- **Signed Cash-Flow Convention**: Outflows (expenses) are signed negative (`paid_total < 0`), inflows (income, refunds) are signed positive (`paid_total > 0`), and transfers reflect net account balance impacts.

Comprehensive architecture, schema specifications, and financial rules are documented in [`doc/subsystems/ledger.md`](doc/subsystems/ledger.md).

## Command-Line Interface (CLI)

The `peit` command provides unified access to inflation tracking, ledger operations, and visual analytics. You can run the interface directly using the root executable `./peit`, via `python3 -m peit.cli`, or simply as `peit` when installed via `pip install -e .`:

### 1. Inflation Index Calculations
```bash
# Calculate fixed-basket and changing-basket inflation indices from a Schema CSV
peit --index data/example_month.csv

# Output machine-readable JSON
peit --index data/example_month.csv --json
```

### 2. Ingesting & Deduplicating Receipts (`--import`)
```bash
# Import Schema receipt items into the authoritative ledger
peit --ledger data/ledger.jsonl --import data/example_month.csv

# Import into a specific account with force overwrite
peit --ledger data/ledger.jsonl --import data/example_month.csv --account "savings:emergency" --force
```

### 3. Direct Transaction Addition (`--add`)
```bash
# Record an expense with Schema attributes
peit --ledger data/ledger.jsonl --add \
     --date 2026-03-05 --amount -45.50 --event-type one_off \
     --merchant "Corner Cafe" --item "coffee and lunch" \
     --brand "Artisan Roasters" --pack-size 1 --unit "piece" \
     --category "Food and beverages" \
     --store-tier "A" --store-rating 5.0 \
     --brand-tier "A" --brand-rating 5.0 \
     --product-tier "A" --product-rating 5.0

# Record income
peit --ledger data/ledger.jsonl --add \
     --date 2026-03-01 --amount 3000.00 --event-type income \
     --merchant "Employer Inc" --category "Income" --notes "Monthly salary"
```

### 4. Financial Inquiries & Analytics
```bash
# Financial balance summary (income, expenditure, transfers, net balance)
peit --ledger data/ledger.jsonl --balance [--month YYYY-MM] [--account <account>] [--json]

# Chronological transaction listing with conjunctive filters
peit --ledger data/ledger.jsonl --list [--month YYYY-MM] [--category <cat>] [--merchant <name>] [--event-type <type>] [--json]

# Consumption expenditure breakdown by category (excluding non-consumption flows)
peit --ledger data/ledger.jsonl --breakdown [--month YYYY-MM] [--account <account>] [--json]

# Rebuild sibling SQLite projection cache from JSONL log
peit --ledger data/ledger.jsonl --rebuild-cache
```

### 5. Desktop Synchronization Daemon & Web Workbench (`--serve`)
```bash
# Launch the local HTTP daemon and serve the Web Workbench
peit --serve --host 127.0.0.1 --port 8000

# Specify an alternate ledger path and listen on all interfaces
peit --ledger data/my_ledger.jsonl --serve --host 0.0.0.0 --port 8080
```
Provides a zero-dependency, local-first REST API and static web server (`http.server.ThreadingHTTPServer`) for the browser workbench and mobile app synchronization:
- **Web UI/UX Workbench (`web/`)**: High-density Vanilla Modern Web micro-shell featuring real-time KPI cards, interactive 25-column Data Grid, and dynamic Material 3 theming.
- **Embedded Mobile Islands (`<peit-flutter-island>`)**: Runs Flutter Web review components (`mobile/lib/screens/`) directly in the DOM via `flutter.js` Element Embedding with bidirectional event bus.
- **VS Code-Style Extension Framework (`web/extensions/`)**: Extensible runtime (`PeitExtensionHost`) loading plugins from declarative manifests (`peit-crypto-cpi`, `peit-carbon-footprint`).
- **REST Endpoints**:
  - `GET /api/v1/health`: Server status, schema column count (25), and total entry count.
  - `GET /api/v1/summary`: Real-time balance rollups and category breakdowns.
  - `GET /api/v1/entries`: Paginated transaction list with query filters (`month`, `account`, `category`, `merchant`, `limit`, `offset`).
  - `POST /api/v1/sync/push`: Idempotent batch transaction ingestion with strict 25-column schema validation, SHA-256 deduplication, and DoS payload guards (`HTTP 413` at 10 MB limit).
  - `OPTIONS *`: CORS preflight support for local browser and web views.

### 6. Interactive Multi-Graph Visualizer Dashboard (`--dashboard` / `--html`)
```bash
# Generate interactive HTML5 multi-graph dashboard from ledger
peit --ledger data/ledger.jsonl --html [-o reports/dashboard.html] [--open]
peit --ledger data/ledger.jsonl --dashboard  # alias

# Include national benchmark CPI comparison (e.g., INEGI INPC)
peit --ledger data/ledger.jsonl --html --benchmark config/benchmark_cpi_mx.csv -o reports/dashboard.html --open

# Generate standalone HTML price index report from receipt CSV
peit --index data/example_month.csv --html [-o reports/index_report.html] [--open]
```
The dashboard renders a self-contained, offline-first 3-tab layout:
- **Tab 1: Cash Flow & Spending**: Summary KPI cards, Category Breakdown donut chart, Cash Flow dual-bar timeline (monthly or daily), Top Merchants horizontal bar chart, Event Type distribution, and Cumulative Net Balance area line.
- **Tab 2: Inflation & Welfare Analytics**: Personal MoM inflation vs. National CPI divergence, Bennett additive expenditure growth decomposition ($\Delta E = \Delta E_{\text{price}} + \Delta E_{\text{quantity}}$), and Category Percentage-Point Contributions (PPC) and Absolute Dollar Impact (ADI).
- **Tab 3: Transaction Ledger**: Real-time client-side searchable and sortable data grid with full transaction provenance.

*Note*: HTML reports are strictly generated on-demand via `--html` or `--dashboard` and are never produced unrequested during ingestion. Full visualizer details are documented in [`doc/subsystems/dashboard.md`](doc/subsystems/dashboard.md).

## Profile × Market Simulation Engine (`peit.profiler`)

PEIT features a modular, stochastic receipt simulation engine (`src/peit/profiler/`) that cleanly decouples consumer behavior from pricing dynamics:

$$\text{Profile (Consumer)} \times \text{Market (Prices)} \times \text{Seed (Randomness)} \longrightarrow \text{Receipts (CSV)} + \text{Ground Truth (JSON)}$$

- **Profile JSON (`config/profiles/`)**: Defines consumer identity, spending baskets, brand preferences, store loyalty weights, co-living scheduling policies (purchase count, deterministic periodic intervals, and Weibull renewal depletion hazard), and income sources with Gaussian volatility.
- **Market JSON (`config/markets/`)**: Defines catalog base prices, latent Gaussian inflation drift, $(s, S)$ menu-cost sticky price bands, Calvo hazard price reviews, dual-mode charm pricing (grid step quantization + psychological endings like `.99`), and volume discount pack tiers (`pack_size` $\to$ `unit_price` multiplier).
- **Ground Truth Manifest (`ground_truth.json`)**: Exports a complete configuration and seed snapshot ensuring 100% deterministic simulation reproducibility.

### Generate Synthetic Datasets
```bash
# Generate Schema receipts and ground truth manifest from Profile and Market
python -m peit.profiler generate \
  --profile config/profiles/alice.json \
  --market config/markets/mexico_2024.json \
  --seed 42 \
  -o receipts.csv \
  --manifest ground_truth.json

# Generate and directly import into the signed ledger
python -m peit.profiler generate \
  --profile config/profiles/alice.json \
  --market config/markets/mexico_2024.json \
  --seed 42 \
  -o data/Alice/receipts.csv \
  --manifest data/Alice/ground_truth.json \
  --import-ledger data/Alice/ledger.jsonl
```

## Testing & Quality Assurance

PEIT includes a standardized scientific Bash test runner `test/run_tests.sh` executing **201 tests across 13 project suites** (`schema`, `core`, `ledger`, `cli`, `dashboard`, `profiler`, `server`, `mobile`, `ocr`, `ocr_canvas`, `ocr_benchmark`, `security`, `web`):

```bash
# Run all tests (201 tests across 13 suites)
bash test/run_tests.sh --all

# Run specific test suites
bash test/run_tests.sh --suite schema        # Canonical SSOT, cross-platform parity & hash invariants (22 tests)
bash test/run_tests.sh --suite profiler      # Profile generator, market dynamics & CLI (40 tests)
bash test/run_tests.sh --suite ledger        # Signed ledger, SQLite cache, balances & filters (26 tests)
bash test/run_tests.sh --suite cli           # Command-line interface parsing & commands (14 tests)
bash test/run_tests.sh --suite dashboard     # Multi-graph dashboard visualizer & KPI metrics (14 tests)
bash test/run_tests.sh --suite security      # LAN pairing handshake, auth registry & TLS pinning (14 tests)
bash test/run_tests.sh --suite web           # Web workbench micro-shell & static asset delivery (23 tests)
bash test/run_tests.sh --suite server        # Desktop synchronization daemon & REST API (11 tests)
bash test/run_tests.sh --suite core          # Core Schema validation & index algorithms (10 tests)
bash test/run_tests.sh --suite ocr           # Heuristic receipt parser & 25-column conversion (9 tests)
bash test/run_tests.sh --suite ocr_canvas    # Synthetic thermal receipt canvas & distortions (7 tests)
bash test/run_tests.sh --suite ocr_benchmark # Real receipt benchmark suite (CER, WER, F1) (6 tests)
bash test/run_tests.sh --suite mobile        # Mobile client sync payload & hash parity (5 tests)

# List all test suites, test files, and test counts
bash test/run_tests.sh --list

# Filter tests by keyword pattern
bash test/run_tests.sh -k "deterministic"
bash test/run_tests.sh -k "balance"
bash test/run_tests.sh -k "sync"
bash test/run_tests.sh -k "island"
```

## Documentation & Architecture

Comprehensive technical guides, specifications, and architecture decision records are maintained under [`doc/`](doc/):

- [`doc/README.md`](doc/README.md): **Documentation Map & Index**
- [`MAP.md`](MAP.md): current source-code and interface navigation map.
- [`demo/README.md`](demo/README.md): native Android showcase guide, current validation evidence, and separate Python/web and Flutter walkthroughs.
- **Architecture**:
  - [`doc/architecture/ssot_resilience.md`](doc/architecture/ssot_resilience.md): SSOT, drift prevention & self-healing dual persistence.
  - [`doc/architecture/mobile_hybrid.md`](doc/architecture/mobile_hybrid.md): Hybrid Card Stream & Data Grid mobile architecture.
- **Subsystems**:
  - [`doc/subsystems/ledger.md`](doc/subsystems/ledger.md): Signed transaction ledger architecture and complete technical reference.
  - [`doc/subsystems/dashboard.md`](doc/subsystems/dashboard.md): Interactive multi-graph visualizer dashboard and on-demand HTML reports.
  - [`doc/subsystems/profiler.md`](doc/subsystems/profiler.md): Architectural design for Profile × Market simulation engine.
  - [`doc/subsystems/mobile.md`](doc/subsystems/mobile.md): Mobile capture initiation modes, review workflows, and photo privacy policy.
- **Specifications & Showcase**:
  - [`config/receipt_schema.csv`](config/receipt_schema.csv): Authoritative 25-column receipt specification and data dictionary.
  - [`doc/specs/RFC-001_personal_welfare_metrics.md`](doc/specs/RFC-001_personal_welfare_metrics.md): Personal Welfare & Inflation Metric Specification (RFC).
  - [`doc/specs/RFC-003_web_ui_ux_integration.md`](doc/specs/RFC-003_web_ui_ux_integration.md): Web UI/UX Workbench, Flutter Element Embedding & Extensions (RFC).
  - [`doc/showcase/peit.tex`](doc/showcase/peit.tex): Academic conference paper / thesis LaTeX source.
