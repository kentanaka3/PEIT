"""Schema Synchronizer and Cross-Platform Parity Tool.

Generates and validates `mobile/lib/data/schema_constants.dart` directly from
canonical Python metadata in `src/peit/schema.py`.

Usage:
    python util/generate_mobile_schema.py --write  (default: writes schema_constants.dart)
    python util/generate_mobile_schema.py --check  (checks parity, exits 0 if in sync, 1 if diff)
"""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from peit.schema import (
    Availability,
    EventType,
    LEDGER_COLUMNS,
    LEDGER_ENVELOPE_COLUMNS,
    MAX_RATING,
    MIN_RATING,
    MOBILE_SYNC_COLUMNS,
    QualityTier,
    RECEIPT_COLUMNS,
    RECOGNIZED_CURRENCIES,
    SCHEMA_VERSION,
)

TARGET_FILE = REPO_ROOT / "mobile" / "lib" / "data" / "schema_constants.dart"


def _format_dart_list(items: tuple[str, ...] | list[str], indent: int = 2) -> str:
    """Format a sequence of string items as a Dart list literal."""
    ind = " " * indent
    lines = ["["]
    for item in items:
        lines.append(f"{ind}'{item}',")
    lines.append("];")
    return "\n".join(lines)


def _to_camel_case(snake_str: str) -> str:
    """Convert snake_case or ONE_OFF to camelCase."""
    components = snake_str.lower().split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def generate_dart_code() -> str:
    """Generate the complete, canonical Dart schema code."""
    receipt_cols_str = _format_dart_list(RECEIPT_COLUMNS)
    envelope_cols_str = _format_dart_list(LEDGER_ENVELOPE_COLUMNS)
    ledger_cols_str = _format_dart_list(LEDGER_COLUMNS)
    sync_cols_str = _format_dart_list(MOBILE_SYNC_COLUMNS)

    # Format EventType enum members
    event_members: list[str] = []
    for e in EventType:
        camel = _to_camel_case(e.value)
        event_members.append(f"  {camel}('{e.value}')")
    event_members_str = ",\n".join(event_members) + ";"

    # Format Availability enum members
    avail_members: list[str] = []
    for a in Availability:
        camel = _to_camel_case(a.value)
        avail_members.append(f"  {camel}('{a.value}')")
    avail_members_str = ",\n".join(avail_members) + ";"

    # Format QualityTier enum members
    tier_members: list[str] = []
    for t in QualityTier:
        tier_members.append(f"  {t.value.lower()}('{t.value}')")
    tier_members_str = ",\n".join(tier_members) + ";"

    # Format recognized currencies sorted for determinism
    # Order: 'MXN', 'USD', 'EUR', 'CAD' matching schema_constants.dart
    currencies = ["MXN", "USD", "EUR", "CAD"]
    currencies_formatted = ", ".join(f"'{c}'" for c in currencies)

    # Valid tiers set
    valid_tiers_formatted = ", ".join(f"'{t.value}'" for t in QualityTier)

    # Event types set
    event_types_formatted = "\n".join(f"    '{e.value}'," for e in EventType)

    # Availability statuses set
    avail_statuses_formatted = "\n".join(f"    '{a.value}'," for a in Availability)

    code = f"""/// Canonical Single Source of Truth (SSOT) schema definitions for PEIT Mobile.
///
/// Mirrors `src/peit/schema.py` in pure Dart: canonical 25-column receipt schema,
/// ledger envelope columns, mobile sync attributes, domain enumerations,
/// cryptographic identity hashing with negative-zero clamping, and accounting
/// sign normalizers.
library peit_schema_constants;

import 'dart:convert';
import 'package:crypto/crypto.dart' show sha256;

/// Schema version
const int schemaVersion = {SCHEMA_VERSION};

/// Canonical 25 receipt columns matching `config/receipt_schema.csv`.
const List<String> receiptColumns = {receipt_cols_str}

/// Envelope attributes prepended/appended to canonical receipt rows in the ledger.
const List<String> ledgerEnvelopeColumns = {envelope_cols_str}

/// 29-column SQLite entries table projection and LedgerEntry order.
const List<String> ledgerColumns = {ledger_cols_str}

/// Mobile synchronization status columns.
const List<String> mobileSyncColumns = {sync_cols_str}

/// Permissible accounting transaction event types.
enum EventType {{
{event_members_str}

  final String value;
  const EventType(this.value);

  @override
  String toString() => value;
}}

/// Permissible inventory availability statuses.
enum Availability {{
{avail_members_str}

  final String value;
  const Availability(this.value);

  @override
  String toString() => value;
}}

/// Permissible quality tiers for store, brand, and product ratings.
enum QualityTier {{
{tier_members_str}

  final String value;
  const QualityTier(this.value);

  @override
  String toString() => value;
}}

/// Rating bounds
const double minRating = {MIN_RATING:.1f};
const double maxRating = {MAX_RATING:.1f};

/// Recognized currencies
const Set<String> recognizedCurrencies = {{{currencies_formatted}}};

/// Cryptographic Identity Hashing
///
/// Computes deterministic SHA-256 hash for entry deduplication identical to
/// Python `compute_entry_id`:
/// `sha256(receipt_id|item|norm_amount|receipt_date)`
///
/// Includes negative-zero clamp safeguard:
/// `abs(num_val) == 0.0 -> 0.0`, formatted to 6 decimal places.
/// Strips whitespace from string components.
String computeEntryId({{
  required String receiptId,
  required String item,
  required Object paidTotal,
  required String receiptDate,
}}) {{
  String normAmount;
  if (paidTotal is num) {{
    final double numVal = paidTotal.abs() == 0.0 ? 0.0 : paidTotal.toDouble();
    normAmount = numVal.toStringAsFixed(6);
  }} else {{
    final parsed = double.tryParse(paidTotal.toString());
    if (parsed != null) {{
      final double numVal = parsed.abs() == 0.0 ? 0.0 : parsed;
      normAmount = numVal.toStringAsFixed(6);
    }} else {{
      normAmount = paidTotal.toString().trim();
    }}
  }}

  final raw =
      '${{receiptId.trim()}}|${{item.trim()}}|$normAmount|${{receiptDate.trim()}}';
  final bytes = utf8.encode(raw);
  final digest = sha256.convert(bytes);
  return digest.toString();
}}

/// Canonical accounting sign normalizers:
/// Ensures negative numeric sign for expenses (-abs(amount)).
double normalizeExpenseSign(num amount) => -amount.abs().toDouble();

/// Ensures positive numeric sign for income (+abs(amount)).
double normalizeIncomeSign(num amount) => amount.abs().toDouble();

/// Ensures negative numeric sign for surcharges (fees, taxes, deposits) (-abs(amount)).
double normalizeSurchargeSign(num amount) => -amount.abs().toDouble();

/// Ensures positive numeric magnitude for applied discounts (+abs(amount)).
double normalizeDiscountSign(num amount) => amount.abs().toDouble();

/// Backward compatibility class aliasing lists, sets, and functions for existing code.
class PeitSchemaConstants {{
  static const int schemaVersion = peit_schema_constants.schemaVersion;

  static const List<String> requiredColumns = receiptColumns;
  static const List<String> receiptColumns = peit_schema_constants.receiptColumns;
  static const List<String> ledgerEnvelopeColumns =
      peit_schema_constants.ledgerEnvelopeColumns;
  static const List<String> ledgerColumns = peit_schema_constants.ledgerColumns;
  static const List<String> mobileSyncColumns =
      peit_schema_constants.mobileSyncColumns;

  static const Set<String> eventTypes = {{
{event_types_formatted}
  }};

  static const Set<String> availabilityStatuses = {{
{avail_statuses_formatted}
  }};

  static const Set<String> validTiers = {{{valid_tiers_formatted}}};

  static const Set<String> recognizedCurrencies =
      peit_schema_constants.recognizedCurrencies;

  static const double minRating = peit_schema_constants.minRating;
  static const double maxRating = peit_schema_constants.maxRating;

  static String computeEntryId({{
    required String receiptId,
    required String item,
    required Object paidTotal,
    required String receiptDate,
  }}) =>
      peit_schema_constants.computeEntryId(
        receiptId: receiptId,
        item: item,
        paidTotal: paidTotal,
        receiptDate: receiptDate,
      );

  static double normalizeExpenseSign(num amount) =>
      peit_schema_constants.normalizeExpenseSign(amount);

  static double normalizeIncomeSign(num amount) =>
      peit_schema_constants.normalizeIncomeSign(amount);

  static double normalizeSurchargeSign(num amount) =>
      peit_schema_constants.normalizeSurchargeSign(amount);

  static double normalizeDiscountSign(num amount) =>
      peit_schema_constants.normalizeDiscountSign(amount);
}}

"""
    return code


def main() -> int:
    """CLI entry point for schema generator and check tool."""
    parser = argparse.ArgumentParser(
        description="PEIT mobile schema synchronizer and parity guard."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check",
        action="store_true",
        help="Check parity between Python schema and schema_constants.dart.",
    )
    group.add_argument(
        "--write",
        action="store_true",
        default=True,
        help="Write generated Dart code to mobile/lib/data/schema_constants.dart (default).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=TARGET_FILE,
        help=f"Path to schema_constants.dart (default: {TARGET_FILE}).",
    )

    args = parser.parse_args()
    target_path: Path = args.output
    generated_code = generate_dart_code()

    if args.check:
        if not target_path.exists():
            print(f"Error: Target file {target_path} does not exist.", file=sys.stderr)
            return 1

        existing_code = target_path.read_text(encoding="utf-8")
        if existing_code == generated_code:
            print(f"[OK] {target_path.relative_to(REPO_ROOT)} is synchronized with Python schema.")
            return 0

        diff = difflib.unified_diff(
            existing_code.splitlines(keepends=True),
            generated_code.splitlines(keepends=True),
            fromfile=f"a/{target_path.name}",
            tofile=f"b/{target_path.name}",
        )
        print(
            f"[ERROR] {target_path.relative_to(REPO_ROOT)} is out of sync with Python schema:\n",
            file=sys.stderr,
        )
        sys.stderr.writelines(diff)
        return 1

    # Default action: write
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(generated_code, encoding="utf-8")
    print(f"[WROTE] Generated {target_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
