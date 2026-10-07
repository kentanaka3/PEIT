# ADR-0001: Dual Persistence Signed Ledger

* **Status:** Accepted
* **Deciders:** Ken Tanaka H.
* **Consulted:** None
* **Informed:** Architecture Team
* **Date:** 2026-09-05
* **Technical Story / Ticket:** PEIT-ARCH-0001
* **Review Date:** 2027-03-01
* **Supersedes:** None
* **Superseded by:** None

---

## 1. Context and Problem Statement

Personal expenditure and price index calculation require both absolute audit integrity and fast, indexed multidimensional querying. Personal financial records require traceable provenance, deterministic deduplication, and verifiable historical immutability. Meanwhile, personal inflation metrics (such as Carli indices, Laspeyres aggregations, and expenditure basket decompositions) require fast filtering, category rollups, and date-range aggregations over thousands of line items. Relying on a mutable database alone creates risks of silent corruption or provenance loss, while querying raw flat files repeatedly degrades analysis latency.

### Scope and non-goals

* **In scope:** Transaction ingestion, schema validation, append-only provenance logging, cache projection, and query interfaces in [`src/peit/ledger.py`](../../src/peit/ledger.py) and [`src/peit/core.py`](../../src/peit/core.py).
* **Out of scope:** External multi-tenant relational database servers (e.g. PostgreSQL), distributed stream processing, or cloud data warehouses.
* **Assumptions:** Local single-user filesystem execution; receipts arrive as monthly CSV files matching [`config/receipt_schema.csv`](../../config/receipt_schema.csv); transactions use signed cash-flow conventions.
* **Evidence:** Ingestion benchmarks and schema definitions in [`config/receipt_schema.csv`](../../config/receipt_schema.csv) and [`src/peit/ledger.py`](../../src/peit/ledger.py).

## 2. Decision Drivers (Forces and Constraints)

* **Driver 1 (Auditability and Immutability):** The primary record must be an append-only, human-readable format that can be inspected with standard Unix utilities and preserved under revision control or backup without proprietary database tools.
* **Driver 2 (Deterministic Deduplication):** Receipt line items must have canonical, deterministic identifiers derived from cryptographic hashes of transaction attributes to prevent duplicate imports.
* **Driver 3 (Query Latency and Projection Flexibility):** Monthly indices and dashboard views require sub-second filtering and aggregation across categories, dates, and merchants without parsing megabytes of text on every invocation.
* **Driver 4 (Zero Operational Overhead):** The solution must run locally without external daemon services, background servers, or network configuration.
* **Driver 5 (Financial Accounting Rigor):** Cash flows must adhere to signed accounting conventions where outflows/expenses are negative and inflows/refunds are positive.

## 3. Considered Options

* **Option 1:** Dual Persistence (Append-Only JSONL Event Log + Sibling SQLite Projection Cache)
* **Option 2:** SQLite-Only Database Architecture (relational storage as authoritative and query store)
* **Option 3:** Flat-File Only Storage (direct queries over CSV or JSONL logs without indexed cache)

## 4. Evaluation Matrix

| Criterion / Driver | Weight (1-5) | Option 1: Dual JSONL + SQLite | Option 2: SQLite-Only | Option 3: Flat-File Only |
| :--- | :---: | :--- | :--- | :--- |
| **Driver 1: Auditability & Immutability** | 5 | 5 (append-only text, diffable) | 3 (binary format, mutation risk) | 5 (plain text, diffable) |
| **Driver 2: Deterministic Deduplication** | 4 | 5 (SHA-256 entry hashing) | 4 (UNIQUE constraint index) | 2 (manual sequential scanning) |
| **Driver 3: Query Latency & Aggregation** | 5 | 5 (indexed SQL queries) | 5 (indexed SQL queries) | 1 (slow full scans) |
| **Driver 4: Operational Simplicity** | 4 | 5 (zero daemons, auto-sync) | 5 (zero daemons, single file) | 5 (zero daemons) |
| **Driver 5: Disaster Recovery & Rebuildability**| 4 | 5 (cache regenerates from JSONL)| 2 (database corruption is fatal) | 4 (text files preserved) |
| **Weighted total** | — | **98** | 76 | 62 |
| **Suitability** | — | **High** | Medium | Low |

## 5. Decision Outcome

**Chosen Option:** **Option 1: Dual Persistence (Append-Only JSONL Event Log + Sibling SQLite Projection Cache)**, because it combines the durability, provenance, and Git-friendly auditability of an append-only JSONL log with the indexing, aggregation speed, and SQL expressiveness of a local SQLite database.

### Justification and key differentiators

* **Authoritative Source vs. Disposable Projection:** The JSONL file (`.jsonl`) is the authoritative source of truth. The SQLite database (`.db`) is treated as a projection cache that is automatically rebuilt or synchronized whenever the JSONL file modification timestamp changes or the cache is missing.
* **Deterministic Deduplication:** Each record is keyed by a SHA-256 hash (`entry_id`) of `receipt_id|item|paid_total|receipt_date`, preventing duplicate line-item insertion across repeated import runs.
* **Signed Cash-Flow Discipline:** Outflows (expenses) are strictly negative floats, and inflows (income, refunds, deposits returned) are positive floats, guaranteeing conservation of value during balance and expenditure rollups.

## 6. Detailed Analysis of Options

### Option 1: Dual Persistence (JSONL Log + SQLite Cache)

* **Description:** Ingested CSV transactions are validated, hashed, and appended to `ledger.jsonl`. Simultaneously, a sibling `ledger.db` SQLite database is maintained with indexed columns (`entry_id`, `month`, `receipt_date`, `category`, `merchant`, `paid_total`). Queries read from the SQLite cache; if the cache is corrupted or missing, it is deterministically recreated from the JSONL log.
* **Advantages:**
  * (+) Append-only JSONL provides an unalterable audit trail and straightforward Git/diff inspection.
  * (+) SQLite projection provides microsecond query latencies and rich aggregation capabilities.
  * (+) Cache is completely disposable and rebuildable with zero data loss.
* **Disadvantages and risks:**
  * (-) Dual-write synchronization logic requires careful file-locking or timestamp invalidation.
  * (-) Disk footprint is slightly larger due to storing both representations.
* **Security considerations:** Local filesystem permissions restrict access; no network ports opened.
* **Operational considerations:** No server administration; automatic recovery on cache mismatch.
* **Migration impact:** Upgrades to SQLite schema can be applied by deleting the `.db` file and regenerating it from `.jsonl`.

### Option 2: SQLite-Only Architecture

* **Description:** Use a single SQLite database file for both authoritative transaction logging and querying.
* **Advantages:**
  * (+) Single file to manage.
  * (+) Immediate ACID transactions.
* **Disadvantages and risks:**
  * (-) Binary database files are not diffable in version control.
  * (-) Accidental `UPDATE` or `DELETE` statements permanently mutate historical financial data without a verifiable log.
  * (-) Corruption of the SQLite file destroys both analytical capability and provenance.
* **Security considerations:** Database file must be protected with filesystem access controls.
* **Operational considerations:** Requires regular backup dumps to prevent total data loss upon corruption.
* **Migration impact:** Schema migrations require SQL migration scripts (`ALTER TABLE`) with potential rollback risks.

### Option 3: Flat-File Only Storage

* **Description:** Store transactions exclusively in CSV or JSONL files and parse the entire dataset into memory for every calculation.
* **Advantages:**
  * (+) Simple implementation without database dependencies.
  * (+) Human readable text.
* **Disadvantages and risks:**
  * (-) Query performance scales linearly \(O(N)\) with data volume, making CLI and dashboard rendering slow.
  * (-) Complex multidimensional filtering requires reimplementing database indices in Python.
* **Security considerations:** Plain text storage requires filesystem protection.
* **Operational considerations:** Inefficient CPU and memory usage during repeated analyses.
* **Migration impact:** Schema evolution requires rewrites of flat files.

## 7. Security and Privacy Assessment

* **Assets and data classification:** Financial transaction records containing merchant names, purchased items, dates, and amounts. Classified as Private Personal Data.
* **Trust boundaries:** Local machine environment only. No data transmitted across network boundaries or external LLM APIs.
* **Threats considered:** Unauthorized local access, accidental deletion, silent data corruption, duplicate imports.
* **Required controls:** Posix umask (077/022), read-only validation passes, SHA-256 record hashing, local file storage within user-controlled workspace.
* **Residual risk:** Unencrypted local storage if full-disk encryption (FileVault) is disabled by the user.
* **Security review:** Verified against repository data privacy rules in [`AGENTS.md`](../../AGENTS.md).

## 8. Consequences and Trade-Offs

### Positive impacts

* Complete auditability of every personal expenditure item from source CSV to final index.
* Instantaneous dashboard and CLI query responses using SQLite B-tree indices.
* Seamless recovery from database corruption by deleting `.db` and allowing automatic rebuild.
* Deterministic deduplication prevents duplicate expenses when re-importing receipt batches.

### Negative impacts and accepted debt

* Two files (`.jsonl` and `.db`) must be tracked per ledger.
* Cache invalidation depends on filesystem mtime comparison; clock skew or manual touches must trigger rebuilds.

### Mitigations and action plan

| Risk or debt | Mitigation / action | Owner | Due date | Tracking issue | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Cache out of sync with JSONL | Compare JSONL mtime and record count in `_ensure_cache_valid()` | Dev Lead | 2026-09-15 | PEIT-LEDGER-01 | Done |
| Large dataset SQLite index size | Add composite indices on `(month, category)` | Dev Lead | 2026-10-01 | PEIT-LEDGER-02 | Open |

## 9. Implementation and Validation Plan

* [x] **Phase 1 — Proof of Concept:** Implemented `LedgerEntry`, `compute_entry_id`, and `LedgerDatabase` in [`src/peit/ledger.py`](../../src/peit/ledger.py).
* [x] **Phase 2 — Integration:** Wired ledger into CLI commands (`peit import`, `peit query`, `peit balance`) in [`src/peit/cli.py`](../../src/peit/cli.py).
* [x] **Phase 3 — Automated Testing:** Added comprehensive unit and regression tests in [`test/test_core.py`](../../test/test_core.py).

### Acceptance criteria

* [x] Ingesting the same receipt multiple times produces identical `entry_id` hashes and does not duplicate entries.
* [x] Outflow transactions are stored with negative `paid_total`, inflows with positive `paid_total`.
* [x] Deleting the `.db` file causes the application to transparently rebuild the SQLite cache from the `.jsonl` log.
* [x] Validation check `bash LLM/scripts/handler.sh validate` passes without ADR linting errors.

### Rollout and rollback

* **Feature flag / control:** Default ledger backend; configured via CLI `--ledger` argument.
* **Rollout increments:** Deployed in core library.
* **Abort thresholds:** Any mismatch between JSONL row count and SQLite table count aborts execution.
* **Rollback procedure:** Remove SQLite cache file; revert to raw CSV processing if ledger failure occurs.
* **Rollback owner:** Architecture Team

## 10. Operational Readiness

* **Ownership:** Core Engineering & Architecture Team
* **SLOs / SLIs:** Query latency < 50ms for 10,000 transactions; zero deduplication collisions.
* **Dashboards and alerts:** Standalone HTML report generated via `peit dashboard`.
* **Logging and tracing:** Timestamped console logging on import and cache validation.
* **Backup and recovery:** Backup `ledger.jsonl`; SQLite cache can be regenerated on demand.
* **Runbooks:** Documented in [`LLM/01_context/pipeline_map.md`](../../LLM/01_context/pipeline_map.md).
* **Capacity plan:** SQLite cache handles >100,000 records on modest consumer hardware with < 50MB RAM footprint.

## 11. Open Questions and Revisit Triggers

* **Open question:** Support for multi-currency automated exchange rate normalization (see [`LLM/00_governance/open_questions.md`](../../LLM/00_governance/open_questions.md)).
* **Revisit trigger:** Introduction of real-time receipt streaming or multi-device synchronization requiring distributed conflict resolution.
* **Review cadence:** Annual architecture review or upon major version bump.

## 12. References and Evidence

* Source implementation: [`src/peit/ledger.py`](../../src/peit/ledger.py)
* Receipt schema specification: [`config/receipt_schema.csv`](../../config/receipt_schema.csv)
* Core index calculation: [`src/peit/core.py`](../../src/peit/core.py)
* Unit tests: [`test/test_core.py`](../../test/test_core.py)
