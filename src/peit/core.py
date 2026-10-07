"""Core schema validation and transparent index calculations."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
REQUIRED = (
    "receipt_id", "receipt_date", "merchant", "item", "brand", "category",
    "quantity", "pack_size", "unit", "unit_price", "currency", "discount",
    "fee", "tax", "deposit", "paid_total", "event_type", "store_tier",
    "store_rating", "brand_tier", "brand_rating", "product_tier",
    "product_rating", "availability", "notes",
)
EVENT_TYPES = {"recurring", "one_off", "transfer", "refund", "income"}
AVAILABILITY_STATUSES = {"in_stock", "low_stock", "out_of_stock", "discontinued"}
TIERS = {"A", "B", "C", "D", "E"}
STATUS_INSUFFICIENT = {
    "status": "insufficient_history",
    "message": "Insufficient historical data",
}


@dataclass(frozen=True)
class ValidationIssue:
  row: int
  field: str
  message: str


def _number(
    value: str, field: str, row: int, issues: list[ValidationIssue]
) -> float | None:
  try:
    return float(value)
  except (TypeError, ValueError):
    issues.append(ValidationIssue(row, field, "must be numeric"))
    return None


def validate_rows(rows: Iterable[dict[str, str]]) -> list[ValidationIssue]:
  """Validate normalized receipt rows without changing their source values."""
  issues: list[ValidationIssue] = []
  for row_number, row in enumerate(rows, start=2):
    for field in REQUIRED:
      if field not in row:
        issues.append(ValidationIssue(row_number, field, "missing column"))
    if any(field not in row for field in REQUIRED):
      continue
    try:
      date.fromisoformat(row["receipt_date"])
    except (ValueError, TypeError):
      issues.append(ValidationIssue(
          row_number, "receipt_date", "must use YYYY-MM-DD"))
    quantity = _number(row["quantity"], "quantity", row_number, issues)
    if quantity is not None and quantity <= 0:
      issues.append(ValidationIssue(
          row_number, "quantity", "must be positive"))
    pack_size_val = row.get("pack_size", "")
    if (pack_size_val is None or (
        isinstance(pack_size_val, str) and not pack_size_val.strip()
    )):
      pack_size = 1.0
    else:
      pack_size = _number(str(pack_size_val), "pack_size", row_number, issues)
    if pack_size is not None and pack_size <= 0:
      issues.append(ValidationIssue(
          row_number, "pack_size", "must be positive"
      ))
    if not str(row["unit"]).strip():
      issues.append(ValidationIssue(row_number, "unit", "must not be empty"))
    for field in (
        "unit_price", "discount", "fee", "tax", "deposit", "paid_total"
    ):
      _number(row[field], field, row_number, issues)
    if not re.fullmatch(r"[A-Za-z]{3}", str(row["currency"])):
      issues.append(ValidationIssue(
          row_number, "currency", "must be a three-letter code"))
    if row["event_type"] not in EVENT_TYPES:
      issues.append(ValidationIssue(
          row_number, "event_type", "unsupported event type"))
    for field in ("store_tier", "brand_tier", "product_tier"):
      if row[field] not in TIERS:
        issues.append(ValidationIssue(
            row_number, field, "must be one of A, B, C, D, E"))
    for field in ("store_rating", "brand_rating", "product_rating"):
      try:
        rating = float(row[field])
        if not (1.0 <= rating <= 5.0):
          issues.append(ValidationIssue(
              row_number, field, "must be between 1.0 and 5.0"))
      except (ValueError, TypeError):
        issues.append(ValidationIssue(
            row_number, field, "must be between 1.0 and 5.0"))
    if row["availability"] not in AVAILABILITY_STATUSES:
      issues.append(
          ValidationIssue(
              row_number, "availability", "unsupported availability status"
          )
      )
  return issues


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[ValidationIssue]]:
  """Read and validate a monthly CSV, preserving rows for audit."""
  with path.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    if reader.fieldnames is None:
      return [], [ValidationIssue(1, "header", "missing CSV header")]
    missing = [field for field in REQUIRED if field not in reader.fieldnames]
    if missing:
      return [], [
          ValidationIssue(1, field, "missing column") for field in missing
      ]
    rows = list(reader)
  return rows, validate_rows(rows)


def _monthly_item_unit_prices(
    rows: Iterable[dict[str, str]]
) -> dict[str, float]:
  """Compute quantity-weighted average unit price for each normalized item."""
  totals: dict[str, float] = defaultdict(float)
  quantities: dict[str, float] = defaultdict(float)
  for row in rows:
    try:
      item = row["item"]
      qty = float(row["quantity"])
      price = float(row["unit_price"])
    except (ValueError, KeyError):
      continue
    if qty > 0 and price >= 0:
      totals[item] += qty * price
      quantities[item] += qty
  return {
      item: totals[item] / quantities[item]
      for item in quantities
      if quantities[item] > 0
  }


def calculate_indices(
    rows: Iterable[dict[str, str]]
) -> list[dict[str, object]]:
  """Calculate transparent monthly price and expenditure indices.

  The first available month is 100.0. Price observations use exact normalized
  items first, then category averages when no item match exists.
  """
  grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
  for row in rows:
    if row.get("event_type") in {"recurring", "one_off"}:
      month = (row["receipt_date"][:7] if (
          "receipt_date" in row and row["receipt_date"]
      ) else row.get("month", ""))
      grouped[month].append(row)
  months = sorted(grouped)
  if not months:
    return []
  base = grouped[months[0]]
  base_prices = _monthly_item_unit_prices(base)
  base_total = sum(abs(float(row["paid_total"])) for row in base)
  output: list[dict[str, object]] = []
  for month in months:
    current = grouped[month]
    current_prices = _monthly_item_unit_prices(current)
    matched = [
        current_prices[item] / base_prices[item] for item in base_prices
        if item in current_prices and base_prices[item] > 0
    ]
    price_index = 100.0 * sum(matched) / len(matched) if matched else None
    expenditure = sum(abs(float(row["paid_total"])) for row in current)
    output.append({
        "month": month,
        "fixed_basket_index": (
            round(price_index, 6) if price_index is not None else None
        ),
        "changing_basket_expenditure_index": (
            round(100 * expenditure / base_total, 6) if base_total else None
        ),
        "coverage_percent": round(100 * len(matched) / len(base_prices), 2)
        if base_prices else 0.0,
        "expenditure": round(expenditure, 6),
        "status": "derived",
    })
  for index, record in enumerate(output):
    current = record["fixed_basket_index"]
    previous = output[index - 1]["fixed_basket_index"] if index else None
    record["mom_percent"] = round(
        100 * (current / previous - 1), 6) if current and previous else None
  return output
