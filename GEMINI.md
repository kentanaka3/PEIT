# Gemini project instructions

This file is a provider-specific entry point for Gemini. The repository-wide
contract is [`AGENTS.md`](AGENTS.md); read and follow it before working.

## Safe autonomous workflow

```text
status → map → context → entry points → plan → small edit → focused test
  ↑                                                           ↓
  └────────────── report evidence, uncertainty, and review ───┘
```

Do not overwrite existing work. Do not run operational initialization,
downloads, inference, package installation, or cluster jobs without explicit
approval. Prefer repository-relative paths and focused tests or dry runs.

## Evidence discipline

Separate observed repository facts from assumptions and inferences. Scientific
results require source and data provenance plus human review. If documentation
and executable code disagree, report the discrepancy and inspect the
executable source before drawing conclusions.

For PEIT, verify receipt fields against `config/receipt_schema.csv` and index
claims against `src/peit/core.py` and `test/test_core.py`. Treat the conference
abstract in `doc/` as a presentation draft, not as evidence of unimplemented
features.
