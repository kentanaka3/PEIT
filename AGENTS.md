# Agent instructions for `PEIT`

This file is the repository-level contract for any human, coding agent,
assistant working in this repository.

## Repository map

```text
PEIT/
├── config/   # configuration files, templates, and project data definitions
├── data/     # raw and processed datasets
├── doc/      # thesis, reports, figures, and documentation (see doc/README.md)
├── mobile/   # Flutter mobile client (OCR, Drift SQLite, LAN sync)
├── src/      # Python source code
├── test/     # Python tests
├── util/     # utility scripts, templates, and helpers
└── web/      # browser workbench source code and static assets
```

## Custom agents

Use the [`.github/agents/latex-docxer.agent.md`](.github/agents/latex-docxer.agent.md)
agent for PEIT LaTeX document creation, review, and evidence-bounded builds.

Use the [`.github/agents/bash-scripter.agent.md`](.github/agents/bash-scripter.agent.md)
agent for PEIT scientific Bash scripting, validation, and reproducible workflows.


## Scientific context

The PEIT project analyzes personal expenditure and personal price change. Its
first milestone covers monthly receipt ingestion, validation, provenance,
comparison, and visualization-oriented outputs. Forecasting, clustering, and
financial-management views are future or adjacent capabilities unless a source
file explicitly demonstrates them.

Preserve the distinction between observations, model predictions, analyst
labels, hypotheses, and demonstrated results. Never present an LLM-generated
statement as a scientific result without a traceable source, command, dataset
version, or human review record.

## Before changing files

1. Read this file, the target file, and nearby README/configuration docs.
2. Run `git status --short`; existing changes belong to the user.
3. State the intended scope in the work log or commit message.
4. Make small, incremental changes that are easy to review or revert.
5. Prefer repository-relative paths in documentation.

## After changing files

Run the smallest meaningful checks and record the outcome. For this scaffold:

```bash
bash -n test/run_tests.sh
bash test/run_tests.sh --all
git diff --check
git status --short
```

For PEIT code, run the focused test or a dry run such as `make -n TARGET ...`.
Do not run downloads, SLURM submissions, Conda installation, or inference as a
smoke test.

## Python environment

Before running Python commands or tests, agents should activate the virtual
environment or project Conda environment:

```bash
# Repository-local Conda environment (Python 3.13):
conda activate "$PWD/.venv/PEIT"
export PATH="$CONDA_PREFIX/bin:$PATH"

# Ensure the package is in PYTHONPATH or installed in editable mode:
export PYTHONPATH="$PWD/src:$PYTHONPATH"
```

## Data, privacy, and secrets

- Never commit `.env` files, API keys, access tokens, SSH keys, passwords, or
  private prompts.
- Never commit raw personal receipts, financial transaction ledgers, large catalogs, model checkpoints, or generated
  artifacts. Keep them in the approved storage.
- Redact credentials, personal data, and internal URLs in examples.
- Treat external LLM services as untrusted data processors until approved.

## LLM quality rules

- Reusable prompts declare purpose, inputs, expected output, assumptions, and
  failure behavior.
- Experiments record model/provider, date, prompt version, context sources,
  settings when available, and reviewer.
- Mark uncertain or inferred statements explicitly.
- Validate structured output before using it in a pipeline.
- Require a human checkpoint before code edits, data access, cluster jobs, or
  publication.

## Documentation and script navigation

When reconciling Markdown with implementation, inspect the referenced
Makefile, Bash, and Python files directly. Record repository-relative paths and
line ranges in the Markdown, distinguish documented behavior from inferred
behavior, and update documentation when a referenced script has been removed.
Do not recreate deleted scripts merely to satisfy stale documentation. Prefer
focused checks such as `bash -n`, Python syntax/type checks already provided by
the project, and `make -n`; never run downloads, inference, or cluster jobs as
documentation validation.

For Bash function documentation, place a short description immediately before
the function declaration and include a `# N` comment counting the complete
function body. Update that count whenever the function changes; treat it as a
navigation aid rather than a permanent source reference.

## Escalation and definition of done

Ask before changing pipeline semantics, moving/deleting existing files,
installing software, accessing restricted data, submitting jobs, or publishing.

A change is done when the intended files are present, unrelated files are
untouched, safety-sensitive paths are ignored, validation passes (or its
failure is documented), links and implementation claims are current, and the
next human decision is clear.
