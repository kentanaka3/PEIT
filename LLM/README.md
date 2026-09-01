# LLM and Artificial Intelligence Workspace

This directory documents the PEIT research and review process; it is not the
PEIT runtime or receipt-data store.

This is the controlled knowledge and experimentation layer for PEIT. It
supports collaboration between a researcher and an LLM while keeping source
code, scientific data, prompts, and generated outputs separate.

## Purpose and operating boundary

Use this directory to curate context, define bounded prompts, record
experiments, evaluate outputs, and route reviewed material. It is not a runtime
checkout, a model-training workspace, or a substitute for the source code and
configuration under `src/`, `config/`, and `test/`.

## Inputs, outputs, and side effects

- **Inputs:** repository-relative context, redacted excerpts, prompt versions,
  experiment metadata, and human decisions.
- **Outputs:** reviewable Markdown records and explicitly promoted outputs.
- **Assumptions:** missing provenance is recorded as `unknown`; narrative
  context is not automatically a scientific result.
- **Side effects:** the scripts can create missing workspace directories and
  starter files, but they do not install packages, download data, call an LLM
  provider, or submit jobs. Inspect script help and paths before running
  helpers in a new checkout.

## Navigation map

```text
00_governance → 01_context → 02_prompts → 03_workflows
       │              │             │             │
       └──────────────┴─────────────┴──────→ 04_experiments
                                                   │
                                                   ▼
                         05_evaluations → 06_outputs → 07_archive
                                                    │
                                                    ▼
                          human review ← handoffs/final report
```

The repository-level operating rules are in
[`../AGENTS.md`](../AGENTS.md). For a fresh crawl, run
[`scripts/handler.sh`](scripts/handler.sh) with `navigate --root .`; it is the
only supported navigation and validation entrypoint. Its line numbers are the
references used in handoffs.

## Workspace initialization

The workspace `init` target creates missing documentation directories and
starter files. It does not access receipts, install packages, or run analyses.
The legacy computational initializer is outside PEIT and is not part of this
documentation. The Makefile passes its configured paths to that script. The
script first requires the configured workspace, PEIT checkout, external
repositories, and commands to exist; it verifies or clones the configured
external repositories when possible, copies Leonardo launch files, loads
cluster modules, conditionally downloads and installs Miniconda, conditionally
creates the configured environment, and creates only missing documentation
files. These are external side effects; reading this description does not
perform them.

That is a computational-environment initializer. This directory is a
knowledge-and-review initializer. It does not touch `WORK_PATH`, install
packages, download models, call an LLM provider, or submit jobs.

## Repository path

Use repository-relative paths from the PEIT root. The executable source of
truth is `src/peit/core.py`; schemas and tests are under `config/` and `test/`.

## Markdown inventory and line references

The navigation handler reports the current Markdown inventory. At the time of
last verification (2026-08-30), the repository contained **35 Markdown files**
(excluding `.git/`): 1 under `.github/`, 4 root files (`AGENTS.md`,
`CLAUDE.md`, `GEMINI.md`, `README.md`), 8 under `PEIT/`, 6 under `doc/`, and
16 under `LLM/`. Run `bash LLM/scripts/handler.sh navigate --root "$PWD"` to
obtain the current count after edits. Crawler `path:line` locations are
generated references; line numbers are not inserted into Markdown content, so
they remain accurate after editing and a fresh crawl.

The optional `03_workflows/handoffs/` directory currently contains only its
`.gitkeep` marker; no final integration record is present in this checkout.
When a handoff is created, link it from this overview and record its evidence
boundaries, checks, and questions for the human researcher.

## Mental model

```text
                    HUMAN RESEARCHER
                          │
            question ─────┼───── review/decision
                          ▼
┌────────────────────────────────────────────────────┐
│                     LLM workspace                  │
│  context → prompt → workflow → experiment → review │
└────────────────────────────────────────────────────┘
      │                   │                    │
      ▼                   ▼                    ▼
PEIT source       external WORK_PATH      doc/reports
and tests         waveforms/catalogs      approved writing
```

The arrows mean documented references, not automatic data movement. An output
file is not scientifically approved merely because it exists.

## Directory guide

| Directory | Role | Examples |
|---|---|---|
| `00_governance/` | boundaries and decisions | scope, decisions, questions |
| `01_context/` | curated project knowledge | glossary, pipeline map |
| `02_prompts/` | reusable instructions | code review, catalog QA |
| `03_workflows/` | repeatable procedures | experiment lifecycle |
| `04_experiments/` | run records | dated Markdown records |
| `05_evaluations/` | quality control | rubric and test cases |
| `06_outputs/` | human-review queue | drafts and approved summaries |
| `07_archive/` | superseded material | old versions with reasons |
| `config/` | safe configuration | schemas and path conventions |
| `scripts/` | deterministic helpers | initialization and validation |
| `templates/` | copyable records | experiment and decision templates |

Architecture Decisions Records (ADRs) are managed under `../doc/adr/`. The
production-ready template is [`../config/adr_schema.md`](../config/adr_schema.md).
Use the `scripts/handler.sh` script to initialize the directory, create a
numbered ADR, or rebuild its index:

```bash
bash LLM/scripts/handler.sh adr init
bash LLM/scripts/handler.sh adr new "Choose a versioned audit format"
bash LLM/scripts/handler.sh adr update
```

`adr new` creates a zero-padded file such as
`doc/adr/0001-choose-a-versioned-audit-format.md`, pre-fills the date and Git
author, and preserves the template's security, trade-off, rollout, and
operational-readiness sections. Existing ADR files and index prose are not
overwritten.

## Suggested lifecycle

```text
question → scope/data check → context snapshot → prompt version
    → bounded run → format validation → scientific evaluation
    → human decision → approved output OR revised/archived version
```

## First use

```bash
cd PEIT
bash LLM/scripts/handler.sh init
bash LLM/scripts/handler.sh validate
```

`handler.sh init` is idempotent: it creates missing LLM directories and
starter files but never overwrites existing files. `navigate` writes its
inventory only to standard output; `validate` checks the fixed documentation
scaffold and handler entry point without modifying files. Neither command
validates links, source-code claims, Makefile targets, or Python dependencies.
The `adr` command is a separate documentation workflow and writes only under
`doc/adr/`; run `adr update` after manually adding or editing an ADR.

## Example

```text
Question: Can an LLM classify parser failures from existing error messages?
Context: 01_context/pipeline_map.md plus source commit abc123
Prompt: 02_prompts/code_review.md, version 0.1
Input: redacted examples only; no credentials or raw waveform data
Output: structured labels plus uncertainty
Decision: human reviewer accepts labels for triage only; no automatic fixes
```

Read `00_governance/open_questions.md` before connecting this workspace to a
provider, production catalog, or automated cluster workflow.

## Evidence boundary

The LLM workspace describes how to inspect and review the project; it is not a
scientific source of truth. Executable behavior is defined by the current
Makefile, Python source, tests, and configuration under `src/` and `config/`. Narrative reports under `doc/` are
useful context but must be checked against
their underlying sources before being treated as results.
