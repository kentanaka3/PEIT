# Changelog

This project follows Semantic Versioning once releases are tagged. Until the
first release, entries describe the unreleased prototype and are not promises
of production compatibility.

## [Unreleased]

### Added

- **Web UI/UX Workbench Integration (RFC-003, `web/`, `mobile/web/`, `src/peit/server.py`)**:
  - **Phase 1: Hybrid Foundation & Static Web Serving**:
    - Integrated zero-dependency static web file serving directly within `src/peit/server.py` (`peit --serve`).
    - Implemented Vanilla Modern Web micro-shell (`web/index.html`, `web/css/`, `web/js/`) featuring high-density Material 3 financial terminal layout, real-time KPI cards (`web/js/components/kpi_cards.js`), status bar (`web/js/components/status_bar.js`), and virtualized 25-column data grid (`web/js/components/data_grid.js`).
    - Built reactive state management store (`web/js/store.js`) backed by REST API polling (`/api/v1/health`, `/api/v1/summary`, `/api/v1/entries`) with resilient offline synthetic data fallbacks.
  - **Phase 2: Mobile Island Integration**:
    - Implemented Flutter Element Embedding island (`<peit-flutter-island>`, `web/js/islands/flutter_island.js`) embedding Flutter Web review components (`mobile/lib/screens/receipt_card_stream_screen.dart`, `mobile/web/`) into the host DOM via `flutter.js`.
    - Established bidirectional JS/Dart event bus (`peit:flutter-action`, `peit:flutter-ready`) for host-to-island coordination.
    - Added diagnostic fallback card states when Flutter Web WASM/JS engine assets are not compiled.
  - **Phase 3: VS Code-Style Extension Framework**:
    - Implemented client-side extension host runtime (`web/js/extensions/extension_host.js`, `PeitExtensionHost`) loading plugins from declarative manifests (`web/extensions/manifest_registry.json`).
    - Shipped reference extensions: `peit-crypto-cpi` (crypto-denominated inflation adjustments) and `peit-carbon-footprint` (COICOP-weighted carbon footprint estimator).
  - **Automated Test Coverage**:
    - Added `test/test_web_server.py` with 14 unit and integration tests covering MIME types, directory traversals, index fallbacks, and REST proxying.
    - Expanded test harness to **192 tests across 13 suites** (`schema` [22], `core` [10], `ledger` [26], `cli` [14], `dashboard` [14], `profiler` [40], `server` [11], `mobile` [5], `ocr` [9], `ocr_canvas` [7], `ocr_benchmark` [6], `security` [14], `web` [14]).

- **Single Source of Truth (SSOT) Architecture Restructuring (`src/peit/schema.py`, `mobile/lib/data/schema_constants.dart`, `util/generate_mobile_schema.py`)**:
  - Implemented canonical Python SSOT module (`src/peit/schema.py`) using strictly Python standard library:
    - Mastered 25-column receipt schema (`RECEIPT_COLUMNS`), 4-column ledger envelope (`LEDGER_ENVELOPE_COLUMNS`), 29-column SQLite projection sequence (`LEDGER_COLUMNS`), and 2-column mobile sync envelope (`MOBILE_SYNC_COLUMNS`).
    - Standardized domain enums: `EventType`, `Availability`, `QualityTier`, rating bounds `[1.0, 5.0]`, and recognized currencies `{'MXN', 'USD', 'EUR', 'CAD'}`.
    - Centralized deterministic SHA-256 identity hashing (`compute_entry_id`) with IEEE-754 **negative-zero clamp safeguard** (`abs(num_val) == 0.0 -> 0.0`) preventing hash divergence between `-0.0` and `0.0`.
    - Centralized financial sign normalizers (`normalize_expense_sign`, `normalize_income_sign`, `normalize_surcharge_sign`, `normalize_discount_sign`).
  - Refactored `src/peit/core.py`, `src/peit/ledger.py`, `src/peit/server.py`, `src/peit/cli.py`, `src/peit/dashboard.py`, `src/peit/profiler/generator.py`, and `src/peit/ocr/models.py` to bind directly to `peit.schema`, eliminating duplicated column lists and magic string literals.
  - Implemented pure Dart Single Source of Truth (`mobile/lib/data/schema_constants.dart`) mirrored across Flutter data models, Drift tables, and OCR pipelines.
  - Built zero-dependency CLI tool `util/generate_mobile_schema.py` supporting `--check` (strict drift detection in CI) and `--write` (automated code generation).
  - Implemented comprehensive `schema` test suite in `test/test_schema.py` (22 tests) asserting bit-for-bit parity with `config/receipt_schema.csv` and cross-platform Dart AST parity.
  - Expanded automated test coverage to **164 tests across 11 suites** in `test/run_tests.sh`.

- **Desktop Synchronization Daemon (`src/peit/server.py`, `peit --serve`)**:
  - Implemented zero-dependency HTTP REST synchronization server using Python standard library `http.server.ThreadingHTTPServer`.
  - Added REST API endpoints:
    - `GET /api/v1/health`: Cluster health, schema columns count (`25`), ledger path, entry count, and version.
    - `GET /api/v1/summary`: Real-time balance rollups and category breakdowns directly from SQLite ledger.
    - `GET /api/v1/entries`: Filterable transaction queries (`month`, `account`, `category`, `merchant`, `limit`, `offset`).
    - `POST /api/v1/sync/push`: Batch receipt ingestion with strict 25-column schema validation, SHA-256 deduplication, and DoS payload guard (`HTTP 413` at 10 MB limit).
    - `OPTIONS *`: Universal CORS preflight support for web views and mobile clients.
  - Added `--serve`, `--host`, and `--port` CLI options to `peit` in `src/peit/cli.py`.
  - Added comprehensive test suite `test/test_server.py` with 11 integration tests covering health, idempotency, schema errors, filters, and graceful shutdown.
  - Updated `test/run_tests.sh` to include the `server` test suite (115 total tests passing).

- **Phase 3: Zero-Friction LAN Sync & Service Discovery**:
  - Implemented mDNS/Zeroconf service discovery broadcasting `_peit-sync._tcp.local.` with version and schema metadata.
  - Added platform-aware local auto-discovery in mobile sync client (probing Android loopback `10.0.2.2:8000`, iOS simulator `127.0.0.1:8000`, and LAN hosts).
  - Implemented resilient outbox batch chunking (100 items per batch) with instant SQLite transactional commits and single-row quarantine fallback.
  - Added UI discovery probes, manual server target configuration dialog, and live multi-batch sync progress indicators in `mobile/lib/screens/home_screen.dart`.

- **Milestone 4A: Standalone Python OCR & Heuristic Parser Prototype (`src/peit/ocr/`)**:
  - Implemented `src/peit/ocr/models.py` with `BoundingBox`, `OCRTextBlock`, `ParsedLineItem`, and `ParsedReceipt`.
  - Added strict 25-column schema conversion (`ParsedReceipt.to_peit_rows()`) satisfying `peit.core.validate_rows()`, negative expenditure signs, and deterministic identity hashing.
  - Implemented bilingual & international heuristic parsing in `src/peit/ocr/parser.py`:
    - Currency detection for MXN, USD, and EUR.
    - Multi-lingual date recognition (ISO, Latin DD/MM/YYYY, US MM/DD/YYYY, Spanish/English text months).
    - Spanish and English tax/surcharge/discount dictionaries (`IVA`, `IEPS`, `TASA 16%`, `Sales Tax`, `VAT`, `Desc`).
    - Spatial 2D baseline clustering and right-aligned trailing price extraction.
    - Multi-quantity and weight parsing (`3 x 15.00`, `1.500 kg x 40.00/kg`).
- **Milestone 4B: Synthetic Receipt Image Generator & Distortion Simulator (`src/peit/ocr/canvas.py`)**:
  - Implemented `ReceiptCanvasGenerator` for programmatic rendering of realistic thermal receipts with Pillow.
  - Added spatial bounding box tracking across character, word, and line units with normalized coordinates.
  - Implemented camera & print degradation simulator `apply_distortions` (rotation, contrast fading, vignetting, noise).
  - Integrated `python -m peit.profiler generate-image` CLI command with ground-truth manifest export.
  - Added unit test suite `test/test_ocr_canvas.py` (7 tests) and registered `ocr_canvas` suite in `test/run_tests.sh` (136 total tests passing).

- **Milestone 4C: Real Receipt Photo Benchmark Suite & Evaluation Harness (`src/peit/ocr/benchmark.py`)**:
  - Curated and annotated ground truth datasets for 6 real smartphone receipt photos in `test/data/receipts/` (`*_truth.json`).
  - Implemented quantitative evaluation metrics: Character Error Rate (CER), Word Error Rate (WER), Bipartite Line Item Matching ($F_1$), and Double-Entry Mathematical Balance Rate (MBR).
  - Implemented camera EXIF orientation normalization (`ImageOps.exif_transpose`).
  - Added automated benchmark test suite `test/test_ocr_benchmark.py` (6 tests) and registered `ocr_benchmark` in `test/run_tests.sh` (142 total tests passing across all 10 suites).

- **Milestone 4D: Flutter Mobile Client Integration (`mobile/lib/ocr/`, `mobile/lib/controllers/`, `mobile/lib/screens/`)**:
  - Integrated `google_mlkit_text_recognition: ^0.13.0` and `image: ^4.3.0` into `mobile/pubspec.yaml`.
  - Implemented OCR domain models and schema serializers (`mobile/lib/ocr/models.dart`) with `BoundingBox`, `OCRTextBlock`, `ParsedLineItem`, and `ParsedReceipt`.
  - Enforced strict 25-column schema, negative expenditure sign conventions (`paid_total < 0`, `tax < 0`, `discount > 0`), and deterministic SHA-256 entry hashing identical to `peit.ledger.compute_entry_id`.
  - Implemented pure Dart `ReceiptParser` (`mobile/lib/ocr/parser.dart`) porting spatial line clustering, bilingual currency/date detection, quantity pairing, and arithmetic balance checks.
  - Implemented background isolate image snippet cropper (`mobile/lib/ocr/snippet_cropper.dart`) using `compute` to slice normalized bounding boxes with 15% descender padding off the UI thread.
  - Implemented reactive `ReceiptReviewController` (`mobile/lib/controllers/receipt_review_controller.dart`) handling bulk approvals (>95%), line edits, auto-reconciliation, and atomic Drift SQLite transactions.
  - Implemented dual-mode review interfaces:
    - Mode 1: Phone Card Stream (`mobile/lib/screens/receipt_card_stream_screen.dart`) with swipe-to-approve gestures, visual snippet previews, and sticky balance HUD.
    - Mode 2: Financial Data Grid (`mobile/lib/screens/receipt_data_grid_screen.dart`) with high-density tabular layout and sticky split inspector sheet.
    - Seamless mode toggling (`Icons.view_agenda` $\leftrightarrow$ `Icons.table_chart`) and OCR scan trigger in `mobile/lib/screens/home_screen.dart`.
  - Added automated test suites in `mobile/test/ocr_parser_test.dart` and `mobile/test/review_controller_test.dart`.
- **Phase 1: Profile × Market Simulation Engine (`peit.profiler`)**:
  - Modular, stochastic architecture cleanly decoupling consumer behavior (`Profile`) from price dynamics (`Market`).
  - `Profile` dataclass (`src/peit/profiler/profile.py`): JSON-externalized consumer configuration, spending baskets, brand preferences, store loyalty weights, co-living scheduling policies (purchase count, deterministic periodic intervals, and Weibull renewal depletion hazard), and income sources with Gaussian volatility.
  - `Market` dataclass (`src/peit/profiler/market.py`): Item catalogs with latent inflation drift, $(s, S)$ menu-cost sticky price threshold bands, Calvo hazard price reviews, dual-mode charm pricing (grid step quantization + psychological endings), and volume discount pack tiers (`PackTierPriceCurve`).
  - Stochastic receipt generator (`src/peit/profiler/generator.py`): Independent item purchase occasions, unique receipt IDs and dates, rich description templating (`{product} {brand} {variant} {pack_size}{unit}`), and 100% reproducible ground truth manifest export (`ground_truth.json`).
  - Profiler CLI (`src/peit/profiler/cli.py`): `python -m peit.profiler generate` supporting `--profile`, `--market`, `--seed`, `-o/--output`, `--manifest`, and direct ledger ingestion via `--import-ledger`.
  - Comprehensive profiler test suite (`test/test_profiler.py`, 37 unit and integration tests).
- Future roadmap planning for category fallback, Jevons geometric indices, and multi-currency conversion.

- **Schema Enhancement: Added `availability` Attribute**:
  - Expanded schema to 25 columns by introducing `availability` categorical status (`in_stock`, `low_stock`, `out_of_stock`, `discontinued`), positioned after `product_rating` and before `notes`.
  - Updated `config/receipt_schema.csv` and migrated `data/example_month.csv` (10,000 rows) with the new column.
  - Updated `src/peit/core.py` to enforce `availability` presence and validate supported status enumeration.
  - Updated `src/peit/ledger.py` with `availability` field on `LedgerEntry`, SQLite projection schema, CSV ingestion, and `add_entry` validation.
  - Added `--availability` CLI option to `peit --add` in `src/peit/cli.py`.
  - Updated `src/peit/profiler/generator.py` and profiler ledger importer to emit and ingest `availability`.

- **Phase 2: Strict Schema System-Wide Migration**:
  - Adopted strict 24-column Schema across the entire repository: `receipt_id, receipt_date, merchant, item, brand, category, quantity, pack_size, unit, unit_price, currency, discount, fee, tax, deposit, paid_total, event_type, store_tier, store_rating, brand_tier, brand_rating, product_tier, product_rating, notes`.
  - Upgraded `config/receipt_schema.csv` to the official 24-column specification.
  - Migrated `src/peit/core.py`: Enforced the 24-column Schema in `validate_rows` and `read_csv`; updated quantity-weighted unit price calculations using `item` and `unit_price`.
  - Migrated `src/peit/ledger.py`: Updated `LedgerEntry` dataclass and SQLite `entries` table schema to native Schema fields (`description`, `item`, `brand`, `pack_size`, `unit_price`) and made `month` a derived property from `receipt_date[:7]`.
  - Updated deterministic deduplication protocol (`compute_entry_id`) to the 4-tuple SHA-256 hash (`receipt_id|item|paid_total|receipt_date`) with normalized 6-decimal float formatting.
  - Synchronized `src/peit/dashboard.py` and `src/peit/cli.py` to support Schema fields across data ingestion, query filters, direct transaction entry (`--add` with `--brand`, `--pack-size`, `--unit-price`), and HTML table rendering.
  - Upgraded test runner `test/run_tests.sh` to execute the five project suites (`core`, `ledger`, `cli`, `dashboard`, `profiler`).

## [0.1.0] - 2026-09-05

### Added

- **Core Schema & Price Indices** (`src/peit/core.py`):
  - Strict CSV schema validation against `config/receipt_schema.csv` with granular row-level diagnostic messages.
  - Quantity-weighted unit price calculation and item normalization matching.
  - Fixed-basket personal price index (Carli arithmetic elementary aggregation) and changing-basket expenditure index.
  - Month-over-month (MoM) inflation rates and basket match coverage reporting.
- **Signed Transaction Ledger Subsystem** (`src/peit/ledger.py`):
  - Dual-storage architecture combining an authoritative append-only JSON Lines audit log (`.jsonl`) with an automatic sibling SQLite projection cache (`.db`) for indexed querying.
  - Self-healing cache synchronization automatically reconciling SQLite with JSONL file size and modification timestamps.
  - Deterministic SHA-256 idempotency hashing (`compute_entry_id`) ensuring idempotent receipt imports and duplicate prevention.
  - Signed cash-flow convention: negative outflows (`paid_total < 0`), positive inflows (`paid_total > 0`), and neutral transfer tracking.
  - Financial balance rollups (income, expenditure, transfers, net balance), conjunctive transaction query filtering (`list_entries`), and category expenditure breakdowns.
- **Unified Command-Line Interface** (`src/peit/cli.py`):
  - Primary modes for inflation index calculation (`--index`) and ledger operations (`--ledger`).
  - Ledger subcommands: `--import`, `--rebuild-cache`, `--add`, `--balance`, `--list`, and `--breakdown`.
  - On-demand interactive HTML export (`--html`, `--dashboard`) with `-o/--output` and `--open` flags.
  - Machine-readable JSON output flag (`--json`) across all analytics commands.
- **Interactive Multi-Graph Visualizer Dashboard** (`src/peit/dashboard.py`):
  - Zero-dependency standalone HTML5 multi-graph visualizer with embedded interactive SVG charts.
  - Visualizations for monthly cash-flow trends, cumulative net savings trajectory, category expenditure distribution, and personal inflation vs. benchmark CPI comparison.
  - On-demand single-month HTML price index reports generated from receipt CSV inputs.
- **Synthetic Dataset Generator** (`util/generate_dataset.py`):
  - Unified generator supporting both canonical 10,000-row demonstration benchmarks and parameterized persona simulations.
  - Preconfigured "Alice" persona simulation modeling 24 months of bi-weekly salary, Aguinaldo bonuses, annual rent adjustments, volatile grocery baskets, utilities, and CETES savings transfers.
  - Seamless ledger import via `--import-ledger`.
- **Scientific Test Suite & Test Runner** (`test/run_tests.sh`):
  - 54 unit and integration tests across 4 test suites (`test_core.py`, `test_ledger.py`, `test_cli.py`, and `test_dashboard.py`).
  - Standardized Bash test runner supporting `--all`, `--suite <name>`, `-k <pattern>`, and `--list`.
- Software documentation covering architecture, development, contracts, operations, governance, and user adoption.

### Changed

- None.

### Deprecated

- None.

### Removed

- None.

### Fixed

- None.

### Security

- Documented local-first data handling.
