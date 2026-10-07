"""
Command-line interface and system integration for PEIT Profiler.

Supports generating synthetic receipt datasets from Profile and Market
definitions, exporting to Schema CSV, emitting ground truth manifests, and
adapting Schema rows for import into the existing PEIT transaction ledger.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, TextIO

from peit.ledger import LedgerDatabase, LedgerEntry, compute_entry_id
from peit.profiler.market import Market
from peit.profiler.profile import Profile

from peit.profiler.generator import HEADERS


def write_csv(
    rows: list[dict[str, Any]], out_dest: TextIO | Path | str
) -> None:
  """
  Write receipts to CSV using exact Schema 19 columns with csv.DictWriter.
  """
  if isinstance(out_dest, (str, Path)):
    out_path = Path(out_dest)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
      writer = csv.DictWriter(f, fieldnames=HEADERS)
      writer.writeheader()
      for row in rows:
        writer.writerow({k: row.get(k, "") for k in HEADERS})
  else:
    writer = csv.DictWriter(out_dest, fieldnames=HEADERS)
    writer.writeheader()
    for row in rows:
      writer.writerow({k: row.get(k, "") for k in HEADERS})


def write_manifest(
    manifest: dict[str, Any], manifest_path: Path | str
) -> None:
  """Write ground truth manifest to JSON file with indent=2."""
  p = Path(manifest_path)
  p.parent.mkdir(parents=True, exist_ok=True)
  with p.open("w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")


def import_to_ledger(
    rows: list[dict[str, Any]],
    ledger_path: Path | str,
    output_csv: Path | str | None = None,
    account: str = "default:checking",
) -> tuple[int, int]:
    """Convert Schema v2 receipt rows into native LedgerEntry objects and import into ledger.

    Adapts Schema v2 fields to Schema v1 LedgerEntry:
      month = row["receipt_date"][:7]
      source_file = Path(output_csv).name if output_csv else "profiler.csv"
      item_raw = row["description"]
      item_normalized = row["item"]
      shelf_unit_price = float(row["unit_price"])
    and calls LedgerDatabase(ledger_path).append_entries(entries).
    """
    source_filename = Path(output_csv).name if output_csv else "profiler.csv"
    now_iso = datetime.now(timezone.utc).isoformat()
    entries: list[LedgerEntry] = []

    for row in rows:
        receipt_date = str(row["receipt_date"])
        month = receipt_date[:7]
        item_raw = str(row["description"])
        item_normalized = str(row["item"])
        shelf_unit_price = float(row["unit_price"])
        paid_total = float(row["paid_total"])
        receipt_id = str(row["receipt_id"])

        entry_id = compute_entry_id(
            source_file=source_filename,
            receipt_id=receipt_id,
            item_normalized=item_normalized,
            paid_total=paid_total,
            receipt_date=receipt_date,
        )

        entry = LedgerEntry(
            entry_id=entry_id,
            month=month,
            receipt_id=receipt_id,
            receipt_date=receipt_date,
            account=str(row.get("account") or account),
            merchant=str(row["merchant"]),
            item_raw=item_raw,
            item_normalized=item_normalized,
            category=str(row["category"]),
            quantity=float(row["quantity"]),
            unit=str(row["unit"]),
            shelf_unit_price=shelf_unit_price,
            currency=str(row["currency"]),
            discount=float(row.get("discount", 0.0) or 0.0),
            fee=float(row.get("fee", 0.0) or 0.0),
            tax=float(row.get("tax", 0.0) or 0.0),
            deposit=float(row.get("deposit", 0.0) or 0.0),
            paid_total=paid_total,
            event_type=str(row["event_type"]),
            source_file=source_filename,
            notes=str(row.get("notes") or ""),
            recorded_at=now_iso,
        )
        entries.append(entry)

  ledger_p = Path(ledger_path)
  if ledger_p.suffix == ".db":
    ledger_p = ledger_p.with_suffix(".jsonl")
  db = LedgerDatabase(ledger_p)
  return db.append_entries(entries)


def _add_generate_arguments(p: argparse.ArgumentParser) -> None:
  p.add_argument(
      "--profile",
      type=Path,
      required=True,
      help="Path to Profile JSON file (required)",
  )
  p.add_argument(
      "--market",
      type=Path,
      required=True,
      help="Path to Market JSON file (required)",
  )
  p.add_argument(
      "--seed",
      type=int,
      default=None,
      help="Optional integer seed for reproducible generation",
  )
  p.add_argument(
      "-o",
      "--output",
      type=Path,
      default=None,
      help="Path to output CSV file (default: stdout or receipts.csv)",
  )
  p.add_argument(
      "--manifest",
      type=Path,
      default=None,
      help="Optional path to output ground_truth.json manifest",
  )
  p.add_argument(
      "--import-ledger",
      type=Path,
      default=None,
      help="Optional path to SQLite/JSONL ledger to import into",
  )


def build_parser() -> argparse.ArgumentParser:
  """
  Construct argument parser supporting 'generate' sub-command and direct flags.
  """
  parser = argparse.ArgumentParser(
      prog="peit.profiler",
      description="PEIT Profile × Market Synthetic Receipt Generator.",
  )
  subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
  gen_parser = subparsers.add_parser(
      "generate",
      help="Generate synthetic receipts from Profile and Market JSON definitions.",
  )
  _add_generate_arguments(gen_parser)
  return parser


def main(argv: list[str] | None = None) -> int:
  """Main CLI entry point."""
  if argv is None:
    argv = sys.argv[1:]

  effective_argv = list(argv)
  if not effective_argv:
    parser = build_parser()
    parser.print_help(sys.stderr)
    return 2

  # Support running directly with flags (e.g.
  #   python -m peit.profiler --profile ...
  # )
  first = effective_argv[0]
  if first not in ("generate", "-h", "--help", "-v", "--version"):
    effective_argv.insert(0, "generate")

  parser = build_parser()
  try:
    args = parser.parse_args(effective_argv)
  except SystemExit as e:
    return e.code if isinstance(e.code, int) else 2

  if not hasattr(args, "command") or args.command != "generate":
    parser.print_help(sys.stderr)
    return 2

  if not args.profile.exists():
    sys.stderr.write(f"Error: Profile file not found: {args.profile}\n")
    return 2

  if not args.market.exists():
    sys.stderr.write(f"Error: Market file not found: {args.market}\n")
    return 2

  try:
    profile = Profile.from_json(args.profile)
  except Exception as e:
    sys.stderr.write(f"Error loading profile from {args.profile}: {e}\n")
    return 2

  try:
    market = Market.from_json(args.market)
  except Exception as e:
    sys.stderr.write(f"Error loading market from {args.market}: {e}\n")
    return 2

  try:
    from peit.profiler.generator import generate
    rows, manifest = generate(profile=profile, market=market, seed=args.seed)
  except Exception as e:
    sys.stderr.write(f"Error during receipt generation: {e}\n")
    return 2

  try:
    if args.output:
      write_csv(rows, args.output)
    else:
      write_csv(rows, sys.stdout)
  except Exception as e:
    sys.stderr.write(f"Error writing CSV output: {e}\n")
    return 2

  if args.manifest:
    try:
      write_manifest(manifest, args.manifest)
    except Exception as e:
      sys.stderr.write(f"Error writing manifest: {e}\n")
      return 2

  if args.import_ledger:
    try:
      imported, skipped = import_to_ledger(
          rows=rows,
          ledger_path=args.import_ledger,
          output_csv=args.output,
      )
      if args.output:
        print(
            f"Imported {imported} rows, skipped {skipped} duplicates into "
            f"ledger: {args.import_ledger}"
        )
      else:
        sys.stderr.write(
            f"Imported {imported} rows, skipped {skipped} duplicates into "
            f"ledger: {args.import_ledger}\n"
        )
    except Exception as e:
      sys.stderr.write(
          f"Error importing into ledger {args.import_ledger}: {e}\n"
      )
      return 2

  return 0
