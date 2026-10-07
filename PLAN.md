# Plan: PEIT Multi-Graph Dashboard Visualizer (`peit.dashboard`) with Integrated Welfare Metrics & Indices

This document provides the detailed technical specification and implementation plan for building the interactive multiple-graph dashboard visualizer in PEIT under `src/peit/dashboard.py`, integrating both **cash flow spending patterns** and **personal welfare metrics & price indices** into a unified, tabbed analytical dashboard.

---

## 1. Overview & Objectives

Build a dedicated, standalone visualization engine in Python (`peit.dashboard`) that:
- Ingests transactions and financial projections from `src/peit/ledger.py` (`LedgerDatabase`, `list_entries`, `get_category_breakdown`, `get_balance`).
- Integrates personal welfare metrics and price index calculations (`peit.metrics`):
  - **Personal vs. National CPI Comparison**: Compares personal matched inflation against national benchmark statistics.
  - **Expenditure Growth Decomposition Waterfall**: Isolates pure price inflation effects from quantity/lifestyle changes using exact additive decomposition.
  - **Category Inflation Contribution (Dual Metric)**: Quantifies percentage-point contributions ($\mathrm{PPC}$) and absolute dollar impacts ($\mathrm{ADI}$) across spending categories.
  - **Strict Matched-Only Basket Integrity**: Formulates all price metrics on common items without synthetic imputation, reporting coverage metrics transparently.
- Applies the identical filter arguments available in `peit.ledger`:
  - `--month YYYY-MM`
  - `--category <category>`
  - `--merchant <merchant>`
  - `--event-type <event_type>`
  - `--account <account>`
- Accepts an optional `--benchmark <path>` flag to compare personal inflation against official benchmark CPI series (e.g. `config/benchmark_cpi_mx.csv` for Mexico INEGI or `config/benchmark_cpi_us.csv` for US BLS).
- Emits a standalone, responsive HTML5 dashboard organized into a clean **Sectioned / Tabbed View**:
  - **Tab 1: Cash Flow & Spending** (5 interactive spending charts + 4 financial KPI cards)
  - **Tab 2: Inflation & Welfare Analytics** (3 interactive index/decomposition charts + 3 inflation KPI cards)
  - **Tab 3: Transaction Ledger** (Searchable and filterable line-item transaction table)
- Provides graceful degradation when transaction history is under 2 months or when no benchmark file is supplied.
- Offers dual execution interfaces:
  - `peit --ledger <path> --dashboard [--output <path>] [--open] [--benchmark <path>] [filters]`
  - Standalone `python -m peit.dashboard --ledger <path> [--benchmark <path>] [filters]`

---

## 2. Architecture & Module Organization

```text
PEIT/
├── config/
│   ├── benchmark_cpi_mx.csv   # Reference INEGI INPC monthly benchmark
│   └── benchmark_cpi_us.csv   # Reference US BLS CPI monthly benchmark
├── src/
│   └── peit/
│       ├── __init__.py        # Re-export dashboard and metrics generator functions
│       ├── core.py            # Core schema validation & base price index calculations
│       ├── ledger.py          # Signed ledger, SQLite projection, balances, and filters
│       ├── metrics.py         # [NEW] Personal welfare metrics, CPI gap, and decompositions
│       ├── dashboard.py       # [NEW] Multi-tab dashboard generator, Chart.js templates & CLI
│       └── cli.py             # [MODIFY] Wire --dashboard, --benchmark, --output, --open flags
├── test/
│   ├── test_core.py           # Core schema & index tests
│   ├── test_ledger.py         # Signed ledger & SQLite cache tests
│   ├── test_cli.py            # CLI integration tests
│   ├── test_dashboard.py      # [NEW] Dashboard aggregation, tab navigation & visualizer tests
│   └── run_tests.sh           # [MODIFY] Add 'dashboard' suite to test runner
└── PLAN.md                    # This master plan
```

---

## 3. Visual Dashboard Architecture: Sectioned & Tabbed UI

The dashboard UI renders as a single, self-contained HTML5 file with an embedded tab bar allowing effortless switching between analytical views:

```
+-----------------------------------------------------------------------------+
| PEIT Personal Economic Inflation Tracker - Financial & Welfare Dashboard    |
| Ledger: data/ledger.jsonl | Generated: 2026-09-05 | Records: 142             |
| Active Badges: [Month: 2026-03] [Account: default:checking]                 |
+-----------------------------------------------------------------------------+
|  [ Tab 1: Cash Flow & Spending ]  [ Tab 2: Inflation & Welfare ]  [ Tab 3: Ledger ] |
+-----------------------------------------------------------------------------+
```

### 3.1 Tab 1: Cash Flow & Spending Analytics

#### KPI Header Cards (Row 1):
- **Total Inflow / Income**: Green card with signed positive total (e.g., `+$5,200.00`).
- **Total Outflow / Expenditure**: Red card with signed consumption total (e.g., `-$2,430.50`).
- **Net Balance / Savings**: Blue/Emerald indicator of net periodic accumulation.
- **Transaction Volume**: Total matching entries count.

#### Multi-Graph Grid (Row 2 & 3):
1. **Category Breakdown (`--breakdown`)**:
   - Interactive Donut chart displaying spending share and percentage per category.
   - Reconciled 100.0% rounding with hover tooltips.
2. **Cash Flow Timeline**:
   - Chronological dual bar chart comparing income (green) vs. expenditure (coral) across months (or days if single-month filter is active).
3. **Top Merchants by Spend**:
   - Horizontal ranking bar chart identifying top 10 expenditure counterparties.
4. **Event Type Distribution**:
   - Doughnut/bar chart breaking down volume and spend across `recurring`, `one_off`, `income`, `refund`, and `transfer`.
5. **Cumulative Balance Trajectory**:
   - Area-fill line chart showing running account balance over time.

---

### 3.2 Tab 2: Inflation & Welfare Analytics

#### Inflation & Basket Integrity KPI Cards (Row 1):
- **Personal Inflation Rate (MoM)**: Realized matched-basket price movement (e.g., `+2.45%`).
- **National Benchmark Gap**: Difference between personal inflation and national CPI (e.g., `+2.10 pp (Above Average)`).
- **Basket Coverage %**: Item and expenditure coverage metrics (e.g., `75.0% items / 87.5% spend`).

#### Multi-Graph Grid (Row 2 & 3):
1. **Personal vs. National CPI Comparison Chart**:
   - Dual-line time-series chart comparing the user's monthly personal inflation rate against official national benchmark CPI.
   - Shaded divergence area highlighting months where personal inflation exceeded or lagged official statistics.
   - Tooltips show exact percentage-point gap and benchmark series identifier.
2. **Expenditure Growth Decomposition Waterfall Chart**:
   - Waterfall bar chart decomposing monthly spending changes into:
     - Starting Matched Spend ($E^M_{t-1}$)
     - **Price Effect** ($\Delta E_{\mathrm{price}}$): How much spending increased purely due to higher prices (inflation).
     - **Quantity Effect** ($\Delta E_{\mathrm{quantity}}$): How much spending changed due to volume/consumption adjustments.
     - Ending Matched Spend ($E^M_t$).
   - Built on the **Exact Additive (Bennett) Decomposition** guaranteeing zero residual.
3. **Category Inflation Contribution Chart**:
   - Diverging horizontal bar chart displaying each category's impact on personal inflation.
   - Dual tooltips reporting both **Percentage-Point Contribution ($\mathrm{PPC}$)** and **Absolute Dollar Impact ($\mathrm{ADI}$)**.

#### Graceful Degradation Rules for Tab 2:
- **Insufficient History (< 2 months)**: If the ledger contains only 1 month of data, Tab 2 renders an informative empty-state card:
  > *"Inflation dynamics and expenditure decomposition require at least two consecutive months of transaction data. Add transactions from another month to unlock this tab."*
- **Missing Benchmark**: If `--benchmark` is not passed, the personal inflation line is displayed alone, alongside an informative banner:
  > *"No national benchmark provided. Supply `--benchmark config/benchmark_cpi_mx.csv` to compare personal inflation against official statistics."*

---

### 3.3 Tab 3: Filterable Transaction Ledger

- Real-time client-side search input filter (`#table-search`).
- Full line-item table rendering:
  - Date, Receipt ID, Merchant, Category, Event Type, Quantity, Unit, Unit Price, Signed Total.
  - Event-type color badges and positive/negative financial amount formatting.

---

## 4. Mathematical Specifications for Visualizer Metrics

### 4.1 Strict Matched Basket Extraction
All inflation and decomposition calculations operate strictly on the common intersection of normalized items:
\[
  M_t = I_{t-1} \cap I_t
\]
Unmatched items are excluded from price index calculations, and basket coverage is reported:
\[
  C^{\mathrm{item}}_t = 100 \times \frac{|M_t|}{|I_{t-1}|}, \qquad C^{\mathrm{exp}}_t = 100 \times \frac{\sum_{i \in M_t} p_{i,t} q_{i,t}}{\sum_{k \in I_t} e_k}
\]

### 4.2 Exact Additive Expenditure Decomposition (Bennett)
For the waterfall chart:
\[
  \Delta E^M = E^M_t - E^M_{t-1} = \Delta E_{\mathrm{price}} + \Delta E_{\mathrm{quantity}}
\]
\[
  \Delta E_{\mathrm{price}} = \sum_{i \in M_t} \left(\frac{q_{i, t-1} + q_{i, t}}{2}\right) (p_{i, t} - p_{i, t-1})
\]
\[
  \Delta E_{\mathrm{quantity}} = \sum_{i \in M_t} \left(\frac{p_{i, t-1} + p_{i, t}}{2}\right) (q_{i, t} - q_{i, t-1})
\]
Guarantees **zero residual**: $\Delta E_{\mathrm{price}} + \Delta E_{\mathrm{quantity}} \equiv \Delta E^M$.

### 4.3 Category Inflation Contribution (Dual Metric)
For the category contribution diverging bar chart:
1. **Percentage-Point Contribution ($\mathrm{PPC}_c$)**:
   \[
     \mathrm{PPC}_c = w_{c, t-1} \times \pi_{c, t} \times 100
   \]
   Where $w_{c, t-1}$ is category $c$'s base budget share and $\sum_c \mathrm{PPC}_c = \pi_t \times 100$.
2. **Absolute Dollar Impact ($\mathrm{ADI}_c$)**:
   \[
     \mathrm{ADI}_c = \sum_{i \in M_{c, t}} q_{i, t-1} (p_{i, t} - p_{i, t-1})
   \]

---

## 5. CLI Interface Design

```bash
# 1. Full dashboard generation with default settings
peit --ledger data/ledger.jsonl --dashboard

# 2. Dashboard with national benchmark comparison
peit --ledger data/ledger.jsonl --dashboard --benchmark config/benchmark_cpi_mx.csv

# 3. Filtered dashboard automatically launched in default web browser
peit --ledger data/ledger.jsonl --dashboard \
     --benchmark config/benchmark_cpi_mx.csv \
     --month 2026-03 \
     --account default:checking \
     --open

# 4. Custom output path
peit --ledger data/ledger.jsonl --dashboard -o reports/march_overview.html

# 5. Standalone module invocation
python -m peit.dashboard --ledger data/ledger.jsonl --benchmark config/benchmark_cpi_mx.csv --open
```

---

## 6. Implementation Tasks (Phased Roadmap)

### Phase 1: Core Dashboard & Spending Visualizer (T1 - T3)
- [ ] **T1.1**: Implement spending aggregation pipelines in `src/peit/dashboard.py` (Category breakdown, Timeline, Top merchants, Event types, Cumulative balance, Financial KPIs).
- [ ] **T1.2**: Implement multi-tab HTML5/CSS grid templates with embedded Chart.js and client-side tab switching.
- [ ] **T1.3**: Wire `--dashboard`, `--output` (`-o`), and `--open` into `src/peit/cli.py` and implement `python -m peit.dashboard`.

### Phase 2: Welfare Metrics & Indices Integration (T2.1 - T2.4)
- [ ] **T2.1**: Implement benchmark CSV reader in `src/peit/metrics.py` supporting `config/benchmark_cpi_mx.csv` and custom `--benchmark` paths.
- [ ] **T2.2**: Implement strict matched-basket extractor with coverage tracking ($C^{\mathrm{item}}$, $C^{\mathrm{exp}}$).
- [ ] **T2.3**: Implement Bennett exact additive decomposition ($\Delta E_{\mathrm{price}}$, $\Delta E_{\mathrm{quantity}}$) and category dual metrics ($\mathrm{PPC}$, $\mathrm{ADI}$).
- [ ] **T2.4**: Wire Tab 2 charts (CPI Comparison, Waterfall Decomposition, Category Contribution) and graceful degradation handlers into `dashboard.py`.

### Phase 3: Automated Test Suites & Runner Integration (T3.1 - T3.2)
- [ ] **T3.1**: Implement Suites 1 through 11 in `test/test_dashboard.py` and `test/test_cli.py`.
- [ ] **T3.2**: Update `test/run_tests.sh` to add `dashboard` suite and include in `all`.

---

## 7. Detailed Design Tests & Verification Matrix

The test suite is structured into 11 comprehensive suites covering all visualizer components, metrics mathematics, tab navigation, and CLI operations:

### Suite 1: KPI Metrics & Aggregation Engine (`test/test_dashboard.py`)
- **T1.1: Mixed Cash Flow KPIs**: Verifies income (+5000), expenses (-2000), transfers (-200), refunds (+100) yield exact net balance (2900.00) and count (5).
- **T1.2: Empty Ledger Zero-State**: Returns 0.00 for all financial KPIs without exceptions.
- **T1.3: Income-Only Ledger**: Verifies net balance matches total income with zero expenses.
- **T1.4: Outflow-Only Ledger**: Verifies net balance matches negative expenses with zero income.
- **T1.5: Floating-Point Rounding**: All currency KPIs are rounded to exactly 2 decimal places.

### Suite 2: Category Breakdown Analytics (`test/test_dashboard.py`)
- **T2.1: Spending Share Precision**: 3 categories sum to exactly 100.0% with reconciled rounding.
- **T2.2: Non-Consumption Exclusion**: Excludes income and transfer categories from expenditure breakdown.
- **T2.3: Zero Expenditure Month**: Graceful empty list return without ZeroDivisionError.
- **T2.4: Palette-Coded Color Assignment**: Distinct, aesthetic palette colors assigned per category.
- **T2.5: Precomputed Database Breakdown Compatibility**: Integrates cleanly with `LedgerDatabase.get_category_breakdown()`.

### Suite 3: Cash Flow Timeline Aggregations (`test/test_dashboard.py`)
- **T3.1: Multi-Month Cash Flow Grouping**: Monthly grouping (`YYYY-MM`) with separate income and expense series.
- **T3.2: Single-Month Filter Daily Resolution**: Automatic switch to daily resolution (`YYYY-MM-DD`) when `--month` is filtered.
- **T3.3: Chronological Sort Stability**: Ensures timeline is strictly chronological regardless of insertion order.
- **T3.4: Mixed Same-Day Inflow/Outflow**: Correctly separates same-day income and expenses into respective series.

### Suite 4: Top Merchants & Event Type Distributions (`test/test_dashboard.py`)
- **T4.1: Top 10 Merchants Sorting & Capping**: Ranks top 10 spend vendors; aggregates 11+ into "Other".
- **T4.2: Merchant Outflow Invariant**: Refunds are not counted as merchant spend.
- **T4.3: Less Than 10 Merchants**: Renders cleanly without placeholder padding.
- **T4.4: Event Type Full Spectrum Aggregation**: Correct counts and totals across all 5 event types.
- **T4.5: Event Type Zero-Count Safety**: Handles absent event types safely.

### Suite 5: Cumulative Balance Trajectory (`test/test_dashboard.py`)
- **T5.1: Chronological Prefix Sum Trajectory**: Running balance curve matches chronological transaction amounts.
- **T5.2: Unsorted Input Stability**: Auto-sorts by `(receipt_date, receipt_id)` before calculating prefix sums.
- **T5.3: Single Entry Trajectory**: Boundary test with 1 entry.
- **T5.4: Empty Trajectory**: Graceful empty series return.

### Suite 6: HTML Generation, Integrity & Security (`test/test_dashboard.py`)
- **T6.1: Valid HTML5 Structure**: Contains doctype, head, meta charset, responsive viewport, closing tags.
- **T6.2: All Chart Canvases Present**: Verifies DOM elements for all 8 charts.
- **T6.3: Chart.js Script Injection**: Valid Chart.js configuration payloads embedded in `<script>` tags.
- **T6.4: Active Filter Badges**: Badges reflect applied CLI filters.
- **T6.5: Unfiltered Default State**: Shows "All Records (Unfiltered)" when no filters are set.
- **T6.6: XSS Prevention & HTML Escaping**: Merchant names and notes with `<script>` are properly escaped.
- **T6.7: Interactive Transaction Table**: Table with search input filter and formatted line items.
- **T6.8: Responsive CSS Grid**: Flexbox and grid styles adapt across viewports.

### Suite 7: File Output & Browser Launching (`test/test_dashboard.py`)
- **T7.1: Default Output Path Derivation**: Generates `<ledger_stem>_dashboard.html`.
- **T7.2: Custom Output Path Creation**: Creates nested parent directories automatically.
- **T7.3: Overwriting Existing File**: Safely replaces existing dashboard files.
- **T7.4: Browser Auto-Open Mock**: Invokes `webbrowser.open` when `--open` is provided.
- **T7.5: Browser Auto-Open Disabled**: Default execution does not invoke `webbrowser.open`.

### Suite 8: CLI Integration & Filter Combinations (`test/test_cli.py`)
- **T8.1: Full Dashboard Generation CLI**: `peit --ledger ... --dashboard` creates file and exits 0.
- **T8.2: Month Filter CLI**: `--dashboard --month 2026-02` applies single-month slice.
- **T8.3: Category Filter CLI**: `--dashboard --category Food` isolates category transactions.
- **T8.4: Merchant Filter CLI**: `--dashboard --merchant SuperStore` isolates merchant.
- **T8.5: Multi-Filter Conjunction**: Combines month, category, merchant, account, and event-type.
- **T8.6: Standalone Module Invocation**: `python -m peit.dashboard` matches `peit --dashboard`.
- **T8.7: Standalone Help Flag**: `--help` displays complete documentation.
- **T8.8: Error on Missing Ledger**: Exits code 2 if `--dashboard` is run without `--ledger`.
- **T8.9: Graceful Empty Ledger Dashboard**: Generates valid zero-state dashboard without stacktrace.

### Suite 9: Inflation & Benchmark Visualizations (`test/test_dashboard.py`)
- **T9.1: Personal vs. National CPI Time-Series Dataset**:
  - *Given*: 3 consecutive months of ledger transactions and a valid benchmark CSV (`config/benchmark_cpi_mx.csv`).
  - *When*: Generating the CPI comparison chart dataset.
  - *Then*: Produces aligned series for personal inflation, benchmark CPI, and calculated inflation gap ($\Delta \pi_t$).
- **T9.2: Missing Benchmark Fallback Banner**:
  - *Given*: Multi-month ledger, but no `--benchmark` flag provided.
  - *When*: Dashboard is generated.
  - *Then*: CPI chart renders personal inflation line and embeds an informative notice explaining how to supply `--benchmark`.
- **T9.3: Inflation Gap Visual Styling**:
  - *Given*: Personal inflation higher than national CPI in Month 1, lower in Month 2.
  - *When*: Dataset styling is generated.
  - *Then*: Applies distinct red/coral shading for penalty periods and green shading for insulated periods.

### Suite 10: Decomposition Waterfall & Category Contribution Visualizations (`test/test_dashboard.py`)
- **T10.1: Bennett Exact Additive Waterfall Dataset**:
  - *Given*: Consecutive months with known price shifts and quantity shifts.
  - *When*: Generating waterfall chart data.
  - *Then*: Contains bars for: Base Spend, Price Effect ($\Delta E_{\mathrm{price}}$), Quantity Effect ($\Delta E_{\mathrm{quantity}}$), and Final Spend, summing with zero residual.
- **T10.2: Category Contribution Diverging Bar Dataset**:
  - *Given*: Matched items across 3 categories with positive and negative price movements.
  - *When*: Generating category contribution chart data.
  - *Then*: Contains accurate Percentage-Point Contributions ($\mathrm{PPC}$) and Absolute Dollar Impacts ($\mathrm{ADI}$) per category, with $\sum \mathrm{PPC} \equiv \pi_t \times 100$.
- **T10.3: Zero Matched Items Handling**:
  - *Given*: Consecutive months sharing zero identical items.
  - *When*: Generating decomposition datasets.
  - *Then*: Returns zeroed waterfall and category datasets with 0% coverage badge, avoiding division errors.

### Suite 11: Tabbed UI Navigation & Graceful Degradation (`test/test_dashboard.py`)
- **T11.1: Tab Markup & Navigation Controls**:
  - *Given*: Generated dashboard HTML.
  - *When*: Inspecting DOM structure.
  - *Then*: Contains tab buttons for `tab-spending`, `tab-welfare`, and `tab-ledger`, along with client-side JavaScript tab switching handlers.
- **T11.2: Insufficient History (< 2 months) Empty-State Card**:
  - *Given*: A ledger containing only 1 month of data.
  - *When*: Dashboard HTML is generated.
  - *Then*: Tab 1 renders cash flow charts normally, while Tab 2 renders an informative card stating that at least 2 consecutive months of data are required.
- **T11.3: Active Tab State Persistence**:
  - *Given*: Dashboard HTML rendered in browser.
  - *When*: Tab buttons are clicked.
  - *Then*: Script toggles `active` CSS class and shows/hides corresponding tab panels.

---

## 8. Verification Checklist

- [ ] All 11 design test suites implemented and passing 100% via `pytest test/test_dashboard.py test/test_cli.py`.
- [ ] `test/run_tests.sh -s dashboard` passes cleanly.
- [ ] `test/run_tests.sh --all` runs all suites (`core`, `ledger`, `cli`, `dashboard`) successfully.
- [ ] Ingesting `data/example_month.csv` and generating the dashboard creates a valid tabbed HTML page with all charts functional.
- [ ] Passing `--benchmark config/benchmark_cpi_mx.csv` displays personal vs. national CPI comparison in Tab 2.
- [ ] Repository documentation and scaffold validation passes:
  - `bash -n test/run_tests.sh`
  - `bash -n LLM/scripts/handler.sh`
  - `bash LLM/scripts/handler.sh validate --root "$PWD"`
  - `git diff --check`
