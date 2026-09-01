#!/usr/bin/env python3
"""Sort a PEIT receipt CSV by its receipt and item identity fields."""

from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TextIO


DEFAULT_INPUT = Path(__file__).resolve(
).parents[1] / "data" / "example_month.csv"
SORT_FIELDS = ("receipt_date", "merchant", "item_raw", "quantity", "unit")


def _quantity_key(value: str) -> tuple[int, Decimal | str]:
  """
  Sort numeric quantities numerically while keeping malformed values last.
  Return a tuple of (sort_order, value) where sort_order is 0 for valid
  numbers and 1 for invalid numbers. This ensures that invalid numbers are
  sorted after valid numbers, while still preserving the original value for
  display purposes.
  """
  try:
    return (0, Decimal(value))
  except InvalidOperation:
    return (1, value)


def _sort_key(row: dict[str, str]) -> tuple[object, ...]:
  """Return the requested stable, ascending sort key for one CSV row."""
  return (
      row["receipt_date"],
      row["merchant"],
      row["item_raw"],
      _quantity_key(row["quantity"]),
      row["unit"],
  )


def sort_csv(input_path: Path, output: TextIO) -> None:
  """Write ``input_path`` sorted by the canonical receipt/item fields."""
  with input_path.open("r", encoding="utf-8", newline="") as source:
    reader = csv.DictReader(source)
    if reader.fieldnames is None:
      raise ValueError(f"CSV has no header: {input_path}")

    missing = [
        field for field in SORT_FIELDS if field not in reader.fieldnames
    ]
    if missing:
      names = ", ".join(missing)
      raise ValueError(f"CSV is missing required sort field(s): {names}")

    rows = list(reader)

  writer = csv.DictWriter(
      output,
      fieldnames=reader.fieldnames,
      lineterminator="\n",
  )
  writer.writeheader()
  writer.writerows(sorted(rows, key=_sort_key))


def main() -> int:
  """Parse command-line arguments and sort the requested CSV."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      "input",
      nargs="?",
      type=Path,
      default=DEFAULT_INPUT,
      help="input CSV (default: data/example_month.csv)",
  )
  parser.add_argument(
      "-o",
      "--output",
      type=Path,
      help="write sorted CSV to this file instead of standard output",
  )
  args = parser.parse_args()

  try:
    if args.output is None:
      sort_csv(args.input, sys.stdout)
    else:
      with args.output.open("w", encoding="utf-8", newline="") as destination:
        sort_csv(args.input, destination)
  except (OSError, ValueError) as error:
    parser.error(str(error))

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
