# Canonical Schema & Single Source of Truth (SSOT)

This document is the authoritative technical reference for the PEIT data model, column sequences, constraints, domain enumerations, identity hashing, and accounting sign conventions.

The code implementations are mastered in:
- Python: [`src/peit/schema.py`](../../src/peit/schema.py)
- Dart (Flutter): [`mobile/lib/data/schema_constants.dart`](../../mobile/lib/data/schema_constants.dart)
- CSV Schema Definition: [`config/receipt_schema.csv`](../../config/receipt_schema.csv)
- Drift Synchronization Tool: [`util/generate_mobile_schema.py`](../../util/generate_mobile_schema.py)

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
| 11 | `currency` | `str` | 3 letters (`^[A-Za-z]{3}$`) | Currency code (`MXN`, `USD`, `EUR`, `CAD`) |
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

Entry deduplication relies on a deterministic SHA-256 hash of a 4-tuple:

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

All monetary amounts follow double-entry signed cash-flow conventions:
- **Expenses (`paid_total`)**: Always negative (`-abs(amount)`).
- **Income (`paid_total`)**: Always positive (`+abs(amount)`).
- **Discounts (`discount`)**: Always positive (`+abs(amount)`), reflecting expenditure savings.
- **Surcharges (`tax`, `fee`, `deposit`)**: Always negative (`-abs(amount)`), reflecting additional cash outflows.

Canonical normalizers:
- Python: `normalize_expense_sign()`, `normalize_income_sign()`, `normalize_surcharge_sign()`, `normalize_discount_sign()`
- Dart: `normalizeExpenseSign()`, `normalizeIncomeSign()`, `normalizeSurchargeSign()`, `normalizeDiscountSign()`

---

## 5. Cross-Platform Parity Verification

To guarantee that Python and Dart definitions never diverge:
```bash
# Check schema drift in CI
python util/generate_mobile_schema.py --check

# Regenerate mobile constants after changing src/peit/schema.py
python util/generate_mobile_schema.py --write
```
Parity is verified by 6 automated unit tests in `test/test_schema.py`.

