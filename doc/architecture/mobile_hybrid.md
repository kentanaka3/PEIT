# PEIT Mobile Phase 4 Architecture: Hybrid Card Stream & Data Grid with On-Device OCR

> **Status:** Approved Architectural Specification  
> **Target Framework:** Flutter (Dart) / iOS & Android  
> **OCR Engine:** Google ML Kit Text Recognition v2 (`google_mlkit_text_recognition`)  
> **UI Paradigms:** Responsive Dual-Mode (Card Stream on Phones + Dense Financial Data Grid on Tablets/Simulators)  
> **Persistence & Sync:** Drift / SQLite with Local-First Outbox Synchronization  

---

## 1. Executive Summary & Architectural Overview

Phase 4 bridges the physical point-of-sale observation into PEIT's computational and econometric engine. It solves the tension between **mobile review speed** (one-handed thumb ergonomics) and **econometric data completeness** (strict 25-column receipt schema adherence) by introducing a **Complementary Hybrid Architecture**:

```text
[ Receipt Capture: Camera / Picker / Burst ]
                       │
                       ▼
    [ ML Kit On-Device Text Recognition v2 ]
                       │
                       ▼
        [ Heuristic Spatial Parser ]
         • Merchant & Date Extraction
         • Baseline Price Alignment
         • Running Total & Tax Detection
                       │
                       ▼
        [ Shared Core Domain State ]
         • ReceiptReviewController
         • Background SnippetCropperService (Isolate)
         • Historical Attribute Inheritance (SQLite)
         • Sticky Balance Verification HUD (Σ items - disc + tax == total)
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
[ Mode 1: Card Stream View ]   [ Mode 2: Financial Data Grid ]
 • Default on Handheld Phones   • Default on Tablets & Desktops
 • One-handed thumb swipe       • High-density 12–18 rows visible
 • Cropped image snippet card   • Monospace numeric columns
 • Quick "Approve >95%" action  • Multi-row bulk batch tagging
         └─────────────┬─────────────┘
                       │ Toggle (Icons.table_chart ↔ Icons.view_agenda)
                       ▼
        [ Atomic SQLite Commit (Drift) ] ──► "pending_sync" Outbox
```

---

## 2. Ingestion Pathways & Pre-Processing

As specified in [`doc/mobile_ui_ux_capture.md`](mobile_ui_ux_capture.md), the capture pipeline provides three unified ingestion modalities:

1. **Standard System Camera (`image_picker` / camera intent)**: Quick single-shot receipt capture utilizing native OEM camera hardware, optical image stabilization, HDR, and auto-focus.
2. **System Media & Document Picker Sheet (`file_picker`)**: For importing electronic PDF invoices, bank screenshots, and pre-existing photos. PDFs are rasterized to bitmaps at 300 DPI prior to OCR.
3. **Multi-Page Burst Mode**: Enables taking multiple consecutive photos of long supermarket slips (30–80 cm) with vertical spatial index stitching and footer deduplication.

---

## 3. Shared OCR & Domain Architecture

Both view modes operate over a single, reactive `ReceiptReviewController`:

### 3.1 Background Snippet Cropper Service (`SnippetCropperService`)
To guarantee fluid 60/120 FPS UI scrolling without jank, image cropping is offloaded to a background Dart isolate:
- Uses `compute(cropBoundingBoxes, ...)` to decode and slice bounding-box coordinates off the main UI thread.
- Applies vertical (+15%) and horizontal (+6%) safety margins to preserve character descenders (`g`, `y`, `p`, `q`).
- Compresses sliced crops to in-memory WebP buffers (<1.2 MB RAM footprint across 30 items, compared to >40 MB raw RGBA).

### 3.2 Historical Attribute Inheritance Engine
When OCR parses a merchant or line item, the engine queries the local Drift SQLite database:
- **Merchant Match**: Auto-populates `store_tier` and `store_rating`.
- **Item/Brand Match**: Auto-populates `category`, `brand_tier`, `brand_rating`, `product_tier`, `product_rating`, `unit`, and `pack_size`.
- **Availability**: Defaults to `in_stock`, with quick override chips for `low_stock`, `out_of_stock`, and `discontinued`.

### 3.3 Sticky Balance Verification HUD
Enforces the fundamental PEIT accounting invariant at the bottom of the screen:
$$\sum_{i=1}^{N} \text{total\_price}_i - \text{discount} + \text{tax} + \text{fee} + \text{deposit} = |\text{paid\_total}|$$
- **Emerald Green State**: Arithmetic balances perfectly; commit button unlocked.
- **Amber / Red Discrepancy State**: Arithmetic discrepancy detected ($\Delta \neq 0$); displays delta banner and suggests one-tap auto-reconciliation lines (e.g. bottle deposit or round-off).

---

## 4. The Complementary View Modes

Users can seamlessly switch between view modes via a top AppBar action (`Icons.view_agenda` $\longleftrightarrow$ `Icons.table_chart`). State, edits, and confirmations are synchronized in real time.

### 4.1 Mode 1: Card Stream View (Default for Mobile Phones)
- **Ergonomics**: Engineered strictly for one-handed operation within the bottom 55% thumb zone.
- **Card Layout**: Each line item is rendered as a clean card showing the cropped receipt image snippet directly above the parsed fields (`item`, `quantity`, `unit_price`, `total_price`).
- **Gesture Velocity**:
  - **Swipe Right**: Affirmative confirmation with haptic feedback; marks item verified.
  - **Swipe Left**: Discards artifact noise or merges with preceding line.
  - **Tap Card**: Slides up the full 25-column detail drawer.
  - **Tap Snippet**: Opens pinch-and-zoom lightbox overlay.
- **Bulk Action**: *"Approve All >95% Confidence"* confirms all clean lines in one tap, allowing the user to review only questionable items in ~30–45 seconds.

### 4.2 Mode 2: Financial Data Grid (Default for Tablets & Simulators)
- **Ergonomics**: Inspired by professional desktop accounting software (Excel, Bloomberg, Numbers).
- **Tabular Layout**: Displays 12–18 rows simultaneously on phones and 35+ rows on tablets with sticky headers and a sticky status column (`ST`).
- **Monospace Financial Cells**: High-contrast, right-aligned monetary values for rapid visual scanning across numbers.
- **Split Inspector Drawer**: Selecting any table cell or row instantly projects its corresponding cropped image snippet in a bottom inspector drawer with zero context switching.
- **Multi-Row Bulk Operations**: Select multiple rows to apply categories, brands, or tiers across multiple lines in a single tap.

---

## 5. Drift SQLite Persistence & Outbox Synchronization

Once the receipt balances and the user confirms:
1. All line items are committed atomically to SQLite inside a `BEGIN TRANSACTION ... COMMIT` block.
2. Every item receives its canonical deterministic identity:
   $$\text{entry\_id} = \text{SHA-256}(\text{receipt\_id} \parallel "|" \parallel \text{item} \parallel "|" \parallel \text{paid\_total}_{.6f} \parallel "|" \parallel \text{receipt\_date})$$
3. Records are marked `is_synced = 0`.
4. Phase 3's zero-friction auto-discovery background worker (`SyncService`) detects the local workstation daemon (`_peit-sync._tcp.local.` / `127.0.0.1:8000` / `10.0.2.2:8000`) and pushes the batch idempotently in 100-item chunks.

---

## 6. Implementation Strategy: Standalone OCR Prototype & Testing Framework

To ensure maximum econometric reliability before assembling Flutter screens, Phase 4 follows a structured **Prototype-First Engineering Workflow**:

### 6.1 Milestone 4A: Standalone Python OCR & Heuristic Parser Prototype (`src/peit/ocr/`) [COMPLETED]
- **Bilingual & International Parser Engine**:
  - Generalized heuristic parser supporting **MXN, USD, and EUR** currencies.
  - Multi-lingual date recognition (ISO `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, and Spanish/English text months).
  - Configurable VAT/tax regex dictionaries:
    - Spanish: `IVA`, `IEPS`, `TASA 16%`, `PROPINA`, `DESC`, `SUBTOTAL`, `TOTAL`.
    - English: `TAX`, `SALES TAX`, `VAT`, `TIP`, `DISC`, `SAVINGS`, `SUBTOTAL`, `TOTAL`.
  - Baseline price alignment: Spatial association pairing item names with right-aligned unit and total prices.
- **Strict Receipt-Level Scope Invariant**:
  - Enforces that all items extracted from a single scan strictly share identical `receipt_id`, `receipt_date`, `merchant`, and `currency`.
  - Strict total price sum check: $\sum \text{items} - \text{discount} + \text{tax} + \text{fee} + \text{deposit} = |\text{paid\_total}|$.

### 6.2 Milestone 4B: Synthetic Receipt Canvas & Distortion Simulator (`src/peit/ocr/canvas.py`) [COMPLETED]
- Programmatically generates realistic, multi-lingual thermal receipt image bitmaps (`PIL.Image.Image`) from PEIT structured receipts:
  - Thermal receipt layout standards (store headers, two-column line items, dashed dividers, balanced footers).
  - Tracks exact pixel boundaries and normalized bounding boxes $[0.0, 1.0]$ for all words and lines.
  - Distortion simulator `apply_distortions`: affine rotation ($\pm 3^\circ$), thermal head contrast fading, radial perspective vignetting, and grain noise.
  - Integrated CLI command `python -m peit.profiler generate-image -o receipt.png --manifest manifest.json`.
  - Verified with 100% round-trip fidelity against `ReceiptParser` in `test/test_ocr_canvas.py`.

### 6.3 Milestone 4C: Real Receipt Photo Benchmark Suite (`src/peit/ocr/benchmark.py`) [COMPLETED]
- Curated repository bundle of anonymized real-world smartphone receipt photos in `test/data/receipts/` (`20261006_221633.jpg` through `20261006_221920.jpg`) paired with strict ground truth JSON manifests (`*_truth.json`).
- Quantitative evaluation metrics:
  - Character Error Rate (CER) and Word Error Rate (WER) via dynamic programming Levenshtein distance.
  - Bipartite Line Item Matching (name similarity $\ge 0.80$ and $|\Delta_{\text{price}}| \le \$0.02$) yielding Precision, Recall, and $F_1$.
  - Double-Entry Mathematical Balance Rate (MBR) verifying arithmetic closure within $\$0.01$.
  - EXIF orientation auto-transposition (`ImageOps.exif_transpose`) resolving portrait sensor orientation (`Orientation = 6`).
- Benchmark outcome on real supermarket captures: CER = 5.41%, WER = 5.71%, Line Item $F_1$ = **81.70%**, MBR = 50.00%.

### 6.4 Milestone 4D: Flutter Mobile Client Integration (`mobile/lib/`) [COMPLETED]
- Integrated `google_mlkit_text_recognition: ^0.13.0` and `image: ^4.3.0` in `mobile/pubspec.yaml`.
- Ported OCR models and 25-column schema serializers to Dart (`mobile/lib/ocr/models.dart`).
- Ported bilingual heuristic parsing algorithm (`mobile/lib/ocr/parser.dart`) with 100% parity with Python parser (spatial baseline clustering, trailing price association, quantity expressions, and balance checks).
- Wrapped ML Kit Latin recognition engine in `mobile/lib/ocr/mlkit_service.dart`.
- Built background Dart isolate snippet cropper (`mobile/lib/ocr/snippet_cropper.dart`) using `compute` to slice normalized bounding boxes with 15% descender padding off the UI thread.
- Implemented reactive `ReceiptReviewController` (`mobile/lib/controllers/receipt_review_controller.dart`) with triage state, bulk approve $>95\%$, auto-reconciliation, and atomic Drift SQLite transactions.
- Implemented **Mode 1: Card Stream** (`mobile/lib/screens/receipt_card_stream_screen.dart`) with swipe gestures, visual snippets, and sticky balance verification HUD.
- Implemented **Mode 2: Financial Data Grid** (`mobile/lib/screens/receipt_data_grid_screen.dart`) with high-density tabular layout and split inspector sheet.
- Added live mode switching (`Icons.view_agenda` $\leftrightarrow$ `Icons.table_chart`) and camera/scan trigger in `mobile/lib/screens/home_screen.dart`.
- Validated via automated unit and integration tests in `mobile/test/model_test.dart`, `mobile/test/ocr_parser_test.dart`, and `mobile/test/review_controller_test.dart`.
