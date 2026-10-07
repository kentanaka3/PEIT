# PEIT Documentation Map & Information Architecture

Welcome to the documentation for the **Personal Economic Inflation Tracker (PEIT)**.
This index is the authoritative navigation hub for human engineers, researchers, and autonomous coding agents.

---

## 1. Directory Structure

```text
doc/
├── README.md                               # This documentation hub
│
├── architecture/                           # High-level architecture & system design
│   ├── ssot_resilience.md                  # SSOT, redundancy, failover, diversity, and fault isolation
│   └── mobile_hybrid.md                    # Hybrid mobile client architecture & LAN sync
│
├── subsystems/                             # Subsystem guides, operational manuals & data contracts
│   ├── schema.md                           # Canonical SSOT schema, 25 columns, 29 ledger projection, enums & hash
│   ├── ledger.md                           # Signed dual-persistence storage engine (JSONL + SQLite)
│   ├── dashboard.md                        # Interactive 3-tab visualizer & on-demand reports
│   ├── profiler.md                         # Synthetic consumer profiler & market simulation engine
│   ├── ocr.md                              # Multilingual OCR pipeline & spatial clustering parser
│   └── mobile.md                           # Flutter client manual, capture initiation & review workflows
│
├── specs/                                  # Formal specifications, RFCs, and decision records
│   └── RFC-001_personal_welfare_metrics.md # Specification for personal welfare & inflation metric algorithms
│
├── showcase/                               # Academic showcase, conference drafts, and slides
│   ├── peit.tex                            # LaTeX conference paper / demonstrator source
│   ├── peit.pdf                            # Compiled conference paper
│   └── Presentation2.pptx                  # Showcase slide deck
│
└── archive/                                # Non-normative historical plans & completed milestones
    ├── PLAN_v1_milestone.md                # Completed Phase 1-4 milestone tracking
    ├── PLAN_UI_CARD_STREAM.md              # Implemented mobile card stream UI design plan
    └── PLAN_UI_INLINE_DATA_GRID.md         # Implemented mobile data grid UI design plan
```

---

## 2. Navigation Index by Topic

### 2.1 System Architecture
- **[SSOT & Distributed Resilience](architecture/ssot_resilience.md)**: Details the Single Source of Truth paradigm across Python (`src/peit/schema.py`) and Flutter (`mobile/lib/data/schema_constants.dart`), dual persistence (`.jsonl` + `.db`), and fault isolation.
- **[Mobile Hybrid Client Architecture](architecture/mobile_hybrid.md)**: Explains the dual review UX (Card Stream for phones, Inline Data Grid for tablets/power users), Drift SQLite local storage, and Zeroconf LAN synchronization.

### 2.2 Subsystem Manuals
- **[Canonical Schema Guide](subsystems/schema.md)**: Definitive data dictionary, column ordering, rating bounds ($1.0 - 5.0$), domain enums (`EventType`, `Availability`, `QualityTier`), deterministic SHA-256 identity hashing (`compute_entry_id` with negative-zero safeguard), and signed cash-flow normalizers.
- **[Ledger Storage Engine](subsystems/ledger.md)**: Reference manual for append-only JSON Lines logs, self-healing SQLite caches, atomic query methods, financial balances, and command-line usage.
- **[Dashboard Visualizer](subsystems/dashboard.md)**: Design of the 3-tab HTML visualizer (Cash Flow, Inflation & Welfare, Transaction Ledger) with embedded Chart.js.
- **[Consumer Profiler & Synthetic Data](subsystems/profiler.md)**: Stochastic consumer behavior (`Profile`) coupled with market price dynamics (`Market`) producing reproducible benchmark datasets.
- **[OCR & Computer Vision Pipeline](subsystems/ocr.md)**: Optical character recognition, bounding box geometry, spatial baseline clustering, tax keyword matching, and econometric evaluation benchmarks.
- **[Mobile Client Guide](subsystems/mobile.md)**: On-device review workflows, capture initiation modes, manual entry, and photo privacy policies.

### 2.3 Specifications & Decisions
- **[RFC-001: Personal Welfare & Inflation Metrics](specs/RFC-001_personal_welfare_metrics.md)**: Formal RFC specifying future decomposition metrics (Bennett indicators, Apparent Disposable Income gap, and substitution curves).

### 2.4 Academic & Demonstrations
- **[PEIT Showcase Document (`peit.tex`)](showcase/peit.tex)**: Academic paper summarizing the system, data provenance, and empirical evaluation.

---

## 3. Rules for Autonomous Agents

When navigating or citing documentation:
1. **Normative Ground Truth**: Code in `src/peit/` and `mobile/lib/` is authoritative. When documentation disagrees with executable code, consult `src/peit/schema.py` and notify the team.
2. **Repository-Relative Paths**: Always link documentation using repository-relative Markdown paths (e.g., `doc/subsystems/ledger.md`).
3. **No Phantom Modules**:
   - `src/peit/core.py` and `src/peit/dashboard.py` implement active price indices and cash flows.
   - Do not reference `src/peit/metrics.py` (it is an unreleased RFC in `doc/specs/RFC-001_personal_welfare_metrics.md`).
   - Do not reference `util/generate_dataset.py` (it was replaced by `src/peit/profiler/`).
4. **Validation Baseline**: Always verify documentation and implementation changes with:
   ```bash
   bash -n test/run_tests.sh
   python util/generate_mobile_schema.py --check
   bash test/run_tests.sh --all
   git diff --check
   ```

