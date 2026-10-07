# OCR & Computer Vision Pipeline (`src/peit/ocr/`)

This document describes the on-device and desktop optical character recognition (OCR) and receipt parsing pipeline in PEIT.

The code implementations reside in:
- Data models & 25-column mapper: [`src/peit/ocr/models.py`](../../src/peit/ocr/models.py)
- Spatial clustering & bilingual heuristic parser: [`src/peit/ocr/parser.py`](../../src/peit/ocr/parser.py)
- Synthetic thermal receipt canvas: [`src/peit/ocr/canvas.py`](../../src/peit/ocr/canvas.py)
- Benchmark & evaluation engine: [`src/peit/ocr/benchmark.py`](../../src/peit/ocr/benchmark.py)
- Flutter mobile counterpart: [`mobile/lib/ocr/`](../../mobile/lib/ocr/)

---

## 1. Pipeline Architecture

The receipt parsing workflow operates in four stages:

```text
Receipt Image 
   │
   ▼
[1. Text Recognition (ML Kit / Tesseract / Synthetic)]
   │ ➔ Bounding Boxes + Normalized Text Blocks
   ▼
[2. Spatial Clustering & Line Association]
   │ ➔ Group text blocks into horizontal visual lines
   ▼
[3. Bilingual Heuristic Parsing]
   │ ➔ Extract merchant, ISO date, currency (MXN/USD/EUR/CAD)
   │ ➔ Associate items with unit & total prices
   │ ➔ Identify subtotal, taxes (IVA/IEPS), discounts, and paid total
   ▼
[4. Mathematical Reconciliation & Canonical 25-Column Mapping]
   │ ➔ Verify: Subtotal - Discount + Tax + Fee = Paid Total
   │ ➔ Produce deterministic SHA-256 entry_id and canonical rows
   ▼
Validated Receipt Rows (RECEIPT_COLUMNS)
```

---

## 2. Bilingual Parsing Features

PEIT natively supports both Spanish and English physical receipts:
- **Tax & Fee Dictionaries**:
  - Spanish: `IVA`, `IEPS`, `TASA 16%`, `PROPINA`, `DESC`, `SUBTOTAL`, `TOTAL`.
  - English: `TAX`, `SALES TAX`, `VAT`, `TIP`, `DISC`, `SAVINGS`, `SUBTOTAL`, `TOTAL`.
- **Date Formats**:
  - ISO `YYYY-MM-DD`, slash dates `DD/MM/YYYY` or `MM/DD/YYYY`.
  - Spanish text dates: `"15 de marzo de 2026"`, `"24-abr-2025"`.
- **Currency Detection**:
  - Automatically identifies `MXN` (`$`, `PESOS`, `M.N.`), `USD` (`USD`, `US$`), `EUR` (`EUR`, `€`), and `CAD`.

---

## 3. Mathematical Balance Verification

Every parsed receipt calculates an arithmetic balance delta:

$$\Delta_{\text{balance}} = \text{paid\_total} - (\text{subtotal} - \text{discount} + \text{tax} + \text{fee} + \text{deposit})$$

- Receipts are flagged as balanced if $|\Delta_{\text{balance}}| < 0.05$.
- When math reconciles, items are trusted with high confidence.
- When unbalance occurs, items remain editable in mobile review screens (Card Stream / Data Grid) with a sticky reconcile HUD.

---

## 4. Synthetic Canvas & Benchmark Suite

- **Synthetic Canvas (`src/peit/ocr/canvas.py`)**:
  Generates photo-realistic receipts with simulated thermal paper fade, perspective warping, Gaussian blur, and lighting gradients for automated testing.
- **Evaluation Metrics (`src/peit/ocr/benchmark.py`)**:
  - Character Error Rate (CER) and Word Error Rate (WER).
  - Bipartite Item Matching $F_1$-score.
  - Mathematical Balance Rate (MBR).
- Automated tests run via `bash test/run_tests.sh --suite ocr_benchmark`.

