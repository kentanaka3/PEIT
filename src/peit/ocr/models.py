"""Data models for Optical Character Recognition (OCR) and receipt parsing."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from peit.schema import (
    RECEIPT_COLUMNS,
    Availability,
    EventType,
    MAX_RATING,
    QualityTier,
    normalize_discount_sign,
    normalize_expense_sign,
    normalize_surcharge_sign,
)


@dataclass(frozen=True)
class BoundingBox:
  """Bounding box coordinates for detected OCR text regions.

  Coordinates can be normalized (0.0 to 1.0) or absolute pixel measurements.
  """

  x: float
  y: float
  width: float
  height: float

  @property
  def right(self) -> float:
    """Right boundary x coordinate."""
    return self.x + self.width

  @property
  def bottom(self) -> float:
    """Bottom boundary y coordinate."""
    return self.y + self.height

  @property
  def center_x(self) -> float:
    """Center x coordinate."""
    return self.x + self.width / 2.0

  @property
  def center_y(self) -> float:
    """Center y coordinate."""
    return self.y + self.height / 2.0


@dataclass
class OCRTextBlock:
  """Extracted OCR text unit with associated spatial bounding box and confidence."""

  text: str
  bbox: BoundingBox
  confidence: float = 1.0


@dataclass
class ParsedLineItem:
  """Extracted and normalized receipt line item."""

  item: str
  brand: str = "Generic"
  category: str = "General"
  quantity: float = 1.0
  pack_size: float = 1.0
  unit: str = "ea"
  unit_price: float = 0.0
  total_price: float = 0.0
  discount: float = 0.0
  fee: float = 0.0
  tax: float = 0.0
  deposit: float = 0.0
  event_type: str = EventType.ONE_OFF.value
  store_tier: str = QualityTier.A.value
  store_rating: float = MAX_RATING
  brand_tier: str = QualityTier.A.value
  brand_rating: float = MAX_RATING
  product_tier: str = QualityTier.A.value
  product_rating: float = MAX_RATING
  availability: str = Availability.IN_STOCK.value
  notes: str = ""
  confidence: float = 1.0
  bbox: BoundingBox | None = None


@dataclass
class ParsedReceipt:
  """Structured representation of a parsed receipt conforming to PEIT semantics."""

  receipt_id: str
  receipt_date: str
  merchant: str
  currency: str = "MXN"
  items: list[ParsedLineItem] = field(default_factory=list)
  subtotal: float = 0.0
  discount_total: float = 0.0
  tax_total: float = 0.0
  fee_total: float = 0.0
  deposit_total: float = 0.0
  paid_total: float = 0.0
  is_balanced: bool = False
  balance_delta: float = 0.0
  confidence: float = 1.0
  store_id: str = ""
  raw_text: str = ""

  def to_peit_rows(self) -> list[dict[str, Any]]:
    """Convert parsed receipt into standard 25-column dictionary rows for PEIT.

    Follows PEIT sign conventions:
    - paid_total is negative (< 0) for expenditures
    - discount is positive (> 0)
    - tax, fee, deposit are negative (<= 0)
    """
    rows: list[dict[str, Any]] = []
    n_items = len(self.items)

    # Distribute receipt-level discount/tax/fee/deposit across items if item-level not specified
    # If item-level totals exist, check sum
    item_sum_discount = sum(item.discount for item in self.items)
    item_sum_tax = sum(item.tax for item in self.items)
    item_sum_fee = sum(item.fee for item in self.items)
    item_sum_deposit = sum(item.deposit for item in self.items)

    unallocated_discount = max(
        0.0, self.discount_total - item_sum_discount) if self.discount_total > 0 else 0.0
    unallocated_tax = max(0.0, self.tax_total -
                          item_sum_tax) if self.tax_total > 0 else 0.0
    unallocated_fee = max(0.0, self.fee_total -
                          item_sum_fee) if self.fee_total > 0 else 0.0
    unallocated_deposit = max(
        0.0, self.deposit_total - item_sum_deposit) if self.deposit_total > 0 else 0.0

    valid_tiers = {tier.value for tier in QualityTier}
    valid_availabilities = {avail.value for avail in Availability}

    for idx, item in enumerate(self.items):
      item_discount = item.discount
      item_tax = item.tax
      item_fee = item.fee
      item_deposit = item.deposit

      # Distribute leftover unallocated totals proportionally or evenly
      if unallocated_discount > 0 and n_items > 0:
        item_discount += unallocated_discount / n_items
      if unallocated_tax > 0 and n_items > 0:
        item_tax += unallocated_tax / n_items
      if unallocated_fee > 0 and n_items > 0:
        item_fee += unallocated_fee / n_items
      if unallocated_deposit > 0 and n_items > 0:
        item_deposit += unallocated_deposit / n_items

      # Item paid total: total_price - discount + tax + fee + deposit
      # Sign convention: negative for expense
      item_net = item.total_price - item_discount + item_tax + item_fee + item_deposit
      # Ensure paid_total is negative for expenditure
      item_paid_total = normalize_expense_sign(
          round(item_net, 4) if item_net > 0 else round(item.total_price, 4))

      # Strictly 25 columns
      row = {
          "receipt_id": self.receipt_id,
          "receipt_date": self.receipt_date,
          "merchant": self.merchant,
          "item": item.item,
          "brand": item.brand if item.brand else "Generic",
          "category": item.category if item.category else "General",
          "quantity": f"{item.quantity:.4f}".rstrip("0").rstrip(".") if item.quantity % 1 != 0 else f"{int(item.quantity)}",
          "pack_size": f"{item.pack_size:.4f}".rstrip("0").rstrip(".") if item.pack_size % 1 != 0 else f"{int(item.pack_size)}",
          "unit": item.unit if item.unit else "ea",
          "unit_price": f"{item.unit_price:.2f}",
          "currency": self.currency,
          "discount": f"{normalize_discount_sign(item_discount):.2f}",
          "fee": f"{normalize_surcharge_sign(item_fee):.2f}" if item_fee != 0 else "0.00",
          "tax": f"{normalize_surcharge_sign(item_tax):.2f}" if item_tax != 0 else "0.00",
          "deposit": f"{normalize_surcharge_sign(item_deposit):.2f}" if item_deposit != 0 else "0.00",
          "paid_total": f"{item_paid_total:.2f}",
          "event_type": item.event_type if item.event_type else EventType.ONE_OFF.value,
          "store_tier": item.store_tier if item.store_tier in valid_tiers else QualityTier.A.value,
          "store_rating": f"{float(item.store_rating):.1f}",
          "brand_tier": item.brand_tier if item.brand_tier in valid_tiers else QualityTier.A.value,
          "brand_rating": f"{float(item.brand_rating):.1f}",
          "product_tier": item.product_tier if item.product_tier in valid_tiers else QualityTier.A.value,
          "product_rating": f"{float(item.product_rating):.1f}",
          "availability": item.availability if item.availability in valid_availabilities else Availability.IN_STOCK.value,
          "notes": item.notes if item.notes else "",
      }
      # Verify all RECEIPT_COLUMNS keys are present and exact column count matches
      assert all(
          k in row for k in RECEIPT_COLUMNS), "Generated row missing required PEIT keys"
      assert len(row) == len(
          RECEIPT_COLUMNS), f"Expected {len(RECEIPT_COLUMNS)} columns, got {len(row)}"
      rows.append(row)

    return rows

  def to_json(self, indent: int = 2) -> str:
    """Serialize parsed receipt to a JSON string."""
    def _serializer(o: Any) -> Any:
      if isinstance(o, (BoundingBox, OCRTextBlock, ParsedLineItem, ParsedReceipt)):
        return asdict(o)
      raise TypeError(
          f"Object of type {type(o).__name__} is not JSON serializable")

    return json.dumps(asdict(self), indent=indent, default=_serializer)
