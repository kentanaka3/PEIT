"""Command-line interface for the PEIT prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import audit_append, calculate_indices, read_csv


def main() -> int:
  parser = argparse.ArgumentParser(
      description="Personal Economic Inflation Tracker"
  )
  parser.add_argument("csv", type=Path, help="monthly receipt CSV")
  parser.add_argument(
      "--audit", type=Path, help="append-only JSONL audit path"
  )
  parser.add_argument(
      "--json", action="store_true", help="emit machine-readable JSON"
  )
  args = parser.parse_args()
  rows, issues = read_csv(args.csv)
  if issues:
    for issue in issues:
      print(f"row {issue.row}: {issue.field}: {issue.message}")
    return 2
  if args.audit:
    audit_append(args.audit, rows, str(args.csv))
  report = calculate_indices(rows)
  if args.json:
    print(json.dumps(report, indent=2))
  else:
    print("month | fixed_basket | changing_expenditure | coverage | MoM")
    for item in report:
      print(
          f"{item['month']} | {item['fixed_basket_index']} | "
          f"{item['changing_basket_expenditure_index']} | "
          f"{item['coverage_percent']}% | {item['mom_percent']}"
      )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
