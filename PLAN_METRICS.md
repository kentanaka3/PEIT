# Plan: Personal Welfare Metrics and Economic Price Indices (`peit.metrics`)

> [!NOTE]
> **Status**: Planning Specification Only (No Implementation).
> This document specifies the architectural, mathematical, CLI, and test design for the future personal welfare metrics and economic price index module in PEIT.

---

## 1. Overview & Objectives

The goal of the `peit.metrics` module is to bridge macroeconomic inflation indices and personal financial reality through transparent, inspectable personal welfare measurements.

While standard national consumer price indices (such as INEGI INPC in Mexico or BLS CPI in the United States) track an aggregate, population-weighted hypothetical basket, PEIT analyzes realized individual transactions.

The future module will provide three core personal welfare metrics:
1. **Personal vs. National CPI Deviation**: Compares the user's realized personal inflation against official national benchmark statistics.
2. **Category Inflation Decomposition (Dual Metric)**: Determines which expenditure categories drive personal price changes, reported in both **Percentage-Point Contribution** and **Absolute Dollar Impact**.
3. **Expenditure Growth Decomposition (Dual Mathematical Models)**: Disentangles whether higher monthly bills stem from paying higher prices (pure inflation) or buying more goods (volume/lifestyle expansion), planned using:
   - **Exact Additive Decomposition (Bennett / Montgomery-Vartia)**
   - **Multiplicative Ratio Decomposition (Index Duality)**
4. **Strict Matched-Only Discipline**: All price-change metrics operate strictly on exact matched items ($M_t = B_{t-1} \cap B_t$), reporting basket coverage percentages without silently inventing synthetic prices.

---

## 2. Mathematical Formulations & Concrete Examples

### 2.1 Notation & Data Primitives

For consecutive months $t-1$ (base/previous) and $t$ (current):
- $I_{t-1}$: Items purchased in month $t-1$.
- $I_t$: Items purchased in month $t$.
- $M_t = I_{t-1} \cap I_t$: The set of exact normalized matched items purchased in both months.
- For each item $i \in M_t$:
  - $p_{i, t-1}$ and $p_{i, t}$: Quantity-weighted average unit price in month $t-1$ and $t$.
  - $q_{i, t-1}$ and $q_{i, t}$: Total quantity consumed in month $t-1$ and $t$.
  - $e_{i, t-1} = p_{i, t-1} q_{i, t-1}$: Expenditure on item $i$ in month $t-1$.
  - $e_{i, t} = p_{i, t} q_{i, t}$: Expenditure on item $i$ in month $t$.
- Total matched expenditure:
  - $E^{M}_{t-1} = \sum_{i \in M_t} p_{i, t-1} q_{i, t-1}$
  - $E^{M}_{t} = \sum_{i \in M_t} p_{i, t} q_{i, t}$
- Total overall expenditure (including unmatched items):
  - $E_{t-1} = \sum_{j \in I_{t-1}} e_j$
  - $E_t = \sum_{k \in I_t} e_k$

---

### 2.2 Strict Matched-Only Principle & Basket Coverage

In accordance with PEIT's core design principle (*never invent observations*), items that appear in only one month are **never** imputed.

Instead, the system reports:
\[
  C^{\mathrm{item}}_t = 100 \times \frac{|M_t|}{|I_{t-1}|} \quad (\text{Item Count Coverage \%})
\]
\[
  C^{\mathrm{exp}}_{t-1} = 100 \times \frac{E^M_{t-1}}{E_{t-1}} \quad (\text{Base Expenditure Coverage \%})
\]
\[
  C^{\mathrm{exp}}_t = 100 \times \frac{E^M_t}{E_t} \quad (\text{Current Expenditure Coverage \%})
\]

#### Concrete Example:
- **January (Month $t-1$)**:
  - Milk: 1 unit @ \$3.00 = \$3.00
  - Bread: 1 unit @ \$2.00 = \$2.00
  - Total January Spend = \$5.00
- **February (Month $t$)**:
  - Milk: 1 unit @ \$3.50 = \$3.50 (Price rose +16.7%)
  - Coffee: 1 unit @ \$6.00 = \$6.00 (First time purchase)
  - Total February Spend = \$9.50
- **Matched Analysis**:
  - Matched item: Milk only ($M_t = \{\text{Milk}\}$).
  - Bread and Coffee are excluded from the price index.
  - Item Coverage = $\frac{1 \text{ item}}{2 \text{ items}} = 50.0\%$.
  - Base Expenditure Coverage = $\frac{\$3.00}{\$5.00} = 60.0\%$.
  - Current Expenditure Coverage = $\frac{\$3.50}{\$9.50} = 36.8\%$.

---

### 2.3 Category Inflation Decomposition (Dual Metric)

Personal inflation over matched items is:
\[
  \pi_t = \frac{P_t}{P_{t-1}} - 1
\]
Where $P$ is the price index over matched items (e.g. Laspeyres or Jevons).

For each spending category $c$ (e.g. "Food and beverages", "Transport", "Utilities"):
Let $M_{c, t}$ be the matched items belonging to category $c$.
Let $w_{c, t-1} = \frac{\sum_{i \in M_{c, t}} e_{i, t-1}}{E^M_{t-1}}$ be the category's budget share in the matched basket.
Let $\pi_{c, t} = \frac{P_{c, t}}{P_{c, t-1}} - 1$ be the category-specific price inflation.

#### Dual Metric Reporting:
1. **Percentage-Point Contribution ($\mathrm{PPC}_c$)**:
   \[
     \mathrm{PPC}_c = w_{c, t-1} \times \pi_{c, t} \times 100
   \]
   Property: $\sum_c \mathrm{PPC}_c = \pi_t \times 100$ (Percentage-point contributions sum exactly to total personal inflation).
2. **Absolute Dollar Impact ($\mathrm{ADI}_c$)**:
   \[
     \mathrm{ADI}_c = \sum_{i \in M_{c, t}} q_{i, t-1} (p_{i, t} - p_{i, t-1})
   \]
   Represents how many additional dollars the user paid in month $t$ solely because prices in category $c$ increased, holding base consumption constant.

#### Concrete Worked Example:
Suppose matched monthly budget is \$1,000 in January, with 3 categories:
- **Food** (Budget share $w = 50\%$ / \$500 spend): Food prices rise $+10\%$.
  - $\mathrm{PPC}_{\text{Food}} = 0.50 \times (+10\%) = \mathbf{+5.0\text{ percentage points}}$.
  - $\mathrm{ADI}_{\text{Food}} = \$500 \times (+10\%) = \mathbf{+\$50.00}$.
- **Transport** (Budget share $w = 30\%$ / \$300 spend): Transport prices drop $-5\%$.
  - $\mathrm{PPC}_{\text{Transport}} = 0.30 \times (-5\%) = \mathbf{-1.5\text{ percentage points}}$.
  - $\mathrm{ADI}_{\text{Transport}} = \$300 \times (-5\%) = \mathbf{-\$15.00}$.
- **Utilities** (Budget share $w = 20\%$ / \$200 spend): Utility prices rise $+2\%$.
  - $\mathrm{PPC}_{\text{Utilities}} = 0.20 \times (+2\%) = \mathbf{+0.4\text{ percentage points}}$.
  - $\mathrm{ADI}_{\text{Utilities}} = \$200 \times (+2\%) = \mathbf{+\$4.00}$.
- **Total Personal Inflation**: $+5.0 - 1.5 + 0.4 = \mathbf{+3.9\%}$.
- **Total Absolute Dollar Impact**: $+\$50.00 - \$15.00 + \$4.00 = \mathbf{+\$39.00}$.

---

### 2.4 Personal vs. National CPI Deviation

To answer: *"Is my personal cost of living rising faster or slower than official inflation?"*

Let $\pi^{\mathrm{personal}}_t$ be the user's personal matched price inflation rate for month $t$.
Let $\pi^{\mathrm{national}}_t$ be the official national CPI MoM inflation rate for the matching period (e.g. from INEGI INPC for Mexico or BLS CPI for US).

#### Metrics Computed:
1. **Inflation Gap / Deviation ($\Delta \pi_t$)**:
   \[
     \Delta \pi_t = \pi^{\mathrm{personal}}_t - \pi^{\mathrm{national}}_t
   \]
   - $\Delta \pi_t > 0$: User is experiencing **above-average inflationary pressure** (personal penalty).
   - $\Delta \pi_t < 0$: User is experiencing **below-average inflation** (personal insulation).
2. **Cumulative Divergence Index**:
   Compound tracking over time comparing $I^{\mathrm{personal}}_t$ vs. $I^{\mathrm{national}}_t$ normalized to 100.0 at base month.
3. **Primary Divergence Driver**:
   Identifies which category contributed most to the gap by comparing category personal inflation with national category sub-indices when available.

#### Concrete Worked Example:
- **Month**: February 2026 (Currency: MXN)
- **National CPI (INEGI INPC)**: $+0.35\%$ MoM.
- **Personal Inflation ($\pi^{\mathrm{personal}}$)**: $+1.20\%$ MoM.
- **Inflation Gap**: $+1.20\% - 0.35\% = \mathbf{+0.85\text{ percentage points}}$.
- **Interpretation**: Personal living expenses on recurring items rose $0.85$ percentage points faster than the national average, primarily driven by a $+12\%$ surge in local grocery items.

---

### 2.5 Expenditure Growth Decomposition: Two Mathematical Models

When a user's monthly spending changes from $E^M_{t-1}$ to $E^M_t$, how much was caused by **Price Changes (Inflation)** versus **Quantity Changes (Volume/Lifestyle)**?

The plan specifies supporting **both** mathematical models:

```
                  Matched Expenditure Change: ΔE = E_t - E_{t-1}
                                       |
           +---------------------------+---------------------------+
           |                                                       |
           v                                                       v
   [Model A: Exact Additive]                             [Model B: Multiplicative Ratio]
(Bennett / Montgomery-Vartia)                               (Fisher / Laspeyres Duality)
           |                                                       |
  ΔE = ΔE_price + ΔE_quantity                            E_t / E_{t-1} = P_{t-1,t} × Q_{t-1,t}
   - In exact dollar amounts                              - In ratio/index multipliers
   - Zero residual property                               - Symmetrical economic duality
```

#### Model A: Exact Additive Decomposition (Bennett / Montgomery-Vartia)
Decomposes the dollar change $\Delta E = E^M_t - E^M_{t-1}$ directly into:
\[
  \Delta E = \Delta E_{\mathrm{price}} + \Delta E_{\mathrm{quantity}}
\]
Where:
\[
  \Delta E_{\mathrm{price}} = \sum_{i \in M_t} \left(\frac{q_{i, t-1} + q_{i, t}}{2}\right) (p_{i, t} - p_{i, t-1})
\]
\[
  \Delta E_{\mathrm{quantity}} = \sum_{i \in M_t} \left(\frac{p_{i, t-1} + p_{i, t}}{2}\right) (q_{i, t} - q_{i, t-1})
\]

**Key Mathematical Property**:
$\Delta E_{\mathrm{price}} + \Delta E_{\mathrm{quantity}} \equiv \Delta E$ exactly, with **zero residual**, using average quantity and price weights.

#### Model B: Multiplicative Ratio Decomposition (Index Duality)
Decomposes the spending ratio:
\[
  V_{t-1, t} = \frac{E^M_t}{E^M_{t-1}} = P_{t-1, t} \times Q_{t-1, t}
\]
Using the **Fisher Ideal Index** (the unique superlative index satisfying factor reversal):
\[
  P^{\mathrm{Fisher}}_{t-1, t} = \sqrt{P^{\mathrm{Laspeyres}} \times P^{\mathrm{Paasche}}}
\]
\[
  Q^{\mathrm{Fisher}}_{t-1, t} = \sqrt{Q^{\mathrm{Laspeyres}} \times Q^{\mathrm{Paasche}}}
\]
Where:
- $P^{\mathrm{Laspeyres}} = \frac{\sum p_{i,t} q_{i,t-1}}{\sum p_{i,t-1} q_{i,t-1}}$
- $P^{\mathrm{Paasche}} = \frac{\sum p_{i,t} q_{i,t}}{\sum p_{i,t-1} q_{i,t}}$
- $Q^{\mathrm{Laspeyres}} = \frac{\sum p_{i,t-1} q_{i,t}}{\sum p_{i,t-1} q_{i,t-1}}$
- $Q^{\mathrm{Paasche}} = \frac{\sum p_{i,t} q_{i,t}}{\sum p_{i,t} q_{i,t-1}}$

**Key Mathematical Property**:
$P^{\mathrm{Fisher}} \times Q^{\mathrm{Fisher}} \equiv \frac{E^M_t}{E^M_{t-1}}$ exactly.

#### Concrete Worked Example:
- **Base Month (January)**:
  - Rice: $p_0 = \$2.00$, $q_0 = 10\text{ kg}$ $\rightarrow e_0 = \$20.00$.
- **Current Month (February)**:
  - Rice: $p_1 = \$3.00$, $q_1 = 12\text{ kg}$ $\rightarrow e_1 = \$36.00$.
- **Expenditure Delta**:
  - $\Delta E = \$36.00 - \$20.00 = \mathbf{+\$16.00}$ (an $80.0\%$ increase).

**Applying Model A (Exact Additive)**:
- Average quantity $\bar{q} = \frac{10 + 12}{2} = 11\text{ kg}$.
- Average price $\bar{p} = \frac{\$2.00 + \$3.00}{2} = \$2.50/\text{kg}$.
- $\Delta E_{\mathrm{price}} = 11 \times (\$3.00 - \$2.00) = \mathbf{+\$11.00}$ (Price Inflation Effect).
- $\Delta E_{\mathrm{quantity}} = \$2.50 \times (12 - 10) = \mathbf{+\$5.00}$ (Volume Expansion Effect).
- Check: $\$11.00 + \$5.00 = \mathbf{+\$16.00} \equiv \Delta E$ (exact zero residual!).

**Applying Model B (Multiplicative Ratio)**:
- Expenditure Ratio $V = \frac{36.00}{20.00} = 1.8000$ ($+80.0\%$).
- $P^{\mathrm{Fisher}} = \frac{3.00}{2.00} = 1.5000$ ($+50.0\%$ price increase).
- $Q^{\mathrm{Fisher}} = \frac{12}{10} = 1.2000$ ($+20.0\%$ quantity increase).
- Check: $1.5000 \times 1.2000 = \mathbf{1.8000} \equiv V$ (exact duality!).

---

## 3. Architecture & Data Ingestion Design

```text
PEIT/
├── config/
│   ├── benchmark_cpi_mx.csv       # [NEW] Default reference INEGI INPC monthly benchmark
│   └── benchmark_cpi_us.csv       # [NEW] Default reference US BLS CPI monthly benchmark
├── src/
│   └── peit/
│       ├── core.py                # Existing core schema validation & Carli index
│       ├── ledger.py              # Signed transaction ledger & SQLite projection
│       ├── dashboard.py           # Multi-graph visualizer
│       └── metrics.py             # [NEW PLANNED MODULE] Welfare metrics & decompositions
├── test/
│   ├── test_metrics.py            # [NEW PLANNED TEST SUITE]
│   └── run_tests.sh               # Test runner with 'metrics' suite
└── PLAN_METRICS.md                # This planning document
```

### 3.1 Benchmark CPI Ingestion & Schema

To maintain PEIT's offline, privacy-first nature, national benchmark series are provided via clean local CSV files in `config/`:

#### Benchmark CSV Schema (`config/benchmark_cpi_mx.csv`):
```csv
month,country,series_name,cpi_index,mom_inflation_percent,yoy_inflation_percent,source
2026-01,MEX,INEGI_INPC,138.452,0.49,4.21,INEGI
2026-02,MEX,INEGI_INPC,138.937,0.35,4.15,INEGI
2026-03,MEX,INEGI_INPC,139.382,0.32,4.08,INEGI
```

#### CLI Support for Custom Benchmarks:
Users can supply their own country or local benchmark file:
```bash
peit --ledger data/ledger.jsonl --metrics --benchmark config/benchmark_cpi_mx.csv
```

---

## 4. CLI Interface Design (`peit --metrics`)

The module will integrate with PEIT's command-line interface:

```bash
# 1. Compute full personal welfare metrics report for a ledger
peit --ledger data/ledger.jsonl --metrics

# 2. Compute metrics against a specific national benchmark
peit --ledger data/ledger.jsonl --metrics --benchmark config/benchmark_cpi_mx.csv

# 3. Filter metrics to specific month comparison
peit --ledger data/ledger.jsonl --metrics --month 2026-02

# 4. Filter metrics to specific account and category
peit --ledger data/ledger.jsonl --metrics --category "Food and beverages" --account default:checking

# 5. Output structured JSON for scripts or dashboard integration
peit --ledger data/ledger.jsonl --metrics --json
```

#### Sample Terminal Output Mockup:
```text
================================================================================
PEIT Personal Welfare & Inflation Decomposition Report
Period: 2026-02 vs 2026-01 | Account: default:checking
================================================================================

[1] BASKET COVERAGE & INTEGRITY
--------------------------------------------------------------------------------
Matched Items:                 18 / 24 items (75.0% item coverage)
Base Matched Expenditure:      $2,450.00 / $2,800.00 (87.5% spend coverage)
Current Matched Expenditure:   $2,620.00 / $3,100.00 (84.5% spend coverage)

[2] PERSONAL INFLATION VS. NATIONAL BENCHMARK (INEGI INPC)
--------------------------------------------------------------------------------
Personal Matched Inflation:    +2.45% MoM
National Benchmark (Mexico):   +0.35% MoM
Inflation Gap (Penalty):       +2.10 percentage points (Above National Average)

[3] CATEGORY INFLATION DECOMPOSITION
--------------------------------------------------------------------------------
Category                  Spend (t-1)   MoM Infl.    Contrib (PPC)   Dollar Impact
--------------------------------------------------------------------------------
Food and beverages          $1,200.00     +4.20%       +2.06 pp         +$50.40
Transport                     $650.00     +1.10%       +0.29 pp          +$7.15
Utilities                     $400.00     +0.50%       +0.08 pp          +$2.00
Healthcare                    $200.00     +0.10%       +0.01 pp          +$0.20
--------------------------------------------------------------------------------
Total Matched Basket        $2,450.00     +2.45%       +2.45 pp         +$59.75

[4] EXPENDITURE GROWTH DECOMPOSITION
--------------------------------------------------------------------------------
Matched Spending Change:       +$170.00 (+6.94%)

Model A (Exact Additive - Bennett):
  • Price Inflation Effect:    +$59.75  (35.1% of spending growth)
  • Quantity Volume Effect:    +$110.25 (64.9% of spending growth)
  • Total Reconciled Delta:    +$170.00 (Exact zero residual)

Model B (Multiplicative Ratio - Fisher Duality):
  • Total Expenditure Index:   106.94% (+6.94%)
  • Price Index (Fisher):      102.45% (+2.45% inflation)
  • Quantity Index (Fisher):   104.38% (+4.38% volume consumed)
  • Duality Factor Check:      1.0245 × 1.0438 = 1.0694 (Exact)
================================================================================
```

---

## 5. Detailed Design Tests & Verification Matrix (`test/test_metrics.py`)

When this future module is implemented, it will be validated against the following 8 comprehensive design test suites:

### Suite 1: Basket Matching & Coverage Integrity
- **T1.1: Exact Item Matching Precision**:
  - *Given*: Month $t-1$ has items `[A, B, C]` and Month $t$ has items `[B, C, D]`.
  - *When*: Matched basket is formed.
  - *Then*: Matched set is strictly `[B, C]`; `A` and `D` are excluded from matched price relative calculations.
- **T1.2: Coverage Percentage Accuracy**:
  - *Given*: 2 matched items out of 4 base items.
  - *When*: Coverage metrics are computed.
  - *Then*: `item_coverage_percent == 50.0%`, and base/current expenditure coverage percentages accurately match the sums.
- **T1.3: Zero Matched Items Edge Case**:
  - *Given*: Month $t-1$ and Month $t$ share zero identical item names.
  - *When*: Metrics are computed.
  - *Then*: Returns `coverage == 0.0%`, price inflation is `None` with status `"insufficient_common_basket"`, without raising exceptions.

### Suite 2: Category Inflation Decomposition (PPC & ADI)
- **T2.1: Percentage-Point Contribution Additive Sum**:
  - *Given*: 4 categories with positive and negative price changes.
  - *When*: Category decomposition is calculated.
  - *Then*: $\sum \mathrm{PPC}_c \equiv \pi_t \times 100$ within floating-point tolerance ($10^{-5}$).
- **T2.2: Absolute Dollar Impact Additive Sum**:
  - *Given*: Matched items with known base quantities $q_{i, t-1}$ and price changes $\Delta p_i$.
  - *When*: Category ADI is calculated.
  - *Then*: Each category ADI equals $\sum q_{i,t-1} \Delta p_i$, and total matches overall base-weighted price change.
- **T2.3: Single Category Dominance**:
  - *Given*: All categories have 0% price change except "Food" at +10%.
  - *When*: Decomposition is evaluated.
  - *Then*: Food's PPC equals the entire personal inflation rate.

### Suite 3: Personal vs. National Benchmark Deviation
- **T3.1: Benchmark Gap Calculation**:
  - *Given*: Personal inflation of $+3.2\%$ and benchmark CPI of $+2.0\%$.
  - *When*: Benchmark deviation is computed.
  - *Then*: `inflation_gap == +1.20 pp` with status `"above_national_average"`.
- **T3.2: Missing Benchmark Month Handling**:
  - *Given*: Ledger has data for `2026-05`, but benchmark CSV only covers up to `2026-03`.
  - *When*: Benchmark comparison is executed.
  - *Then*: Emits personal metrics normally, with `benchmark_gap = None` and a clear notice that benchmark data is pending.
- **T3.3: Custom Benchmark CSV Ingestion**:
  - *Given*: Custom CSV via `--benchmark custom_cpi.csv`.
  - *When*: Ingested.
  - *Then*: Parses schema, validates date alignment, and uses custom series for deviation calculations.

### Suite 4: Exact Additive Decomposition (Bennett / Montgomery-Vartia)
- **T4.1: Zero Residual Invariant**:
  - *Given*: Complex basket of 20 items with arbitrary price and quantity changes.
  - *When*: Model A additive decomposition is evaluated.
  - *Then*: $\Delta E_{\mathrm{price}} + \Delta E_{\mathrm{quantity}} == \Delta E$ exactly ($|(\Delta E_P + \Delta E_Q) - \Delta E| < 10^{-6}$).
- **T4.2: Pure Price Change Scenario (No Volume Change)**:
  - *Given*: Quantities are unchanged ($q_{i,t} = q_{i,t-1}$), prices rise by \$2.00 on 5 units.
  - *When*: Evaluated under Model A.
  - *Then*: $\Delta E_{\mathrm{price}} == +\$10.00$, $\Delta E_{\mathrm{quantity}} == \$0.00$.
- **T4.3: Pure Volume Change Scenario (No Price Change)**:
  - *Given*: Prices are unchanged ($p_{i,t} = p_{i,t-1}$), quantity rises from 2 to 6 units at \$5/unit.
  - *When*: Evaluated under Model A.
  - *Then*: $\Delta E_{\mathrm{price}} == \$0.00$, $\Delta E_{\mathrm{quantity}} == +\$20.00$.

### Suite 5: Multiplicative Ratio Decomposition (Fisher Duality)
- **T5.1: Factor Reversal / Product Invariant**:
  - *Given*: Multiple items with shifting prices and quantities.
  - *When*: Model B multiplicative decomposition is evaluated.
  - *Then*: $P^{\mathrm{Fisher}} \times Q^{\mathrm{Fisher}} \equiv \frac{E^M_t}{E^M_{t-1}}$ to within $10^{-6}$.
- **T5.2: Symmetry & Time Reversal**:
  - *Given*: Evaluating month $t-1$ to $t$, and the inverse $t$ to $t-1$.
  - *When*: Fisher price and quantity indices are calculated.
  - *Then*: $P^{\mathrm{Fisher}}_{t, t-1} = \frac{1}{P^{\mathrm{Fisher}}_{t-1, t}}$.

### Suite 6: CLI & Output Formatting
- **T6.1: CLI Table Output Formatting**:
  - *Given*: Executing `peit --ledger data/ledger.jsonl --metrics`.
  - *When*: Invoked.
  - *Then*: Emits clean ASCII report with sections for Coverage, Benchmark Deviation, Category Breakdown, and Both Decomposition Models.
- **T6.2: Structured JSON Output**:
  - *Given*: Executing `peit --ledger data/ledger.jsonl --metrics --json`.
  - *When*: Invoked.
  - *Then*: Outputs valid JSON parseable into a structured Python dictionary with standard numeric types.

---

## 6. Implementation Roadmap

When the project approves implementation of this milestone, the rollout will follow these four phases:

- [ ] **Phase 1: Reference Data & Primitives**
  - Create standard reference benchmark files: `config/benchmark_cpi_mx.csv` and `config/benchmark_cpi_us.csv`.
  - Implement benchmark CSV parser and validator in `src/peit/metrics.py`.
- [ ] **Phase 2: Core Metric Algorithms (`src/peit/metrics.py`)**
  - Implement matched basket extractor with strict coverage tracking.
  - Implement category inflation decomposition (PPC & ADI).
  - Implement personal vs. national CPI gap calculator.
  - Implement Model A (Bennett additive decomposition) and Model B (Fisher multiplicative ratio decomposition).
- [ ] **Phase 3: CLI Integration (`src/peit/cli.py`)**
  - Add `--metrics` and `--benchmark <path>` flags to `peit`.
  - Implement terminal reporting and `--json` formatting.
- [ ] **Phase 4: Test Suite & Runner Automation**
  - Implement all 6 design test suites in `test/test_metrics.py`.
  - Update `test/run_tests.sh` to add `metrics` suite.
  - Optional: Expose metric summary cards into `src/peit/dashboard.py`.
