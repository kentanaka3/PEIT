# Agent instructions for `PEIT`

This file is the repository-level contract for any human, coding agent,
assistant working in this repository.

## Repository map

```text
PEIT/
├── config/   # configuration files, templates, and project data definitions
├── data/     # raw and processed datasets
├── doc/      # thesis, reports, figures, and supporting documentation
├── LLM/      # LLM knowledge, prompts, workflows, experiments, and reviews
├── src/      # Python source code
├── test/     # Python tests
├── util/     # utility scripts, templates, and helpers
└── web/      # [planned / unreleased] web application source code and static assets
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
bash -n LLM/scripts/handler.sh
bash LLM/scripts/handler.sh navigate --root "$PWD"
bash LLM/scripts/handler.sh validate
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

Use the unified Markdown handler before and after documentation work:

```bash
bash LLM/scripts/handler.sh navigate --root "$PWD"
bash LLM/scripts/handler.sh validate
```

The handler is the authoritative entry point for documentation maintenance:

- `init` creates only missing LLM directories and starter documents; it does
  not recreate deleted legacy helper scripts.
- `adr` creates a new Architecture Decision Record in `doc/adr/`
  with a unique ID, title, and template.
- `navigate` produces a Markdown inventory with repository-relative paths,
  line counts, and heading locations. Use it to find the relevant context
  before editing.
- `validate` checks the documentation scaffold, handler prerequisites, and
  required executable script/documentation entry points without modifying
  files.

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

## Two-phase project validation

Before declaring a documentation or script-navigation task complete, run the
handler in two phases from the PhD project root:

```bash
bash LLM/scripts/handler.sh init --dry-run
bash LLM/scripts/handler.sh validate --root "$PWD"
```

The first command previews workspace initialization and must not modify files.
The second command performs the complete read-only validation, including the
documentation scaffold, local Markdown paths, stale script references, Bash
syntax, and malformed fenced code blocks. Do not replace the dry-run with
`init` unless workspace creation is explicitly requested.

For a single Bash template or script, use the handler's file mode:

```bash
bash LLM/scripts/handler.sh navigate --file LLM/scripts/default.sh
bash LLM/scripts/handler.sh validate --file LLM/scripts/default.sh
```

File-mode validation checks only the selected supported script, including Bash
syntax and inline function documentation line counts. Directory-mode
validation remains the complete project check.

## Escalation and definition of done

Ask before changing pipeline semantics, moving/deleting existing files,
installing software, accessing restricted data, submitting jobs, or publishing.
When requirements are ambiguous, make a conservative assumption, record it in
`LLM/00_governance/decisions.md`, and list the unresolved issue in
`LLM/00_governance/open_questions.md`.

A change is done when the intended files are present, unrelated files are
untouched, safety-sensitive paths are ignored, validation passes (or its
failure is documented), links and implementation claims are current, and the
next human decision is clear.
