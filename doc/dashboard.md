# PEIT Multi-Graph Dashboard Visualizer & On-Demand HTML Reports

This document is the comprehensive user and developer guide for the Personal Economic
Inflation Tracker (PEIT) Multi-Graph Dashboard Visualizer and On-Demand HTML Reports subsystem (`src/peit/dashboard.py`).

The visualizer transforms raw point-of-sale receipt observations and signed financial ledger transactions into interactive, self-contained HTML5 analytics dashboards and price index reports.
**Key principle**: HTML visualizers and reports are **generated strictly on-demand via the PEIT CLI** (using the `--html` or `--dashboard` flags). They are never produced as silent or unrequested side-effects during standard imports or index calculations.

---

## 1. System Architecture & Design Principles

The PEIT dashboard visualizer adheres to the project's core principles: **on-demand generation**, **offline-first**, **privacy-preserving**, **strictly observable**, and **evidence-bounded**.

```text
┌───────────────────────────────────────────────────────────────────────┐
│                            Input Sources                              │
│ • Authoritative JSONL Ledger (<ledger>.jsonl)                         │
│ • Sibling SQLite Projection Cache (<ledger>.db)                       │
│ • Monthly Receipt CSV (<receipts>.csv)                                │
│ • National Benchmark CPI Data (e.g. config/benchmark_cpi_mx.csv)      │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                    PEIT CLI Invocation (On-Demand Only)
       peit --ledger <path> --html  |  peit --index <csv> --html
                                    │
                               src/peit/cli.py
                                    │
                             src/peit/dashboard.py
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
                  ▼                                   ▼
┌──────────────────────────────────┐ ┌─────────────────────────────────┐
│ Cash Flow & Ledger Visualizer    │ │ Price Index Report Generator    │
│ • compute_summary_kpis()         │ │ • generate_index_html()         │
│ • aggregate_category_breakdown() │ │ • create_index_report()         │
│ • aggregate_timeline()           │ │ • Matched basket (M_t)          │
│ • aggregate_top_merchants()      │ │ • Fixed vs changing indices     │
│ • Bennett decomposition          │ │ • Coverage & MoM trajectory     │
│ • generate_dashboard_html()      │ └────────────────┬────────────────┘
└─────────────────┬────────────────┘                  │
                  │                                   │
                  ▼                                   ▼
        <output>_dashboard.html              <output>_index.html
```

### 1.1 Core Design Characteristics

1. **Self-Contained Single-File Output**:
   The visualizer outputs a standalone `.html` file that bundles all styling, layout logic, embedded JSON datasets, and interactive JavaScript. It requires no active backend server, making reports easily archiveable, shareable, and viewable in any standard browser.

2. **Zero External Data Leakage**:
   All financial aggregations and personal transaction logs remain strictly local. No ledger data or telemetry is transmitted over the network. Visual assets rely solely on standard modern web APIs and a secure, lightweight Chart.js runtime.

3. **Strict Matched-Only Discipline for Inflation**:
   In strict conformance with `PLAN_METRICS.md` and `AGENTS.md`, price index calculations never invent synthetic observations. Only items purchased in consecutive months ($M_t = I_{t-1} \cap I_t$) are included in price relative evaluations, accompanied by explicit basket coverage reporting.

4. **Robust XSS Prevention**:
  Every string originating from transaction records (merchant names, item keys, account IDs, and category labels) undergoes strict HTML escaping via `html.escape()` before document injection. Chart data structures are safely serialized as clean JSON payloads.

---

## 2. The 3-Tab Interface Layout

The dashboard organizes complex financial data into three specialized tabs:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ [Tab 1: Cash Flow & Spending] [Tab 2: Inflation & Welfare] [Tab 3: Ledger]  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tab 1: Cash Flow & Spending

Focused on household liquidity, spending allocation, and operational cash flow.

- **KPI Metric Cards**:
  - **Total Income**: Cumulative inflow from salaries, investments, and capital returns (`event_type == 'income'`).
  - **Total Expenditure**: Total consumption outflows (`event_type` in `{'recurring', 'one_off'}`).
  - **Net Balance**: Overall algebraic net balance across all recorded accounts:
    $$\text{Net Balance} = \text{Income} - \text{Expenditure} + \text{Transfers} + \text{Refunds}$$
  - **Transaction Count**: Total count of validated ledger entries within the active filter scope.
- **Charts Displayed**:
  - Chart 1: Category Breakdown (Donut Chart)
  - Chart 2: Cash Flow Timeline (Dual Bar Chart)
  - Chart 3: Top Merchants by Spend (Horizontal Bar Chart)
  - Chart 4: Event Type Distribution (Doughnut / Polar Chart)
  - Chart 5: Cumulative Net Balance (Area Line Chart)

### Tab 2: Inflation & Welfare Analytics

Bridges personal expenditure with price index theory and macroeconomic benchmarks.

- **KPI Metric Cards**:
  - **Personal MoM Inflation ($\pi^{\text{personal}}_t$)**: Month-over-month price change on exact matched items.
  - **National Benchmark CPI ($\pi^{\text{national}}_t$)**: Official monthly CPI rate from reference data (e.g. INEGI INPC, US BLS CPI).
  - **Inflation Gap / Penalty ($\Delta \pi_t$)**: Difference between personal and national rates:
    $$\Delta \pi_t = \pi^{\text{personal}}_t - \pi^{\text{national}}_t$$
- **Charts Displayed**:
  - Chart 6: Personal vs. National CPI Divergence (Line Chart)
  - Chart 7: Bennett Expenditure Growth Decomposition (Waterfall / Floating Bar Chart)
  - Chart 8: Category Inflation Contributions (Diverging Bar Chart: PPC & ADI)

### Tab 3: Transaction Ledger

An interactive, searchable, and sortable data grid providing full provenance for every transaction.

- **Live Real-Time Search (`#table-search`)**:
  Client-side filtering instantly narrows displayed transactions as the user types, matching against date, receipt ID, account, merchant, category, item, event type, or amount.
- **Data Table Columns**:
  - `Date`: ISO `YYYY-MM-DD` transaction date (`receipt_date`).
  - `Receipt ID`: Source receipt code or unique transaction identifier (`receipt_id`).
  - `Merchant`: Standardized counterparty name (`merchant`).
  - `Category`: COICOP expenditure classification (`category`).
  - `Item`: Normalized key (`item`).
  - `Type`: Color-coded status badge (`event_type`: `income`, `recurring`, `one_off`, `refund`, `transfer`).
  - `Amount`: Signed net total amount (`paid_total`) formatted with sign and currency.
  - `Account`: Financial account badge (`account`, e.g. `default:checking`, `savings:reserve`).

---

## 3. The 8 Visualizations & Financial Interpretation

The visualizer renders eight distinct charts, each answering a specific economic or financial question:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Tab 1: Cash Flow & Spending                                                 │
│   ├── [Chart 1] Category Breakdown (Donut)                                  │
│   ├── [Chart 2] Monthly/Daily Cash Flow Timeline (Dual Bar)                 │
│   ├── [Chart 3] Top Merchants by Spend (Horizontal Bar)                     │
│   ├── [Chart 4] Event Type Distribution (Doughnut)                          │
│   └── [Chart 5] Cumulative Net Balance Trajectory (Filled Area Line)        │
│                                                                             │
│ Tab 2: Inflation & Welfare Analytics                                        │
│   ├── [Chart 6] Personal vs. National CPI Divergence (Dual Line)            │
│   ├── [Chart 7] Bennett Expenditure Growth Decomposition (Waterfall Bar)    │
│   └── [Chart 8] Category Inflation Contributions (Diverging Bar - PPC/ADI)  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Chart 1: Category Breakdown (Donut Chart)
- **Aggregation**: Groups consumption expenditures (`recurring` and `one_off`) by category, computing the percentage share of total consumption.
- **Financial Interpretation**:
  Exposes the household's budget structure. Identifies whether spending is dominated by essential living costs (e.g. "Food and non-alcoholic beverages", "Housing and utilities") or discretionary categories ("Recreation and culture", "Restaurants and hotels"). Highlights budget concentration risks.

### Chart 2: Monthly / Daily Cash Flow Timeline (Dual Bar Chart)
- **Aggregation**:
  - *Full Ledger Scope*: Aggregates inflows (`income`, `refund`) and outflows (`recurring`, `one_off`) by month (`YYYY-MM`).
  - *Filtered Month Scope (`--month YYYY-MM`)*: Automatically pivots to a daily resolution (`YYYY-MM-DD`).
- **Financial Interpretation**:
  Visualizes liquidity dynamics over time. Green bars denote cash inflows; coral bars denote outflows.
  The spread reveals periods of savings expansion versus cash deficits where savings buffers were depleted.

### Chart 3: Top Merchants by Spend (Horizontal Bar Chart)
- **Aggregation**: Sums total expenditure per merchant, ranking the top 10 counterparties and grouping all remaining vendors into an `"Other"` category.
- **Financial Interpretation**:
  Quantifies vendor concentration. Reveals high-expenditure retail channels, recurring subscription services, and utility providers that consume the largest share of net income.

### Chart 4: Event Type Distribution (Doughnut / Polar Chart)
- **Aggregation**: Calculates the transaction count and financial volume across the five event types:
  `income`, `recurring`, `one_off`, `refund`, and `transfer`.
- **Financial Interpretation**:
  Distinguishes fixed contractual commitments (`recurring`) from variable discretionary outlays (`one_off`).
  A high ratio of recurring obligations indicates fixed overhead inflexibility during economic downturns.

### Chart 5: Cumulative Net Balance Trajectory (Filled Area Line Chart)
- **Aggregation**: Computes the chronological running prefix sum of all signed transactions:
  $$B_k = \sum_{j=1}^k \text{paid\_total}_j$$
- **Financial Interpretation**:
  Demonstrates long-term wealth accumulation and liquid runway. Upward trajectories reflect net positive savings; flat segments reflect breakeven cash flow; downward slopes warn of capital drawdowns.

### Chart 6: Personal vs. National CPI Divergence (Dual Line Chart)
- **Aggregation**:
  Normalizes personal price changes over matched items into an index starting at 100.0 at the base month.
  Plots this alongside official national CPI benchmark series (e.g. Mexico INEGI INPC or US BLS CPI).
- **Financial Interpretation**:
  Solves the "headline inflation vs. personal reality" paradox.
  - *Personal Curve above Benchmark*: The user experiences a **personal inflation penalty** ($\Delta \pi_t > 0$), often caused by higher local grocery or fuel costs than the national average basket.
  - *Personal Curve below Benchmark*: The user benefits from **personal deflationary insulation** ($\Delta \pi_t < 0$).

### Chart 7: Bennett Expenditure Growth Decomposition (Waterfall / Floating Bar Chart)
- **Mathematical Model**:
  Implements the exact additive **Bennett / Montgomery-Vartia** decomposition over consecutive months:
  $$\Delta E = E^M_t - E^M_{t-1} = \Delta E_{\text{price}} + \Delta E_{\text{quantity}}$$
  Where:
  $$\Delta E_{\text{price}} = \sum_{i \in M_t} \left(\frac{q_{i, t-1} + q_{i, t}}{2}\right) (p_{i, t} - p_{i, t-1})$$
  $$\Delta E_{\text{quantity}} = \sum_{i \in M_t} \left(\frac{p_{i, t-1} + p_{i, t}}{2}\right) (q_{i, t} - q_{i, t-1})$$
  Here $p_{i, t}$ denotes Schema unit price (`unit_price`) and $q_{i, t}$ denotes purchased quantity (`quantity`).
- **Mathematical Invariant**:
  $$\Delta E_{\text{price}} + \Delta E_{\text{quantity}} \equiv \Delta E \quad (\text{Exact Zero Residual})$$
- **Financial Interpretation**:
  Decouples price changes from volume changes. Answers the critical budgeting question:
  *"Did my bill increase because goods became more expensive ($\Delta E_{\text{price}}$), or did I consume more units ($\Delta E_{\text{quantity}}$)?"*

### Chart 8: Category Inflation Contributions (Diverging Bar Chart: PPC & ADI)
- **Mathematical Model**:
  Reports dual inflation metrics for each matched expenditure category $c$:
  1. **Percentage-Point Contribution ($\text{PPC}_c$)**:
     $$\text{PPC}_c = w_{c, t-1} \times \pi_{c, t} \times 100$$
     Property: $\sum_c \text{PPC}_c = \pi^{\text{personal}}_t \times 100$.
  2. **Absolute Dollar Impact ($\text{ADI}_c$)**:
     $$\text{ADI}_c = \sum_{i \in M_{c, t}} q_{i, t-1} (p_{i, t} - p_{i, t-1})$$
     Where $p_{i, t}$ is `unit_price` and $q_{i, t-1}$ is base-period `quantity`.
- **Financial Interpretation**:
  Pinpoints which specific categories are the true drivers of inflation. Bars extending to the right indicate inflationary drivers adding cost to the monthly budget; bars extending to the left indicate categories providing deflationary relief.

---

## 4. Command-Line Interface (CLI) Specification

HTML generation is a first-class, on-demand capability across both primary PEIT modes:

```bash
# 1. Ledger Multi-Graph Dashboard (HTML on demand)
peit --ledger <path> --html [OPTIONS]
peit --ledger <path> --dashboard [OPTIONS]   # backward-compatible alias

# 2. Price Index Calculation Report (HTML on demand)
peit --index <csv_path> --html [OPTIONS]
peit --index <csv_path> --dashboard [OPTIONS]
```

### 4.1 CLI Options Reference

| Flag | Mode | Default | Description |
|---|---|---|---|
| `--html` | Both | `False` | Triggers on-demand generation of interactive HTML5 output: multi-graph visualizer dashboard under `--ledger`, or price index report under `--index`. |
| `--dashboard` | Both | `False` | Standard alias for `--html`. |
| `-o`, `--output` | Both | `<stem>_dashboard.html` or `<stem>_index.html` | Custom destination file path for the generated HTML report or dashboard. |
| `--open` | Both | `False` | Automatically launches the generated HTML dashboard or report in your default operating system browser. |
| `--benchmark` | `--ledger` | `None` | Path to national CPI benchmark CSV file (e.g. `config/benchmark_cpi_mx.csv`). |
| `--month` | `--ledger` | `None` | Limits analysis to a single month (`YYYY-MM`). Switches cash flow chart to daily resolution. |
| `--category` | `--ledger` | `None` | Restricts dashboard metrics and ledger to a specific expenditure category. |
| `--merchant` | `--ledger` | `None` | Filters transactions and charts to a specific merchant. |
| `--event-type` | `--ledger` | `None` | Filters by event type: `income`, `recurring`, `one_off`, `refund`, or `transfer`. |
| `--account` | `--ledger` | `None` | Restricts analysis to a specific financial account (e.g. `default:checking`). |
| `--json` | Both | `False` | Emits machine-readable JSON to stdout instead of tables or HTML (mutually exclusive with `--html`). |

---

## 5. Concrete CLI Command Examples

### 5.1 On-Demand Ledger Dashboard (`--ledger ... --html`)
Generate a comprehensive multi-graph dashboard from an authoritative ledger:

```bash
# Standard HTML dashboard generation
peit --ledger data/ledger.jsonl --html

# With custom output path and automatic browser opening
peit --ledger data/ledger.jsonl --html -o reports/my_dashboard.html --open
```
*Output*: Generates self-contained HTML containing all 3 tabs, 8 charts, and all transaction entries.

### 5.2 On-Demand Price Index HTML Report (`--index ... --html`)
Compute personal price and expenditure indices from a receipt CSV and render a visual HTML report:

```bash
# Standard price index HTML report
peit --index data/example_month.csv --html

# Custom destination with browser launch
peit --index data/example_month.csv --html -o reports/inflation_report.html --open
```
*Output*: Produces `reports/inflation_report.html` featuring interactive Chart.js trajectory lines (Fixed Basket vs Changing Expenditure), summary KPI metric cards, and a full month-by-month tabular breakdown.

### 5.3 Dashboard with National CPI Benchmark Comparison
Compare realized personal inflation against official Mexico INEGI INPC benchmark statistics:

```bash
peit --ledger data/ledger.jsonl \
  --html \
  --benchmark config/benchmark_cpi_mx.csv \
  -o reports/personal_inflation_report.html \
  --open
```
*Output*: Produces `reports/personal_inflation_report.html` with populated personal vs. national CPI gap analysis,
Bennett waterfall decomposition, and category PPC contributions.

### 5.4 Single-Month Deep Dive with Daily Timeline
Examine spending patterns for a specific month (e.g. February 2026) with daily cash flow bars:

```bash
peit --ledger data/ledger.jsonl \
  --html \
  --month 2026-02 \
  --open
```

### 5.5 Account-Specific Liquidity Analysis
Analyze cash flow and transactions strictly for a primary checking account:

```bash
peit --ledger data/ledger.jsonl \
  --html \
  --account default:checking \
  -o reports/checking_summary.html
```

### 5.6 Category Spend Audit
Audit all grocery and dining expenses:

```bash
peit --ledger data/ledger.jsonl \
  --html \
  --category "Food and non-alcoholic beverages" \
  -o reports/food_spending.html
```

---

## 6. Developer & Python API Reference

Developers can import and invoke the visualizers and report generators programmatically from Python:

```python
from pathlib import Path
from peit.dashboard import (
    create_dashboard,
    create_index_report,
    generate_dashboard_html,
    generate_index_html,
)
from peit.core import calculate_indices, read_csv
from peit.ledger import LedgerDatabase

# 1. High-level ledger dashboard generation
html_file: Path = create_dashboard(
    ledger_path="data/ledger.jsonl",
    output_path="reports/my_dashboard.html",
    benchmark_path="config/benchmark_cpi_mx.csv",
    month="2026-02",
    open_browser=False,
)
print(f"Dashboard successfully generated at {html_file}")

# 2. High-level price index HTML report generation
rows, _ = read_csv("data/example_month.csv")
report = calculate_indices(rows)
index_html_file: Path = create_index_report(
    report=report,
    csv_path="data/example_month.csv",
    output_path="reports/index_report.html",
    open_browser=False,
)
print(f"Index report successfully generated at {index_html_file}")
```

### 6.1 Core Aggregation Functions (`src/peit/dashboard.py`)

- `compute_summary_kpis(entries: list[LedgerEntry]) -> dict[str, Any]`
  Computes total income, consumption expenditure, net transfers, net refunds, net balance, and transaction count.
- `aggregate_category_breakdown(entries: list[LedgerEntry], db_breakdown: list[dict] | None = None) -> list[dict[str, Any]]`
  Calculates category totals, budget percentages, and assigns distinct theme colors.
- `aggregate_timeline(entries: list[LedgerEntry], month_filter: str | None = None) -> dict[str, Any]`
  Constructs dual time series (inflows and outflows) aggregated at monthly or daily resolution.
- `aggregate_top_merchants(entries: list[LedgerEntry], top_n: int = 10) -> list[dict[str, Any]]`
  Computes merchant spend rankings and consolidates the remainder into an `"Other"` tier.
- `aggregate_event_types(entries: list[LedgerEntry]) -> list[dict[str, Any]]`
  Tallies volume and frequency across transaction event classifications.
- `aggregate_cumulative_balance(entries: list[LedgerEntry]) -> dict[str, Any]`
  Generates chronological prefix running balance series.
- `compute_inflation_and_welfare(entries: list[LedgerEntry], benchmark_path: Path | str | None = None) -> dict[str, Any]`
  Extracts matched item baskets between consecutive months, runs Bennett additive decomposition, calculates category PPC/ADI contributions, and evaluates benchmark gaps.

---

## 7. Testing & Verification Guide

The PEIT test suite includes dedicated automation for the dashboard visualizer in `test/test_dashboard.py`, managed seamlessly through `test/run_tests.sh`.

### 7.1 Running the Tests via `test/run_tests.sh`

The test runner script automatically handles `PYTHONPATH`, detects the active Python/pytest environment, and provides clear ANSI status reporting.

```bash
# 1. Run only the dashboard test suite
bash test/run_tests.sh --suite dashboard

# 2. Run dashboard tests with verbose output
bash test/run_tests.sh -s dashboard -v

# 3. Run all test suites (10 suites, 142 tests)
bash test/run_tests.sh --all

# 4. Filter tests by keyword expression (e.g. Bennett decomposition)
bash test/run_tests.sh -k "bennett"

# 5. List all registered suites and test case counts
bash test/run_tests.sh --list

# 6. Run with code coverage reporting
bash test/run_tests.sh -s dashboard --coverage
```

### 7.2 Verification Checklist & Suite Inventory

The dashboard test suite verifies:
- **KPI Consistency**: Validates that summary cards match algebraic sums of `paid_total`.
- **Bennett Invariant**: Confirms $\Delta E_{\text{price}} + \Delta E_{\text{quantity}} \equiv \Delta E$ within floating-point tolerance ($< 10^{-6}$).
- **Category Additive Sum**: Confirms $\sum \text{PPC}_c \equiv \pi^{\text{personal}}_t \times 100$.
- **Benchmark Alignment**: Verifies proper ingestion of benchmark CSV files and correct inflation gap reporting.
- **HTML Integrity & XSS Prevention**: Validates document structure, Chart.js script elements, and verifies that hostile input strings (e.g. `<script>alert(1)</script>`) are escaped into `&lt;script&gt;`.
- **CLI Integration**: Validates `--dashboard`, `--benchmark`, `--month`, `-o`, and `--open` execution codes and output file generation.
