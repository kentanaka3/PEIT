"""Canonical Single Source of Truth (SSOT) schema definitions for PEIT.

This module defines the canonical 25-column receipt schema, ledger envelope
columns, mobile sync attributes, domain enumerations, cryptographic identity
hashing, and accounting sign normalizers.

Only the Python standard library is used.
"""

from __future__ import annotations

from dataclasses import dataclass
import enum
import hashlib
from pathlib import Path
import re
from typing import Any

# Schema Version
SCHEMA_VERSION: int = 1

# Canonical 25 receipt columns matching config/receipt_schema.csv
RECEIPT_COLUMNS: tuple[str, ...] = (
    "receipt_id",
    "receipt_date",
    "merchant",
    "item",
    "brand",
    "category",
    "quantity",
    "pack_size",
    "unit",
    "unit_price",
    "currency",
    "discount",
    "fee",
    "tax",
    "deposit",
    "paid_total",
    "event_type",
    "store_tier",
    "store_rating",
    "brand_tier",
    "brand_rating",
    "product_tier",
    "product_rating",
    "availability",
    "notes",
)

# Envelope attributes prepended/appended to canonical receipt rows in the ledger
LEDGER_ENVELOPE_COLUMNS: tuple[str, ...] = (
    "entry_id",
    "month",
    "account",
    "recorded_at",
)

# 29-column SQLite entries table projection and LedgerEntry order
LEDGER_COLUMNS: tuple[str, ...] = (
    "entry_id",
    "month",
    "receipt_id",
    "receipt_date",
    "account",
    "merchant",
    "item",
    "brand",
    "category",
    "quantity",
    "pack_size",
    "unit",
    "unit_price",
    "currency",
    "discount",
    "fee",
    "tax",
    "deposit",
    "paid_total",
    "event_type",
    "store_tier",
    "store_rating",
    "brand_tier",
    "brand_rating",
    "product_tier",
    "product_rating",
    "availability",
    "notes",
    "recorded_at",
)

# Mobile synchronization status columns
MOBILE_SYNC_COLUMNS: tuple[str, ...] = (
    "is_synced",
    "synced_at",
)


# Domain Enumerations


class EventType(str, enum.Enum):
  """Permissible accounting transaction event types."""

  RECURRING = "recurring"
  ONE_OFF = "one_off"
  TRANSFER = "transfer"
  REFUND = "refund"
  INCOME = "income"


class Availability(str, enum.Enum):
  """Permissible inventory availability statuses."""

  IN_STOCK = "in_stock"
  LOW_STOCK = "low_stock"
  OUT_OF_STOCK = "out_of_stock"
  DISCONTINUED = "discontinued"


class QualityTier(str, enum.Enum):
  """Permissible quality tiers for store, brand, and product ratings."""

  A = "A"
  B = "B"
  C = "C"
  D = "D"
  E = "E"


# Rating bounds
MIN_RATING: float = 1.0
MAX_RATING: float = 5.0

# Currencies
RECOGNIZED_CURRENCIES: frozenset[str] = frozenset({"MXN", "USD", "EUR", "CAD"})
CURRENCY_REGEX: re.Pattern[str] = re.compile(r"^[A-Za-z]{3}$")


# Cryptographic Identity Hashing


def compute_entry_id(
    receipt_id: str,
    item: str,
    paid_total: float | str | int,
    receipt_date: str,
) -> str:
  """Compute deterministic SHA-256 hash for entry deduplication.

  Normalizes numeric values with a negative-zero clamp safeguard:
  abs(num_val) == 0.0 -> 0.0, formatted to 6 decimal places.
  Strips whitespace from string components.
  """
  try:
    num_val = float(paid_total)
    if abs(num_val) == 0.0:
      num_val = 0.0
    norm_amount = f"{num_val:.6f}"
  except (ValueError, TypeError):
    norm_amount = str(paid_total).strip()

  seed = (
      f"{str(receipt_id).strip()}|"
      f"{str(item).strip()}|"
      f"{norm_amount}|"
      f"{str(receipt_date).strip()}".encode("utf-8")
  )
  return hashlib.sha256(seed).hexdigest()


# Accounting Sign Normalizers


def normalize_expense_sign(amount: float) -> float:
  """Ensure negative numeric sign for expenses (-abs(amount))."""
  return -abs(float(amount))


def normalize_income_sign(amount: float) -> float:
  """Ensure positive numeric sign for income (+abs(amount))."""
  return abs(float(amount))


def normalize_surcharge_sign(amount: float) -> float:
  """Ensure negative numeric sign for surcharges (fees, taxes, deposits)."""
  return -abs(float(amount))


def normalize_discount_sign(amount: float) -> float:
  """Ensure positive numeric magnitude for applied discounts (+abs(amount))."""
  return abs(float(amount))


@dataclass(frozen=True)
class ColumnDefinition:
  """Metadata definition for a schema column."""

  name: str
  dtype: type
  sqlite_type: str
  is_required: bool
  default: Any
  description: str
