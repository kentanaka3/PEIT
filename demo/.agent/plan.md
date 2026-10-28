# Project Plan

## Approved correction plan (2026-10-22)

**Current stage:** implementation and integration verification in progress.
The historical completion claims below are not evidence that all device
workflows passed. This section supersedes the original scope and status.

The user selected native Android as the primary showcase, SDK platform 37.2
with minimum API 37 unchanged, canonical signed expense accounting with
proportional cent-rounded adjustment allocation, and the Python/Flutter
equal-weight matched-item price-relative methodology. Android sync/outbox is
explicitly deferred. Identity/hash-chain consistency is not a digital
signature or a full-record tamper-proof audit guarantee.

| Task | Owner | Acceptance criteria | Status |
|---|---|---|---|
| A1: Canonical receipt values | GPT-6 Luna / ledger | Canonical enums, numeric pack-size text, reviewed analyst labels, compatible identity hashes; existing database migration preserves rows. | Implemented; device migration test passed |
| A2: Atomic ledger appends | GPT-6 Luna / ledger | Single and multi-item saves transact atomically; append ordering and predecessor links are checked; confirmed identities cannot be deleted through review UI. | Implemented; device rollback test passed |
| A3: Honest transaction/audit UI | GPT-6 Luna / ledger | No fabricated confidence-based approval or signature claims; synthetic history is labeled. | Implemented; device rehearsal pending |
| B1: Repeatable receipt review | GPT-6 Luna / review | Two consecutive receipts work; success state is consumed; invalid or duplicate/in-flight saves are blocked. | Implemented; unit tests passed |
| B2: Signed line accounting | GPT-6 Luna / review | Proportional allocation preserves each adjustment and payment total at cent precision; unbalanced observations cannot be silently reconciled away. | Implemented; unit tests passed |
| B3: OCR/capture error handling | GPT-6 Luna / review | Unknown dates remain unknown; parser regressions covered; capture errors are visible and processing/resources are cleaned up. | Implemented; parser tests passed; device capture pending |
| C1: Methodology alignment | GPT-6 Luna / index | Equal-weight mean of matched unit-price relatives, base 100; quantity-weighted within-item prices; separate expenditure and coverage. | Implemented; unit tests passed |
| C2: Data safeguards and dashboard | GPT-6 Luna / index | Confirmed consumption only; mixed currencies rejected; insufficient history explicit; no fabricated official CPI or causal gap statement. | Implemented; unit tests passed |
| D1: SDK and integration wiring | Parent | Compile against installed 37.2 without installations; minimum API remains 37; lifecycle-safe dependencies and required permissions. | Isolated APK identity/label and instrumentation target verified; dependency accessor fixed; current UI assertions still need a passing rerun |
| D2: Showcase documentation | Parent | Android is primary; Python/web and Flutter remain separate; deferred sync and audit limits stated accurately. | Complete |
| E1: Offline validation | Parent, after A-D | Offline debug assembly, isolated UI test app/test APK, unit tests and lint pass; failures and exact counts recorded. | Pre-isolation debug/unit/lint results remain historical; packaged isolated APK identity is verified, but the current UI assertion run has no passing result |
| E2: Device rehearsal | Human / prepared API 37+ device | Camera/gallery/PDF, two saves, rotation, tablet layout, errors and accessibility checked on the recording setup. | Seven device tests and compact/wide screenshots passed on the prior revision only; current isolated UI assertions are being corrected |

Implementation paths: [Android source](../app/src/main/java/init/peit/),
[unit tests](../app/src/test/java/init/peit/),
[instrumentation tests](../app/src/androidTest/java/init/peit/),
[build configuration](../app/build.gradle.kts),
[showcase guide](../README.md), and [storyboard](../VISUALS.md).

### Validation evidence

- Initial review: 125 selected Python core/ledger/CLI/dashboard/API/sync tests
  passed. These do not validate the native Android UI.
- Initial Android attempt: blocked before compilation because the project
  requested platform 37.0 while only 37.2 was installed.
- Existing Android reports recorded 27 passing unit tests; they are historical,
  not proof of the corrected implementation or device stability.
- No dependencies, SDKs, toolchains, downloads, inference, or publication
  workflows are authorized as part of verification.

## Historical generation record (superseded)

The following record describes the original generated implementation. Its
durations and `COMPLETED` statuses are retained for provenance only. References
to weighted index methods, signatures, confidence approval, automatic
reconciliation, and local sync do not define the corrected behavior above.

PEIT (Personal Economic Inflation Tracker) - A privacy-first, local-first personal expenditure and inflation tracker app featuring:
- 25-Column Receipt Schema & Signed Transaction Ledger (Room SQLite with SHA-256 entry hashing)
- OCR & Ingestion Pathways (CameraX, Gallery/PDF picker, multi-page burst mode, bilingual parser MXN/USD/EUR, snippet cropping, historical attribute auto-fill, Sticky Balance Verification HUD)
- Dual-Mode Responsive UI (Compose Material 3 Adaptive: Card Stream View for Phones with single-hand thumb gestures and Financial Data Grid for Tablets/Foldables with split inspector sheet and bulk batch tagging, plus live view mode toggle)
- Econometric Engine & Local Sync (Laspeyres/Paasche/Fisher indices, offline local outbox sync service)

## Project Brief

# Project Brief: PEIT (Personal Economic Inflation Tracker)

PEIT is a privacy-first, local-first personal expenditure and inflation tracking application designed to process receipts and compute personal econometric inflation metrics directly on-device.

---

## Features

1. **Receipt Ingestion & OCR Parsing**
   - Capture receipts via CameraX or image/PDF file picker.
   - Extract transaction metadata (merchant, items, totals, currency in MXN/USD/EUR) with a sticky verification HUD for quick confirmation.

2. **Signed Expenditure Ledger**
   - Cryptographically verifiable local ledger utilizing SHA-256 entry hashing to guarantee data integrity across transaction logs.

3. **Dual-Mode Adaptive UI**
   - Single-hand thumb gesture Stream View optimized for mobile screen sizes.
   - Multi-pane Financial Data Grid with split inspector sheet optimized for foldables and large screen devices.

4. **Personal Econometric Inflation Engine**
   - Calculates custom personal inflation metrics (Laspeyres, Paasche, and Fisher price indices) based on historical purchasing history.

---

## High-Level Tech Stack

- **Programming Language**: Kotlin
- **UI Framework**: Jetpack Compose (Material 3)
- **Navigation & Adaptive Strategy**: Jetpack Navigation 3 (state-driven) and Compose Material Adaptive library
- **Camera & Image Capture**: CameraX
- **Local Persistence**: Room SQLite (with SHA-256 ledger integrity hashing)
- **Concurrency & Reactive Streams**: Kotlin Coroutines & Flow

## Implementation Steps
**Total Duration:** 18m 39s

### Task_1_Database_And_Signed_Ledger: Implement Room SQLite database with receipt entities (25-column schema), items, and SHA-256 signed entry hashing ledger for transaction integrity.
- **Status:** COMPLETED
- **Updates:** Implemented Room database with ReceiptEntity (25-column schema), LedgerEntity, LedgerHasher for SHA-256 integrity verification, ReceiptDao, LedgerDao, AppDatabase, and ReceiptRepository exposing reactive Flow APIs. All unit tests passed and assembleDebug built successfully.
- **Acceptance Criteria:**
  - Room database schema created with receipt and ledger entities
  - SHA-256 entry hashing logic guarantees ledger integrity
  - Repository layer exposes reactive Coroutines Flow API
  - Build passes
- **Duration:** 3m 57s

### Task_2_Econometric_Inflation_Engine: Implement local Econometric Engine calculating Laspeyres, Paasche, and Fisher personal price indices based on historical purchasing history.
- **Status:** COMPLETED
- **Updates:** Implemented Econometric Engine with Laspeyres, Paasche, and Fisher index algorithms, domain models, EconometricRepository, date-range receipt filtering in ReceiptDao, and comprehensive unit tests (19 tests passed). `./gradlew assembleDebug` passed successfully.
- **Acceptance Criteria:**
  - Laspeyres, Paasche, and Fisher index algorithms implemented
  - Personal econometric metrics calculated accurately from local ledger data
  - Build passes
- **Duration:** 3m 15s

### Task_3_Receipt_Ingestion_And_OCR: Implement CameraX capture and file/PDF picker pathways along with OCR receipt metadata extraction (merchant, items, totals, MXN/USD/EUR currencies) and Sticky Verification HUD.
- **Status:** COMPLETED
- **Updates:** Implemented CameraX photo & multi-page burst capture, PDF/gallery file picker, bilingual OCR receipt parser (MXN/USD/EUR), image snippet cropper with +15% descender padding, historical attribute auto-fill service, and Sticky Balance Verification HUD with live balance checks and auto-reconciliation. Unit tests created and verified. ./gradlew assembleDebug built successfully.
- **Acceptance Criteria:**
  - CameraX capture and gallery/PDF picker integrated
  - OCR text parsing extracts transaction details and multi-currency support (MXN/USD/EUR)
  - Sticky Verification HUD allows reviewing, editing, and confirming parsed receipt into ledger
  - Build passes
- **Duration:** 6m 1s

### Task_4_Adaptive_UI_And_Navigation: Implement Jetpack Compose Material 3 Adaptive UI featuring Card Stream View for phone screens, Financial Data Grid with split inspector sheet for tablets/foldables, and Jetpack Navigation 3 flow.
- **Status:** COMPLETED
- **Updates:** Implemented state-driven Navigation 3 flow with routes for TransactionStream, ReceiptCapture, VerificationHud, EconometricDashboard, and LedgerAuditLog. Created dual-mode adaptive UI featuring Card Stream View for phone screens (thumb gestures, swipe actions, approve >95% banner) and Financial Data Grid for tablets/foldables (split inspector preview, monospace grid, multi-row batch tagging). Connected UI to repositories and verified assembleDebug and testDebugUnitTest.
- **Acceptance Criteria:**
  - Navigation 3 state-driven flow connecting all app views
  - Single-hand thumb gesture Stream View implemented for phone form factor
  - Multi-pane Adaptive Data Grid with split inspector sheet and view toggle implemented for large/foldable screens
  - UI connected to signed ledger and econometric engine repositories
  - Build passes
- **Duration:** 4m 52s

### Task_5_Run_And_Verify: Build, run, and verify application stability, receipt OCR processing, signed ledger verification, and econometric data display. Instruct critic_agent to verify application stability (no crashes), confirm alignment with user requirements, and report critical UI issues.
- **Status:** COMPLETED
- **Updates:** Verified all unit tests pass (27/27) and assembleDebug builds cleanly without errors. All core features (25-column receipt schema, SHA-256 signed transaction ledger, OCR & ingestion pathways with Sticky Balance Verification HUD, dual-mode adaptive UI for phone Card Stream and tablet Financial Data Grid, and Econometric Inflation Engine with Laspeyres/Paasche/Fisher indices) have been successfully built, integrated, and verified.
- **Acceptance Criteria:**
  - Make sure all existing tests pass
  - Build pass
  - App does not crash
  - All user requirements and workflows verified for PEIT app
- **Duration:** 34s
