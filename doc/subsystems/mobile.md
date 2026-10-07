# Mobile Capture UI/UX Architectural Specification

This document details the mobile receipt capture workflows and image processing strategies agreed upon for the PEIT mobile application.

---

## 1. Capture Initiation Modes

The PEIT mobile application supports three distinct ingestion pathways to accommodate paper supermarket slips, printed invoices, and electronic receipts:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Receipt Ingestion Modes                         │
├────────────────────────┬───────────────────────┬───────────────────────┤
│ Mode 1: System Camera  │ Mode 2: System Picker │ Mode 3: Burst Mode    │
│ Standard device camera │ Photo gallery and     │ Multi-page consecutive│
│ for quick single-snap  │ screenshot/PDF        │ capture for long      │
│ receipts               │ file import           │ supermarket slips     │
└────────────────────────┴───────────────────────┴───────────────────────┘
```

### 1.1 Mode 1: Standard System Camera
- **Target Use Case:** Quick, everyday single-receipt scanning (e.g., convenience stores, cafes, pharmacies).
- **Behavior:** Delegates to the native camera via Flutter's `image_picker` or camera intent.
- **Benefits:** Retains full hardware camera capabilities (OEM optical image stabilization, HDR, native macro focusing, flash control) without custom camera viewfinder overhead.
- **Post-Capture:** Automatic basic orientation normalization and contrast leveling before dispatch to ML Kit Text Recognition.

### 1.2 Mode 2: Gallery & Document Picker Sheet
- **Target Use Case:** Digital PDF invoices, banking app screenshots, email receipt screenshots, and previously photographed slips.
- **Behavior:** Opens system media/file picker (`image_picker` for photos, `file_picker` for PDFs).
- **PDF Handling:** High-resolution rasterization of PDF pages (rendered at 300 DPI) into in-memory bitmaps for OCR processing.

### 1.3 Mode 3: Multi-Page Burst Mode
- **Target Use Case:** Long supermarket and wholesale paper slips (e.g., Walmart, Costco, Chedraui) that span 30–80 cm and cannot be photographed in a single legible snap.
- **Behavior:** Allows taking consecutive snaps in a single review session (Snap 1: Header/Store $\to$ Snap 2: Mid-receipt items $\to$ Snap 3: Totals/Taxes).
- **Processing:** Sequential OCR processing across images with continuous vertical line-item index stitching and global footer deduplication.

---

## 2. Qualitative Tagging & Historical Inheritance

Supermarket receipts frequently contain 10–30 items. Manually selecting 25 columns for each item is tedious and error-prone. PEIT implements **Historical Tag Inheritance**:

1. **Merchant-Level Inheritance:**
   - When OCR recognizes `merchant` (e.g., "Costco Wholesale"), the app queries local SQLite for the most recent transaction from that merchant.
   - Automatically populates `store_tier` and `store_rating`.
2. **Item & Brand-Level Inheritance:**
   - As line items are parsed (e.g., "Leche Lala 1L"), the app searches historical ledger records for matching `item` and `brand` keys.
   - Automatically inherits:
     - `category` (e.g., "Food and beverages")
     - `brand_tier` and `brand_rating`
     - `product_tier` and `product_rating`
     - `unit` and `pack_size`
3. **Availability Default & Quick Chips:**
   - All scanned items default to `availability = in_stock`.
   - The review UI exposes one-tap chips (`in_stock`, `low_stock`, `out_of_stock`, `discontinued`) to easily override anomalies.

---

## 3. Mathematical Sanity & Validation Enforcement

PEIT enforces strict arithmetic consistency:

$$\sum_{i=1}^{N} \text{total\_price}_i - \text{discount} + \text{tax} + \text{deposit} + \text{fee} = |\text{paid\_total}|$$

- **Visual Highlighting:**
  - **Green Badge:** High OCR confidence ($>85\%$), matching dictionary words, and mathematically consistent lines.
  - **Amber Badge:** Medium confidence ($60\%-85\%$) or unmapped categories.
  - **Red Badge:** Missing required fields, failed numeric parsing, or math discrepancy.
- **Commit Guard:**
  - The "Commit to Ledger" action is disabled while a red mathematical discrepancy exists.
  - The UI indicates the exact delta (e.g., *"Sum of items ($485.00) differs from receipt total ($490.00) by $5.00"*).
  - Users can tap to add a missing adjustment item (e.g., round-off fee or unparsed bottle deposit) or manually adjust detected amounts.

---

## 4. Local Receipt Image Storage & Privacy Policy

- **Default Storage:** Captured receipt images are stored in the app's local private sandbox directory (`/data/user/0/.../app_flutter/receipts/` on Android, `ApplicationSupport/receipts/` on iOS).
- **Zero Cloud Leakage:** Photos are never uploaded to any remote server or third-party service; OCR runs 100% on-device via ML Kit.
- **Lifecycle Management:**
  - Configurable retention in settings:
    1. *Retain indefinitely* (for physical audit proof).
    2. *Compress to low-res thumbnail after sync* (saves device flash storage).
    3. *Delete image automatically once synced to desktop ledger* (maximum privacy).

