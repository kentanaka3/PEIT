"""Unit test suite for peit.schema (Canonical Single Source of Truth)."""

import csv
import hashlib
from pathlib import Path
import re
import subprocess
import sys

import peit
from peit.schema import (
    CURRENCY_REGEX,
    LEDGER_COLUMNS,
    LEDGER_ENVELOPE_COLUMNS,
    MAX_RATING,
    MIN_RATING,
    MOBILE_SYNC_COLUMNS,
    RECEIPT_COLUMNS,
    RECOGNIZED_CURRENCIES,
    SCHEMA_VERSION,
    Availability,
    ColumnDefinition,
    EventType,
    QualityTier,
    compute_entry_id,
    normalize_discount_sign,
    normalize_expense_sign,
    normalize_income_sign,
    normalize_surcharge_sign,
)
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_SCHEMA_PATH = REPO_ROOT / "config" / "receipt_schema.csv"


# ============================================================================
# Suite 1: Canonical Column Sequences & CSV Parity
# ============================================================================


def test_schema_version():
  """Schema version must be 1."""
  assert SCHEMA_VERSION == 1


def test_receipt_columns_parity_with_csv():
  """RECEIPT_COLUMNS must strictly match header of config/receipt_schema.csv."""
  assert CSV_SCHEMA_PATH.exists(), f"Missing CSV schema at {CSV_SCHEMA_PATH}"
  with open(CSV_SCHEMA_PATH, "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)

  # Check exact length 25
  assert len(RECEIPT_COLUMNS) == 25
  assert len(header) == 25

  # Check exact sequence and order
  assert RECEIPT_COLUMNS == tuple(header)


def test_ledger_columns_structure():
  """LEDGER_COLUMNS has exactly 29 columns matching SQLite entries projection."""
  assert len(LEDGER_COLUMNS) == 29
  assert len(LEDGER_ENVELOPE_COLUMNS) == 4

  # Envelope columns
  assert LEDGER_ENVELOPE_COLUMNS == (
      "entry_id",
      "month",
      "account",
      "recorded_at",
  )

  # Check that all RECEIPT_COLUMNS exist in LEDGER_COLUMNS
  for col in RECEIPT_COLUMNS:
    assert col in LEDGER_COLUMNS, f"Missing receipt column in ledger: {col}"

  # Check that all LEDGER_ENVELOPE_COLUMNS exist in LEDGER_COLUMNS
  for col in LEDGER_ENVELOPE_COLUMNS:
    assert col in LEDGER_COLUMNS, f"Missing envelope column in ledger: {col}"

  # Exact layout check:
  expected_ledger_layout = (
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
  assert LEDGER_COLUMNS == expected_ledger_layout


def test_mobile_sync_columns():
  """MOBILE_SYNC_COLUMNS contains sync status attributes."""
  assert MOBILE_SYNC_COLUMNS == ("is_synced", "synced_at")


# ============================================================================
# Suite 2: Domain Enumerations & Boundaries
# ============================================================================


def test_event_type_enumeration():
  """EventType enumeration contains all valid domain types."""
  expected_events = {"recurring", "one_off", "transfer", "refund", "income"}
  enum_values = {e.value for e in EventType}
  assert enum_values == expected_events

  assert EventType.RECURRING == "recurring"
  assert EventType.ONE_OFF == "one_off"
  assert EventType.TRANSFER == "transfer"
  assert EventType.REFUND == "refund"
  assert EventType.INCOME == "income"


def test_availability_enumeration():
  """Availability enumeration contains all inventory states."""
  expected_avail = {"in_stock", "low_stock", "out_of_stock", "discontinued"}
  enum_values = {a.value for a in Availability}
  assert enum_values == expected_avail

  assert Availability.IN_STOCK == "in_stock"
  assert Availability.LOW_STOCK == "low_stock"
  assert Availability.OUT_OF_STOCK == "out_of_stock"
  assert Availability.DISCONTINUED == "discontinued"


def test_quality_tier_enumeration():
  """QualityTier enumeration contains standard A-E tiers."""
  expected_tiers = {"A", "B", "C", "D", "E"}
  enum_values = {t.value for t in QualityTier}
  assert enum_values == expected_tiers

  assert QualityTier.A == "A"
  assert QualityTier.B == "B"
  assert QualityTier.C == "C"
  assert QualityTier.D == "D"
  assert QualityTier.E == "E"


def test_rating_bounds():
  """Rating boundaries are 1.0 to 5.0."""
  assert MIN_RATING == 1.0
  assert MAX_RATING == 5.0


def test_recognized_currencies():
  """Recognized currencies frozenset and regex pattern."""
  assert RECOGNIZED_CURRENCIES == frozenset({"MXN", "USD", "EUR", "CAD"})
  for curr in ["MXN", "USD", "EUR", "CAD", "gbp", "JPY"]:
    assert CURRENCY_REGEX.match(curr) is not None
  assert CURRENCY_REGEX.match("US") is None
  assert CURRENCY_REGEX.match("USDT") is None
  assert CURRENCY_REGEX.match("123") is None


# ============================================================================
# Suite 3: Cryptographic Identity Hashing & Safeguards
# ============================================================================


def test_compute_entry_id_consistency_and_vectors():
  """compute_entry_id matches known vectors and ledger behavior."""
  # Vector from test_ledger.py
  h1 = compute_entry_id("rec-01", "milk 1 l", -2.5, "2026-01-15")
  h2 = compute_entry_id("rec-01", "milk 1 l", "-2.50", "2026-01-15")
  h3 = compute_entry_id("rec-01", "milk 1 l", -2.500000, "2026-01-15")
  assert h1 == h2 == h3
  assert len(h1) == 64

  # Expected SHA-256 calculation verification
  seed = b"rec-01|milk 1 l|-2.500000|2026-01-15"
  expected_sha = hashlib.sha256(seed).hexdigest()
  assert h1 == expected_sha


def test_compute_entry_id_mobile_sync_vectors():
  """compute_entry_id matches test_mobile_sync vectors."""
  test_cases = [
      ("rec-001", "milk 1 l", -2.50, "2026-01-15"),
      ("rec-002", "pan blanco 500g", -49.0, "2026-02-01"),
      ("rec-003", "manzana kg", -32.555555, "2026-03-10"),
      ("rec-004", "salary payment", 15000.0, "2026-04-01"),
  ]
  for receipt_id, item, paid_total, receipt_date in test_cases:
    expected_seed = (
        f"{receipt_id.strip()}|{item.strip()}|"
        f"{float(paid_total):.6f}|{receipt_date.strip()}".encode("utf-8")
    )
    expected_hash = hashlib.sha256(expected_seed).hexdigest()
    assert (
        compute_entry_id(receipt_id, item, paid_total, receipt_date)
        == expected_hash
    )


def test_compute_entry_id_negative_zero_clamping():
  """Negative zero (-0.0) is clamped to 0.0 to prevent hash diverging."""
  h_neg_zero = compute_entry_id("r1", "sample item", -0.0, "2026-01-01")
  h_pos_zero = compute_entry_id("r1", "sample item", 0.0, "2026-01-01")
  h_str_zero = compute_entry_id("r1", "sample item", "0", "2026-01-01")
  h_int_zero = compute_entry_id("r1", "sample item", 0, "2026-01-01")

  assert h_neg_zero == h_pos_zero
  assert h_neg_zero == h_str_zero
  assert h_neg_zero == h_int_zero

  seed = b"r1|sample item|0.000000|2026-01-01"
  assert h_neg_zero == hashlib.sha256(seed).hexdigest()


def test_compute_entry_id_fallback_on_unparseable_amount():
  """Fallback handles unparseable string amounts by stripping whitespace."""
  h = compute_entry_id("r1", "sample", "invalid_amount  ", "2026-01-01")
  seed = b"r1|sample|invalid_amount|2026-01-01"
  assert h == hashlib.sha256(seed).hexdigest()


# ============================================================================
# Suite 4: Accounting Sign Normalizers
# ============================================================================


def test_sign_normalizers():
  """Verify financial sign normalization conventions."""
  # Expenses must be negative (-abs)
  assert normalize_expense_sign(25.50) == -25.50
  assert normalize_expense_sign(-25.50) == -25.50
  assert normalize_expense_sign(0.0) == 0.0

  # Income must be positive (+abs)
  assert normalize_income_sign(1500.0) == 1500.0
  assert normalize_income_sign(-1500.0) == 1500.0
  assert normalize_income_sign(0.0) == 0.0

  # Surcharges (taxes, fees, deposits) must be negative (-abs)
  assert normalize_surcharge_sign(2.5) == -2.5
  assert normalize_surcharge_sign(-2.5) == -2.5
  assert normalize_surcharge_sign(0.0) == 0.0

  # Discounts must be positive (+abs)
  assert normalize_discount_sign(5.0) == 5.0
  assert normalize_discount_sign(-5.0) == 5.0
  assert normalize_discount_sign(0.0) == 0.0


# ============================================================================
# Suite 5: Package Re-exports & ColumnDefinition
# ============================================================================


def test_package_reexports():
  """All schema symbols are cleanly re-exported in peit namespace."""
  assert peit.RECEIPT_COLUMNS == RECEIPT_COLUMNS
  assert peit.LEDGER_COLUMNS == LEDGER_COLUMNS
  assert peit.EventType is EventType
  assert peit.Availability is Availability
  assert peit.QualityTier is QualityTier
  assert peit.compute_entry_id is compute_entry_id


def test_column_definition():
  """ColumnDefinition dataclass instantiation."""
  col = ColumnDefinition(
      name="paid_total",
      dtype=float,
      sqlite_type="REAL",
      is_required=True,
      default=0.0,
      description="Net total paid amount",
  )
  assert col.name == "paid_total"
  assert col.sqlite_type == "REAL"
  assert col.is_required is True


# ============================================================================
# Suite 6: Cross-Platform Dart Parity & Synchronizer Tool
# ============================================================================


DART_SCHEMA_PATH = REPO_ROOT / "mobile" / "lib" / "data" / "schema_constants.dart"
DART_TEST_PATH = REPO_ROOT / "mobile" / "test" / "schema_constants_test.dart"


def _parse_dart_list(content: str, variable_name: str) -> list[str]:
  """Parse a List<String> constant from Dart source code."""
  pattern = rf"const\s+List<String>\s+{variable_name}\s*=\s*\[(.*?)\];"
  match = re.search(pattern, content, re.DOTALL)
  assert match, f"Could not find Dart list '{variable_name}'"
  raw_items = match.group(1)
  items = [
      item.strip().strip("'\"")
      for item in raw_items.split(",")
      if item.strip()
  ]
  return items


def _parse_dart_enum_values(content: str, enum_name: str) -> set[str]:
  """Parse string values of a Dart enum definition."""
  pattern = rf"enum\s+{enum_name}\s*\{{(.*?)\n\s*final\s+String\s+value;"
  match = re.search(pattern, content, re.DOTALL)
  assert match, f"Could not find Dart enum '{enum_name}'"
  raw_body = match.group(1)
  values = re.findall(r"\w+\(['\"]([^'\"]+)['\"]\)", raw_body)
  return set(values)


def test_cross_platform_dart_receipt_columns():
  """mobile/lib/data/schema_constants.dart receiptColumns strictly matches RECEIPT_COLUMNS."""
  assert DART_SCHEMA_PATH.exists(), f"Missing Dart schema at {DART_SCHEMA_PATH}"
  dart_content = DART_SCHEMA_PATH.read_text(encoding="utf-8")
  dart_receipt_columns = _parse_dart_list(dart_content, "receiptColumns")

  # Exact 25 items, exact names, exact order
  assert len(dart_receipt_columns) == 25
  assert len(dart_receipt_columns) == len(RECEIPT_COLUMNS)
  assert tuple(dart_receipt_columns) == RECEIPT_COLUMNS


def test_cross_platform_dart_ledger_columns():
  """mobile/lib/data/schema_constants.dart ledgerColumns strictly matches LEDGER_COLUMNS."""
  assert DART_SCHEMA_PATH.exists(), f"Missing Dart schema at {DART_SCHEMA_PATH}"
  dart_content = DART_SCHEMA_PATH.read_text(encoding="utf-8")
  dart_ledger_columns = _parse_dart_list(dart_content, "ledgerColumns")

  # Exact 29 items, exact order
  assert len(dart_ledger_columns) == 29
  assert len(dart_ledger_columns) == len(LEDGER_COLUMNS)
  assert tuple(dart_ledger_columns) == LEDGER_COLUMNS


def test_cross_platform_dart_enums():
  """Dart enums EventType, Availability, and QualityTier match Python enums."""
  assert DART_SCHEMA_PATH.exists(), f"Missing Dart schema at {DART_SCHEMA_PATH}"
  dart_content = DART_SCHEMA_PATH.read_text(encoding="utf-8")

  # EventType (5)
  dart_event_types = _parse_dart_enum_values(dart_content, "EventType")
  python_event_types = {e.value for e in EventType}
  assert len(dart_event_types) == 5
  assert dart_event_types == python_event_types

  # Availability (4)
  dart_availabilities = _parse_dart_enum_values(dart_content, "Availability")
  python_availabilities = {a.value for a in Availability}
  assert len(dart_availabilities) == 4
  assert dart_availabilities == python_availabilities

  # QualityTier (5)
  dart_tiers = _parse_dart_enum_values(dart_content, "QualityTier")
  python_tiers = {t.value for t in QualityTier}
  assert len(dart_tiers) == 5
  assert dart_tiers == python_tiers


def test_cross_platform_dart_bounds():
  """Dart rating bounds (1.0, 5.0) and recognized currencies match Python schema."""
  assert DART_SCHEMA_PATH.exists(), f"Missing Dart schema at {DART_SCHEMA_PATH}"
  dart_content = DART_SCHEMA_PATH.read_text(encoding="utf-8")

  # Rating bounds
  min_match = re.search(r"const\s+double\s+minRating\s*=\s*([0-9.]+);", dart_content)
  max_match = re.search(r"const\s+double\s+maxRating\s*=\s*([0-9.]+);", dart_content)
  assert min_match and float(min_match.group(1)) == MIN_RATING == 1.0
  assert max_match and float(max_match.group(1)) == MAX_RATING == 5.0

  # Currencies
  curr_match = re.search(
      r"const\s+Set<String>\s+recognizedCurrencies\s*=\s*\{(.*?)\};",
      dart_content,
  )
  assert curr_match
  dart_currencies = {
      c.strip().strip("'\"")
      for c in curr_match.group(1).split(",")
      if c.strip()
  }
  assert dart_currencies == set(RECOGNIZED_CURRENCIES) == {"MXN", "USD", "EUR", "CAD"}


def test_cross_platform_hash_parity_vectors():
  """Python compute_entry_id matches all test vectors from mobile schema test."""
  # Vector 1: milk 1 l
  assert (
      compute_entry_id("rec-01", "milk 1 l", -2.5, "2026-01-15")
      == compute_entry_id("rec-01", "milk 1 l", "-2.50", "2026-01-15")
      == compute_entry_id("rec-01", "milk 1 l", -2.500000, "2026-01-15")
  )

  # Vector 2: mobile sync test vectors
  assert (
      compute_entry_id("rec-001", "milk 1 l", -2.50, "2026-01-15")
      == "90b55482be333df935738569bf6eff4180c6f5fa9d8b265dab3bca3f700c97f1"
  )
  assert (
      compute_entry_id("rec-004", "salary payment", 15000.0, "2026-04-01")
      == "ff99bb83a577f8691107e2e939b49207de0b11bf335665a3ed8fef8a72a37fc2"
  )

  # Vector 3: negative-zero clamping vector
  neg_zero_expected = "2b4e8d7009cc014ecbf3a7886f7dbcc493975fceadd64acf3c0ae63824b9f1a3"
  assert compute_entry_id("r1", "sample item", -0.0, "2026-01-01") == neg_zero_expected
  assert compute_entry_id("r1", "sample item", 0.0, "2026-01-01") == neg_zero_expected
  assert compute_entry_id("r1", "sample item", "0", "2026-01-01") == neg_zero_expected
  assert compute_entry_id("r1", "sample item", 0, "2026-01-01") == neg_zero_expected


def test_schema_synchronizer_tool_check_clean():
  """util/generate_mobile_schema.py --check exits 0 on synchronized schema."""
  import subprocess

  cmd = [sys.executable, str(REPO_ROOT / "util" / "generate_mobile_schema.py"), "--check"]
  result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
  assert result.returncode == 0, f"Check failed: {result.stderr or result.stdout}"
