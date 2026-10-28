# Canonical Schema & Single Source of Truth (SSOT)

This document is the authoritative technical reference for the PEIT data model, column sequences, constraints, domain enumerations, identity hashing, and accounting sign conventions.

Relevant implementations:
- Python: [`src/peit/schema.py`](../../src/peit/schema.py)
- Dart (Flutter): [`mobile/lib/data/schema_constants.dart`](../../mobile/lib/data/schema_constants.dart)
- CSV Schema Definition: [`config/receipt_schema.csv`](../../config/receipt_schema.csv)
- Dart schema generator/check tool: [`util/generate_mobile_schema.py`](../../util/generate_mobile_schema.py)

---

## 1. Column Sequences

PEIT defines two primary tabular column sequences:

### 1.1 Canonical Receipt Items (`RECEIPT_COLUMNS` — 25 Columns)
These 25 columns represent single line-item observations within an ingested or generated receipt matching `config/receipt_schema.csv`:

| # | Column Name | Type | Constraints / Format | Description |
|---|---|---|---|---|
| 1 | `receipt_id` | `str` | Non-empty | Unique identifier of the receipt transaction |
| 2 | `receipt_date` | `str` | `YYYY-MM-DD` | Date of purchase (ISO 8601) |
| 3 | `merchant` | `str` | Non-empty | Merchant or store name |
| 4 | `item` | `str` | Non-empty | Item name or description |
| 5 | `brand` | `str` | String | Brand or manufacturer |
| 6 | `category` | `str` | Non-empty | Expenditure category |
| 7 | `quantity` | `float` | `> 0` | Purchased quantity |
| 8 | `pack_size` | `float` | `> 0` (default: 1.0) | Package size or unit multiplier |
| 9 | `unit` | `str` | Non-empty | Physical unit of measurement (`kg`, `L`, `pcs`, etc.) |
| 10 | `unit_price` | `float` | Numeric | Base price per unit |
| 11 | `currency` | `str` | Three ASCII letters (`^[A-Za-z]{3}$`) in Python row validation | Currency code; the Python validator checks the shape, not membership in a supported-currency list |
| 12 | `discount` | `float` | Signed positive (`>= 0`) | Discount amount applied to item |
| 13 | `fee` | `float` | Signed negative (`<= 0`) | Transaction fee or surcharge |
| 14 | `tax` | `float` | Signed negative (`<= 0`) | Value-added or sales tax |
| 15 | `deposit` | `float` | Signed negative (`<= 0`) | Container or bottle deposit |
| 16 | `paid_total` | `float` | Signed negative (`< 0` for expenses) | Net paid amount for this item |
| 17 | `event_type` | `str` | `EventType` enum | Transaction lifecycle event |
| 18 | `store_tier` | `str` | `QualityTier` enum | Store quality tier (`A`, `B`, `C`, `D`, `E`) |
| 19 | `store_rating` | `float` | `1.0 <= r <= 5.0` | Store customer rating |
| 20 | `brand_tier` | `str` | `QualityTier` enum | Brand tier (`A`, `B`, `C`, `D`, `E`) |
| 21 | `brand_rating` | `float` | `1.0 <= r <= 5.0` | Brand rating |
| 22 | `product_tier` | `str` | `QualityTier` enum | Product quality tier (`A`, `B`, `C`, `D`, `E`) |
| 23 | `product_rating`| `float` | `1.0 <= r <= 5.0` | Product rating |
| 24 | `availability` | `str` | `Availability` enum | Inventory status (`in_stock`, `low_stock`, etc.) |
| 25 | `notes` | `str` | Optional text | Freeform notes or context |

### 1.2 Ledger SQLite Projections (`LEDGER_COLUMNS` — 29 Columns)
In persistent storage, `LedgerEntry` wraps the 25 receipt columns with 4 envelope columns (`entry_id`, `month`, `account`, `recorded_at`):

```text
LEDGER_COLUMNS = (
    "entry_id", "month", "receipt_id", "receipt_date", "account",
    "merchant", "item", "brand", "category", "quantity",
    "pack_size", "unit", "unit_price", "currency", "discount",
    "fee", "tax", "deposit", "paid_total", "event_type",
    "store_tier", "store_rating", "brand_tier", "brand_rating",
    "product_tier", "product_rating", "availability", "notes",
    "recorded_at"
)
```

---

## 2. Domain Enums

### 2.1 `EventType`
Categorizes cash-flow direction and accounting nature:
- `recurring`: Periodic recurring expenditure (rent, utilities, subscriptions).
- `one_off`: Discretionary or single transaction purchase.
- `transfer`: Inter-account balance movement (e.g. checking $\to$ savings).
- `refund`: Returned item credit or cashback (+abs).
- `income`: Inbound salary, bonus, or deposit (+abs).

### 2.2 `Availability`
Inventory and supply availability tracking:
- `in_stock`: Normal store availability.
- `low_stock`: Limited stock noted.
- `out_of_stock`: Item was stock-out at scan time.
- `discontinued`: Merchant no longer offers item.

### 2.3 `QualityTier`
Standardized 5-point ordinal quality hierarchy:
- `A` (Premium / Gourmet), `B` (High / Preferred), `C` (Standard / Mass), `D` (Value / Economy), `E` (Generic / Budget).

---

## 3. Cryptographic Identity Hashing (`compute_entry_id`)

`compute_entry_id` returns a deterministic SHA-256 digest from four trimmed
fields:

$$\text{seed} = \texttt{receipt\_id} \mathbin{\Vert} \texttt{"|"}\mathbin{\Vert} \texttt{item} \mathbin{\Vert} \texttt{"|"}\mathbin{\Vert} \texttt{normalized\_amount} \mathbin{\Vert} \texttt{"|"}\mathbin{\Vert} \texttt{receipt\_date}$$

$$\text{entry\_id} = \text{SHA-256}(\text{seed})$$

### IEEE-754 Negative-Zero Safeguard
In floating-point math, `float("-0.0")` can produce `"-0.000000"` in Python while yielding `"0.000000"` in Dart.
To prevent cross-platform hash divergence, PEIT enforces a strict clamp:
```python
num_val = float(paid_total)
if abs(num_val) == 0.0:
    num_val = 0.0
norm_amount = f"{num_val:.6f}"
```

---

## 4. Accounting Sign Conventions

The normalizer helpers express these sign conventions:
- **Expenses (`paid_total`)**: Always negative (`-abs(amount)`).
- **Income (`paid_total`)**: Always positive (`+abs(amount)`).
- **Discounts (`discount`)**: Always positive (`+abs(amount)`), reflecting expenditure savings.
- **Surcharges (`tax`, `fee`, `deposit`)**: Always negative (`-abs(amount)`), reflecting additional cash outflows.

Canonical normalizers:
- Python: `normalize_expense_sign()`, `normalize_income_sign()`, `normalize_surcharge_sign()`, `normalize_discount_sign()`
- Dart: `normalizeExpenseSign()`, `normalizeIncomeSign()`, `normalizeSurchargeSign()`, `normalizeDiscountSign()`

`validate_rows()` checks that these monetary fields are numeric; it does not
enforce these signs or reconcile a receipt total. Do not infer that every
persisted client row has passed the same validation or normalization.

---

## 5. Implementation boundaries

Python `src/peit/schema.py` defines `RECEIPT_COLUMNS`, ledger envelope
metadata, enums, normalizers, and `compute_entry_id`. Dart
`mobile/lib/data/schema_constants.dart` contains corresponding definitions,
and `mobile/lib/data/schema.dart` declares a Drift table. The Flutter runtime
database in `mobile/lib/data/database.dart`, however, creates its SQLite table
using direct `sqlite3` bindings. Drift declarations and dependencies therefore
do not establish that Drift is the runtime persistence engine.

The separate Android app under `demo/` uses Room entities with a different
receipt identity boundary: `ReceiptEntity.receipt_id` is the Room primary key.
During review save, Android generates a `receipt_id` per line and stores a
shared receipt-group key in `notes`; that differs from canonical receipt
groups whose line-item rows share a receipt ID. The Android UI restricts
currency to `MXN`/`USD`/`EUR` and quality tiers to `A`–`D`, while the Python
schema includes tier `E` and its validator only checks three-letter currency
shape. Android stores event/availability values as strings and currently
saves reviewed rows as `one_off`/`in_stock`.

The Python ledger includes `entry_id`, `month`, `account`, and `recorded_at`
envelope fields. Flutter adds synchronization state and carries `account` and
`recorded_at` in its local and sync representations. The Android receipt row
and ledger entity use separate, smaller fields (`previous_hash`, `timestamp`,
and `is_valid` on the ledger); receipt-group provenance is in `notes`. These
envelopes and provenance conventions are not interchangeable. The Python,
Flutter, and Android implementations must not be described as behaviorally
identical or as one enforced SSOT.

The four-field Python/Dart digest is not the same as the Android ledger's
separate hash-chain metadata. Receipt-level grouping, sync envelopes, account
fields, and provenance payloads also vary by application surface. Consult the
implementation before relying on any cross-client contract.
