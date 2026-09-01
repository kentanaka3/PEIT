"""Core schema validation and transparent index calculations."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
REQUIRED = (
    "month", "receipt_id", "receipt_date", "merchant", "item_raw",
    "item_normalized", "category", "quantity", "unit", "shelf_unit_price",
    "currency", "discount", "fee", "tax", "deposit", "paid_total",
    "event_type", "source_file", "notes",
)
EVENT_TYPES = {"recurring", "one_off", "transfer", "refund", "income"}
STATUS_INSUFFICIENT = {
    "status": "insufficient_history",
    "message": "Insufficient historical data",
}


@dataclass(frozen=True)
class ValidationIssue:
  row: int
  field: str
  message: str


def _number(value: str, field: str, row: int, issues: list[ValidationIssue]) -> float | None:
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
    if not MONTH_RE.match(row["month"]):
      issues.append(ValidationIssue(row_number, "month", "must use YYYY-MM"))
    try:
      date.fromisoformat(row["receipt_date"])
    except ValueError:
      issues.append(ValidationIssue(
          row_number, "receipt_date", "must use YYYY-MM-DD"))
    quantity = _number(row["quantity"], "quantity", row_number, issues)
    if quantity is not None and quantity <= 0:
      issues.append(ValidationIssue(
          row_number, "quantity", "must be positive"))
    if not row["unit"].strip():
      issues.append(ValidationIssue(row_number, "unit", "must not be empty"))
    for field in ("shelf_unit_price", "discount", "fee", "tax", "deposit", "paid_total"):
      _number(row[field], field, row_number, issues)
    if not re.fullmatch(r"[A-Za-z]{3}", row["currency"]):
      issues.append(ValidationIssue(
          row_number, "currency", "must be a three-letter code"))
    if row["event_type"] not in EVENT_TYPES:
      issues.append(ValidationIssue(
          row_number, "event_type", "unsupported event type"))
  return issues


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[ValidationIssue]]:
  """Read and validate a monthly CSV, preserving rows for audit."""
  with path.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    if reader.fieldnames is None:
      return [], [ValidationIssue(1, "header", "missing CSV header")]
    missing = [field for field in REQUIRED if field not in reader.fieldnames]
    if missing:
      return [], [ValidationIssue(1, field, "missing column") for field in missing]
    rows = list(reader)
  return rows, validate_rows(rows)


def _monthly_item_unit_prices(rows: Iterable[dict[str, str]]) -> dict[str, float]:
  """Compute quantity-weighted average unit price for each normalized item."""
  totals: dict[str, float] = defaultdict(float)
  quantities: dict[str, float] = defaultdict(float)
  for row in rows:
    item = row["item_normalized"]
    try:
      qty = float(row["quantity"])
      price = float(row["shelf_unit_price"])
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


def calculate_indices(rows: Iterable[dict[str, str]]) -> list[dict[str, object]]:
  """Calculate transparent monthly price and expenditure indices.

  The first available month is 100.0. Price observations use exact normalized
  items first, then category averages when no item match exists.
  """
  grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
  for row in rows:
    if row["event_type"] in {"recurring", "one_off"}:
      grouped[row["month"]].append(row)
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
    matched = [current_prices[item] / base_prices[item]
               for item in base_prices if item in current_prices and base_prices[item] > 0]
    price_index = 100.0 * sum(matched) / len(matched) if matched else None
    expenditure = sum(abs(float(row["paid_total"])) for row in current)
    output.append({
        "month": month,
        "fixed_basket_index": round(price_index, 6) if price_index is not None else None,
        "changing_basket_expenditure_index": round(100 * expenditure / base_total, 6)
        if base_total else None,
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


def audit_append(audit_path: Path, rows: list[dict[str, str]], source_file: str) -> None:
  """Append imported rows and provenance to a JSON-lines audit ledger."""
  audit_path.parent.mkdir(parents=True, exist_ok=True)
  with audit_path.open("a", encoding="utf-8") as handle:
    for row in rows:
      handle.write(json.dumps({
          "action": "import",
          "import_date": date.today().isoformat(),
          "source_file": source_file,
          "row": row,
      }, sort_keys=True) + "\n")
