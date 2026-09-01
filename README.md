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

The current project is an early, local-first prototype supporting transparent
receipt-line ingestion and analysis. It provides a Python toolkit for importing
personal receipt data, validating its schema, preserving provenance, and
deriving comparable monthly price and expenditure indicators. The broader
community ecosystem, distributed data-node model, and point-of-sale
integration are project vision and future scope, not capabilities demonstrated
by the current repository.

The conceptual model is:

```text
receipt source → normalized line observations → validated ledger
       → fixed-basket price index
       → changing-basket expenditure index
       → month-over-month comparison
```

`item_raw`, amounts, dates, and source files remain observations. The
`item_normalized` key and categories are analyst-controlled matching labels.
Indices are derived values; estimates, forecasts, and hypotheses must remain
explicitly labelled and are never silently promoted to observations.

The current prototype provides CSV validation, JSON-lines audit append, exact
normalized-item matching, and transparent index calculations. Category
fallback, substitution equivalence, dynamic weights, uncertainty intervals,
multi-currency conversion, and forecasting are planned rather than
implemented. PEIT does not provide financial advice or claim that a derived
index represents an official inflation statistic.

## Further reading

- [`config/receipt_schema.md`](config/receipt_schema.md): input contract.
- [`LLM/01_context/pipeline_map.md`](LLM/01_context/pipeline_map.md):
  evidence-aware architecture.
- [`doc/showcase/peit.tex`](doc/showcase/peit.tex): conference demonstrator draft.
- [`doc/software/README.md`](doc/software/README.md): software documentation index.
