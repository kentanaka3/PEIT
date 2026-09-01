# Claude project instructions

This file is a provider-specific entry point for Claude. The repository-wide
contract is [`AGENTS.md`](AGENTS.md); read and follow it before working.

## Navigation contract

Treat executable files as the source of truth. Begin with `git status --short`,
inspect `LLM/README.md`, and use the safe documentation handler:

```bash
bash LLM/scripts/handler.sh navigate --root "$PWD" --scripts
bash LLM/scripts/handler.sh validate --root "$PWD"
```

Preserve user changes. Do not run downloads, inference, environment setup,
SLURM jobs, or publication workflows as smoke tests. Before editing, state the
scope, assumptions, affected files, and validation plan. After editing, show
the evidence, failures, and remaining human decisions.

## Scientific and LLM boundaries

Keep observations, model predictions, analyst labels, hypotheses, and
demonstrated scientific results distinct. Never turn an LLM inference into a
scientific claim without traceable source, command, dataset/version, and human
review. Ask before changing pipeline semantics or accessing restricted data.

## PEIT terminology

Use “personal price change” or “personal inflation index” only when the
definition and formula are stated. Use “expenditure change” for changes caused
by both prices and quantities. Keep observations, normalized labels, derived
indices, estimates, forecasts, and hypotheses visibly separate.
