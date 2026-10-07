"""Unit and integration test suite for peit.ledger."""

from peit.ledger import (
    LedgerDatabase,
    LedgerEntry,
    add_entry,
    compute_entry_id,
    get_balance,
    get_category_breakdown,
    import_csv,
    list_entries,
)
import json
import sqlite3
import sys
import time
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


# ============================================================================
# Suite 1: Data Modeling, Serialization & Hashing
# ============================================================================


def test_t1_1_deterministic_entry_id_consistency():
  """T1.1: Consistent SHA-256 hash for fixed fields."""
  h1 = compute_entry_id("rec-01", "milk 1 l", -2.5, "2026-01-15")
  h2 = compute_entry_id("rec-01", "milk 1 l", -2.5, "2026-01-15")
  assert h1 == h2
  assert len(h1) == 64
  assert isinstance(h1, str)


def test_t1_2_numeric_formatting_normalization_in_hashing():
  """
  T1.2: Normalizes numeric values (e.g., -2.5, -2.50, -2.500) to produce same
  ID.
  """
  h1 = compute_entry_id("rec-01", "milk 1 l", -2.5, "2026-01-15")
  h2 = compute_entry_id("rec-01", "milk 1 l", "-2.50", "2026-01-15")
  h3 = compute_entry_id("rec-01", "milk 1 l", -2.500000, "2026-01-15")
  assert h1 == h2 == h3


def test_t1_3_hash_collision_and_sensitivity():
  """T1.3: Mutating any field produces a distinctly different entry_id."""
  base = ("rec-01", "milk 1 l", -2.5, "2026-01-15")
  base_id = compute_entry_id(*base)

  diff_rec = compute_entry_id("rec-02", "milk 1 l", -2.5, "2026-01-15")
  diff_item = compute_entry_id("rec-01", "bread", -2.5, "2026-01-15")
  diff_amount = compute_entry_id("rec-01", "milk 1 l", -3.5, "2026-01-15")
  diff_date = compute_entry_id("rec-01", "milk 1 l", -2.5, "2026-01-16")

  ids = {base_id, diff_rec, diff_item, diff_amount, diff_date}
  assert len(ids) == 5


def test_t1_4_serialization_roundtrip():
  """T1.4: Serialization via to_dict() and deserialization via from_dict()."""
  entry = LedgerEntry(
      entry_id="abc123hash",
      receipt_id="rec-001",
      receipt_date="2026-01-15",
      account="default:checking",
      merchant="Example Market",
      description="Milk 1 L",
      item="milk 1 l",
      brand="Lala",
      category="Food and beverages",
      quantity=2.0,
      pack_size=1.0,
      unit="L",
      unit_price=2.50,
      currency="MXN",
      discount=0.0,
      fee=0.0,
      tax=0.0,
      deposit=0.0,
      paid_total=-5.00,
      event_type="recurring",
      store_tier="A",
      store_rating=5.0,
      brand_tier="B",
      brand_rating=4.5,
      product_tier="C",
      product_rating=4.0,
      notes="Weekly groceries",
      recorded_at="2026-01-15T12:00:00+00:00",
  )
  d = entry.to_dict()
  roundtrip = LedgerEntry.from_dict(d)
  assert entry == roundtrip
  assert roundtrip.month == "2026-01"
  assert isinstance(roundtrip.quantity, float)
  assert isinstance(roundtrip.pack_size, float)
  assert isinstance(roundtrip.unit_price, float)
  assert isinstance(roundtrip.paid_total, float)
  assert roundtrip.store_tier == "A"
  assert roundtrip.store_rating == 5.0
  assert roundtrip.brand_tier == "B"
  assert roundtrip.brand_rating == 4.5
  assert roundtrip.product_tier == "C"
  assert roundtrip.product_rating == 4.0
  assert roundtrip.tier == "C"
  assert roundtrip.rating == 4.0
  assert isinstance(roundtrip.product_rating, float)


# ============================================================================
# Suite 2: Dual Storage Backend & SQLite Cache Projection
# ============================================================================


def test_t2_1_initial_storage_creation(tmp_path):
  """T2.1: Creates both .jsonl and .db with schema upon writing first entry."""
  ledger_file = tmp_path / "ledger.jsonl"
  db_file = tmp_path / "ledger.db"
  assert not ledger_file.exists()
  assert not db_file.exists()

  db = LedgerDatabase(ledger_file)
  assert db_file.exists()

  conn = sqlite3.connect(str(db_file))
  cur = conn.cursor()
  tables = {r[0] for r in cur.execute(
      "SELECT name FROM sqlite_master WHERE type='table'"
  )}
  assert "entries" in tables
  assert "meta" in tables

  columns = {r[1] for r in cur.execute("PRAGMA table_info(entries)")}
  expected = {
      "entry_id", "month", "receipt_id", "receipt_date", "account", "merchant",
      "description", "item", "brand", "category", "quantity", "pack_size",
      "unit", "unit_price", "currency", "discount", "fee", "tax", "deposit",
      "paid_total", "event_type", "store_tier", "store_rating", "brand_tier",
      "brand_rating", "product_tier", "product_rating", "notes", "recorded_at"
  }
  assert columns == expected
  assert "item_raw" not in columns
  assert "shelf_unit_price" not in columns
  assert "source_file" not in columns
  conn.close()


def test_t2_2_dual_write_atomicity_and_consistency(tmp_path):
  """T2.2: Writing entries keeps both jsonl and sqlite row counts in sync with meta."""
  ledger_file = tmp_path / "ledger.jsonl"
  db = LedgerDatabase(ledger_file)

  entries = [
      LedgerEntry(
          entry_id=f"hash_{i}",
          receipt_id=f"rec-{i}",
          receipt_date="2026-01-10",
          account="default:checking",
          merchant="Shop",
          description="Item",
          item="item",
          brand="Brand",
          category="General",
          quantity=1.0,
          pack_size=1.0,
          unit="unit",
          unit_price=10.0,
          currency="MXN",
          discount=0.0,
          fee=0.0,
          tax=0.0,
          deposit=0.0,
          paid_total=-10.0,
          event_type="recurring",
          store_tier="A",
          store_rating=5.0,
          brand_tier="A",
          brand_rating=5.0,
          product_tier="A",
          product_rating=5.0,
          notes="",
          recorded_at="2026-01-10T00:00:00+00:00",
      )
      for i in range(10)
  ]
  imp, skip = db.append_entries(entries)
  assert imp == 10
  assert skip == 0

  # Verify JSONL lines
  with ledger_file.open("r") as f:
    lines = [line for line in f if line.strip()]
  assert len(lines) == 10

  # Verify SQLite rows & meta
  conn = sqlite3.connect(str(db.db_path))
  cur = conn.cursor()
  assert cur.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 10
  assert cur.execute(
      "SELECT value FROM meta WHERE key='entry_count'"
  ).fetchone()[0] == "10"
  conn.close()


def test_t2_3_staleness_detection_on_external_jsonl_append(tmp_path):
  """T2.3: Out-of-band JSONL edit is auto-detected and projected into SQLite."""
  ledger_file = tmp_path / "ledger.jsonl"
  db = LedgerDatabase(ledger_file)

  entry1 = LedgerEntry(
      entry_id="hash_1",
      receipt_id="rec-1",
      receipt_date="2026-01-10",
      account="default:checking",
      merchant="Shop",
      description="Item",
      item="item",
      brand="Brand",
      category="General",
      quantity=1.0,
      pack_size=1.0,
      unit="unit",
      unit_price=10.0,
      currency="MXN",
      discount=0.0,
      fee=0.0,
      tax=0.0,
      deposit=0.0,
      paid_total=-10.0,
      event_type="recurring",
      store_tier="A",
      store_rating=5.0,
      brand_tier="A",
      brand_rating=5.0,
      product_tier="A",
      product_rating=5.0,
      notes="",
      recorded_at="2026-01-10T00:00:00+00:00",
  )
  db.append_entries([entry1])
  assert len(db.list_entries()) == 1

  # Sleep slightly to ensure mtime change
  time.sleep(0.05)

  # Directly append 3 entries to JSONL
  with ledger_file.open("a") as f:
    for i in range(2, 5):
      e = LedgerEntry(
          entry_id=f"hash_{i}",
          receipt_id=f"rec-{i}",
          receipt_date="2026-01-10",
          account="default:checking",
          merchant="Shop",
          description="Item",
          item="item",
          brand="Brand",
          category="General",
          quantity=1.0,
          pack_size=1.0,
          unit="unit",
          unit_price=10.0,
          currency="MXN",
          discount=0.0,
          fee=0.0,
          tax=0.0,
          deposit=0.0,
          paid_total=-10.0,
          event_type="recurring",
          store_tier="A",
          store_rating=5.0,
          brand_tier="A",
          brand_rating=5.0,
          product_tier="A",
          product_rating=5.0,
          notes="",
          recorded_at="2026-01-10T00:00:00+00:00",
      )
      f.write(json.dumps(e.to_dict()) + "\n")

  # Next read query should auto-detect and sync
  entries_read = db.list_entries()
  assert len(entries_read) == 4


def test_t2_4_corrupted_or_deleted_cache_recovery(tmp_path):
  """T2.4: Corrupted or deleted SQLite cache is regenerated seamlessly on query."""
  ledger_file = tmp_path / "ledger.jsonl"
  db_file = tmp_path / "ledger.db"
  db = LedgerDatabase(ledger_file)

  entry = LedgerEntry(
      entry_id="hash_recov",
      receipt_id="rec-1",
      receipt_date="2026-01-10",
      account="default:checking",
      merchant="Shop",
      description="Item",
      item="item",
      brand="Brand",
      category="General",
      quantity=1.0,
      pack_size=1.0,
      unit="unit",
      unit_price=10.0,
      currency="MXN",
      discount=0.0,
      fee=0.0,
      tax=0.0,
      deposit=0.0,
      paid_total=-10.0,
      event_type="recurring",
      store_tier="A",
      store_rating=5.0,
      brand_tier="A",
      brand_rating=5.0,
      product_tier="A",
      product_rating=5.0,
      notes="",
      recorded_at="2026-01-10T00:00:00+00:00",
  )
  db.append_entries([entry])
  assert len(db.list_entries()) == 1

  # Scenario A: Deleted DB file
  db_file.unlink()
  assert not db_file.exists()
  recovered_entries = db.list_entries()
  assert len(recovered_entries) == 1
  assert db_file.exists()

  # Scenario B: Corrupted DB file
  with db_file.open("wb") as f:
    f.write(b"GARBAGE_CORRUPTED_SQLITE_DATA")
  recovered_again = db.list_entries()
  assert len(recovered_again) == 1


def test_t2_5_explicit_cache_rebuild(tmp_path):
  """T2.5: rebuild_cache() explicitly recreates SQLite DB and meta from JSONL."""
  ledger_file = tmp_path / "ledger.jsonl"
  db = LedgerDatabase(ledger_file)

  entry = LedgerEntry(
      entry_id="hash_exp",
      receipt_id="rec-1",
      receipt_date="2026-01-10",
      account="default:checking",
      merchant="Shop",
      description="Item",
      item="item",
      brand="Brand",
      category="General",
      quantity=1.0,
      pack_size=1.0,
      unit="unit",
      unit_price=10.0,
      currency="MXN",
      discount=0.0,
      fee=0.0,
      tax=0.0,
      deposit=0.0,
      paid_total=-10.0,
      event_type="recurring",
      store_tier="A",
      store_rating=5.0,
      brand_tier="A",
      brand_rating=5.0,
      product_tier="A",
      product_rating=5.0,
      notes="",
      recorded_at="2026-01-10T00:00:00+00:00",
  )
  db.append_entries([entry])

  db.rebuild_cache()
  conn = sqlite3.connect(str(db.db_path))
  cur = conn.cursor()
  assert cur.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 1
  assert cur.execute(
      "SELECT value FROM meta WHERE key='entry_count'"
  ).fetchone()[0] == "1"
  conn.close()


# ============================================================================
# Suite 3: CSV Ingestion, Deduplication & Idempotency
# ============================================================================


def test_t3_1_and_t3_2_csv_ingestion_and_idempotency(tmp_path):
  """T3.1 & T3.2: Ingests CSV and re-importing is strictly idempotent."""
  example_csv = Path(__file__).parents[1] / "data" / "example_month.csv"
  ledger_file = tmp_path / "test_ledger.jsonl"

  imported, skipped = import_csv(ledger_file, example_csv)
  assert imported > 0
  assert skipped == 0

  # Re-importing exact same CSV
  re_imported, re_skipped = import_csv(ledger_file, example_csv)
  assert re_imported == 0
  assert re_skipped == imported

  # Check that imported entries have Schema fields
  entries = list_entries(ledger_file)
  assert len(entries) == imported
  first = entries[0]
  assert hasattr(first, "description")
  assert hasattr(first, "item")
  assert hasattr(first, "brand")
  assert hasattr(first, "pack_size")
  assert hasattr(first, "unit_price")
  assert hasattr(first, "store_tier")
  assert hasattr(first, "store_rating")
  assert hasattr(first, "brand_tier")
  assert hasattr(first, "brand_rating")
  assert hasattr(first, "product_tier")
  assert hasattr(first, "product_rating")
  assert first.store_tier in {"A", "B", "C", "D", "E"}
  assert 1.0 <= first.store_rating <= 5.0
  assert first.month == first.receipt_date[:7]


def test_t3_3_partial_duplicate_csv(tmp_path):
  """T3.3: CSV with 4 existing and 3 new rows imports exactly 3 and skips 4."""
  ledger_file = tmp_path / "test_ledger.jsonl"
  db = LedgerDatabase(ledger_file)

  # Create a small CSV with 7 rows in 25-column schema
  csv_file = tmp_path / "partial.csv"
  header = "receipt_id,receipt_date,merchant,description,item,brand,category,quantity,pack_size,unit,unit_price,currency,discount,fee,tax,deposit,paid_total,event_type,store_tier,store_rating,brand_tier,brand_rating,product_tier,product_rating,notes\n"
  rows = [
      f"rec-{i:03d},2026-01-10,Merchant,Item {i},item {i},Brand,Category,1,1,piece,10.00,MXN,0,0,0,0,-10.00,recurring,A,5.0,A,5.0,A,5.0,\n"
      for i in range(1, 8)
  ]
  csv_file.write_text(header + "".join(rows))

  # Import first 4 manually into ledger
  first_4 = [
      LedgerEntry(
          entry_id=compute_entry_id(
              f"rec-{i:03d}", f"item {i}", -10.0, "2026-01-10"
          ),
          receipt_id=f"rec-{i:03d}",
          receipt_date="2026-01-10",
          account="default:checking",
          merchant="Merchant",
          description=f"Item {i}",
          item=f"item {i}",
          brand="Brand",
          category="Category",
          quantity=1.0,
          pack_size=1.0,
          unit="piece",
          unit_price=10.0,
          currency="MXN",
          discount=0.0,
          fee=0.0,
          tax=0.0,
          deposit=0.0,
          paid_total=-10.0,
          event_type="recurring",
          store_tier="A",
          store_rating=5.0,
          brand_tier="A",
          brand_rating=5.0,
          product_tier="A",
          product_rating=5.0,
          notes="",
          recorded_at="2026-01-10T00:00:00+00:00",
      )
      for i in range(1, 5)
  ]
  db.append_entries(first_4)

  imported, skipped = import_csv(ledger_file, csv_file)
  assert imported == 3
  assert skipped == 4


def test_t3_4_force_ingestion(tmp_path):
  """T3.4: force=True overwrites existing records in SQLite without errors."""
  csv_file = tmp_path / "single.csv"
  header = "receipt_id,receipt_date,merchant,description,item,brand,category,quantity,pack_size,unit,unit_price,currency,discount,fee,tax,deposit,paid_total,event_type,store_tier,store_rating,brand_tier,brand_rating,product_tier,product_rating,notes\n"
  row = "rec-001,2026-01-10,Merchant,Item,item,Brand,Category,1,1,piece,10.00,MXN,0,0,0,0,-10.00,recurring,A,5.0,A,5.0,A,5.0,\n"
  csv_file.write_text(header + row)

  ledger_file = tmp_path / "ledger.jsonl"
  imported, skipped = import_csv(ledger_file, csv_file)
  assert imported == 1

  # Force import
  imp_force, skip_force = import_csv(ledger_file, csv_file, force=True)
  assert imp_force == 1
  assert skip_force == 0


def test_t3_5_validation_failure_handling(tmp_path):
  """T3.5: Malformed CSV raises ValueError and writes zero rows to disk."""
  bad_csv = tmp_path / "bad.csv"
  bad_csv.write_text("item,receipt_id\napple,rec-01\n")

  ledger_file = tmp_path / "ledger.jsonl"
  with pytest.raises(ValueError) as exc:
    import_csv(ledger_file, bad_csv)
  assert "CSV validation failed" in str(exc.value)
  assert not ledger_file.exists()


def test_t3_6_custom_account_assignment(tmp_path):
  """T3.6: Assigns custom account identifier to imported entries."""
  csv_file = tmp_path / "account.csv"
  header = "receipt_id,receipt_date,merchant,description,item,brand,category,quantity,pack_size,unit,unit_price,currency,discount,fee,tax,deposit,paid_total,event_type,store_tier,store_rating,brand_tier,brand_rating,product_tier,product_rating,notes\n"
  row = "rec-001,2026-01-10,Merchant,Item,item,Brand,Category,1,1,piece,10.00,MXN,0,0,0,0,-10.00,recurring,A,5.0,A,5.0,A,5.0,\n"
  csv_file.write_text(header + row)

  ledger_file = tmp_path / "ledger.jsonl"
  import_csv(ledger_file, csv_file, account="savings:emergency")
  entries = list_entries(ledger_file)
  assert len(entries) == 1
  assert entries[0].account == "savings:emergency"


# ============================================================================
# Suite 4: Financial Accounting & Balance Integrity
# ============================================================================


def test_t4_1_and_t4_2_signed_amount_and_single_month_balance(tmp_path):
  """T4.1 & T4.2: Signed accounting with +income/refund and -expenditure."""
  ledger_file = tmp_path / "ledger.jsonl"
  # 1 income +3000, 2 purchases -40 and -26, 1 transfer -500
  add_entry(
      ledger_file, "2026-01-05", 3000.00, "income", "Employer",
      category="Income"
  )
  add_entry(
      ledger_file, "2026-01-10", 40.00, "one_off", "Store A", category="Food"
  )
  add_entry(
      ledger_file, "2026-01-12", 26.00, "recurring", "Store B", category="Food"
  )
  add_entry(
      ledger_file, "2026-01-20", -500.00, "transfer", "Bank",
      category="Transfer"
  )

  bal = get_balance(ledger_file, month="2026-01")
  assert bal["total_income"] == 3000.00
  assert bal["total_expenditure"] == 66.00
  assert bal["net_transfers"] == -500.00
  assert bal["net_refunds"] == 0.00
  assert bal["net_balance"] == 2434.00


def test_t4_3_multi_month_running_balance(tmp_path):
  """T4.3: Rolls over net balance across multiple months."""
  ledger_file = tmp_path / "ledger.jsonl"
  add_entry(ledger_file, "2026-01-05", 2000.00, "income", "Employer")
  add_entry(ledger_file, "2026-01-15", 500.00, "recurring", "Landlord")  # -500
  add_entry(ledger_file, "2026-02-05", 100.00, "one_off", "Shop")  # -100

  bal = get_balance(ledger_file)
  assert bal["net_balance"] == 1400.00
  assert bal["by_month"]["2026-01"]["net_balance"] == 1500.00
  assert bal["by_month"]["2026-02"]["net_balance"] == -100.00


def test_t4_4_multi_account_isolation(tmp_path):
  """T4.4: Balance queries properly isolate accounts."""
  ledger_file = tmp_path / "ledger.jsonl"
  add_entry(
      ledger_file, "2026-01-05", 1000.00, "income", "Employer",
      account="default:checking"
  )
  add_entry(
      ledger_file, "2026-01-10", 150.00, "one_off", "Hotel",
      account="credit:visa"
  )

  bal_checking = get_balance(ledger_file, account="default:checking")
  assert bal_checking["net_balance"] == 1000.00
  assert bal_checking["total_expenditure"] == 0.00

  bal_visa = get_balance(ledger_file, account="credit:visa")
  assert bal_visa["net_balance"] == -150.00
  assert bal_visa["total_expenditure"] == 150.00


def test_t4_5_empty_ledger_query(tmp_path):
  """T4.5: Querying empty ledger returns zeroed metrics without errors."""
  ledger_file = tmp_path / "empty_ledger.jsonl"
  bal = get_balance(ledger_file)
  assert bal["total_income"] == 0.00
  assert bal["total_expenditure"] == 0.00
  assert bal["net_transfers"] == 0.00
  assert bal["net_refunds"] == 0.00
  assert bal["net_balance"] == 0.00
  assert bal["by_month"] == {}


# ============================================================================
# Suite 5: Filterable Queries & Search
# ============================================================================


def test_suite_5_filterable_queries(tmp_path):
  """T5.1 - T5.6: Filter by month, category, merchant, event_type, account, conjunctions, and sorting."""
  ledger_file = tmp_path / "ledger.jsonl"

  # Populate ledger with varied transactions
  add_entry(
      ledger_file, "2026-02-15", 30.00, "recurring", "Market A",
      category="Food", account="acc1"
  )
  add_entry(
      ledger_file, "2026-01-10", 100.00, "income", "Employer",
      category="Salary", account="acc1"
  )
  add_entry(
      ledger_file, "2026-01-20", 25.00, "one_off", "Market A", category="Food",
      account="acc2"
  )
  add_entry(
      ledger_file, "2026-03-05", 50.00, "recurring", "Metro",
      category="Transport", account="acc1"
  )

  # T5.1: Month filter
  feb_entries = list_entries(ledger_file, month="2026-02")
  assert len(feb_entries) == 1
  assert feb_entries[0].receipt_date == "2026-02-15"

  # T5.2: Category filter
  food_entries = list_entries(ledger_file, category="Food")
  assert len(food_entries) == 2

  # T5.3: Merchant filter
  market_entries = list_entries(ledger_file, merchant="Market A")
  assert len(market_entries) == 2

  # T5.4: Event type filter
  income_entries = list_entries(ledger_file, event_type="income")
  assert len(income_entries) == 1
  assert income_entries[0].event_type == "income"

  # T5.5: Combined Conjunction Filtering
  conj = list_entries(ledger_file, month="2026-01", category="Food", merchant="Market A", account="acc2")
  assert len(conj) == 1
  assert conj[0].paid_total == -25.00

  # T5.6: Chronological Ordering
  all_entries = list_entries(ledger_file)
  dates = [e.receipt_date for e in all_entries]
  assert dates == sorted(dates)


# ============================================================================
# Suite 6: Category Breakdown & Expenditure Analytics
# ============================================================================


def test_t6_1_and_t6_2_category_breakdown_precision_and_filtering(tmp_path):
  """T6.1 & T6.2: Excludes non-consumption (income, transfer) and percentages sum to 100.0%."""
  ledger_file = tmp_path / "ledger.jsonl"
  add_entry(ledger_file, "2026-01-01", 3000.00, "income", "Employer", category="Salary")
  add_entry(ledger_file, "2026-01-02", -500.00, "transfer", "Bank", category="Transfer")
  add_entry(ledger_file, "2026-01-05", 100.00, "one_off", "Market", category="Food")
  add_entry(ledger_file, "2026-01-10", 50.00, "recurring", "Bus", category="Transport")
  add_entry(ledger_file, "2026-01-15", 50.00, "recurring", "Electric Co", category="Utilities")

  breakdown = get_category_breakdown(ledger_file)
  assert len(breakdown) == 3
  categories = {b["category"]: b for b in breakdown}

  assert "Salary" not in categories
  assert "Transfer" not in categories

  assert categories["Food"]["total_spent"] == 100.00
  assert categories["Food"]["percentage"] == 50.0

  assert categories["Transport"]["total_spent"] == 50.00
  assert categories["Transport"]["percentage"] == 25.0

  assert categories["Utilities"]["total_spent"] == 50.00
  assert categories["Utilities"]["percentage"] == 25.0

  total_pct = sum(b["percentage"] for b in breakdown)
  assert total_pct == 100.0


def test_t6_3_month_specific_breakdown(tmp_path):
  """T6.3: Only aggregates spending for the selected month."""
  ledger_file = tmp_path / "ledger.jsonl"
  add_entry(ledger_file, "2026-01-10", 40.00, "recurring", "Shop", category="Food")
  add_entry(ledger_file, "2026-02-10", 80.00, "recurring", "Shop", category="Food")

  jan_breakdown = get_category_breakdown(ledger_file, month="2026-01")
  assert len(jan_breakdown) == 1
  assert jan_breakdown[0]["total_spent"] == 40.00


def test_t6_4_zero_expenditure_edge_case(tmp_path):
  """T6.4: Zero expenditure returns empty list without division-by-zero error."""
  ledger_file = tmp_path / "ledger.jsonl"
  add_entry(ledger_file, "2026-01-01", 3000.00, "income", "Employer")
  add_entry(ledger_file, "2026-01-02", 500.00, "transfer", "Bank")

  breakdown = get_category_breakdown(ledger_file, month="2026-01")
  assert breakdown == []


# ============================================================================
# Suite 7: Direct Transaction Entry (add_entry)
# ============================================================================


def test_t7_1_add_one_off_expense(tmp_path):
  """T7.1: add_entry with expense creates valid entry and negative paid_total."""
  ledger_file = tmp_path / "ledger.jsonl"
  entry = add_entry(
      ledger_file,
      receipt_date="2026-03-05",
      amount=45.50,
      event_type="one_off",
      merchant="Corner Cafe",
  )
  assert entry.receipt_id.startswith("TXN-20260305-")
  assert entry.paid_total == -45.50
  assert entry.merchant == "Corner Cafe"
  assert entry.event_type == "one_off"

  # Persistence check
  entries = list_entries(ledger_file)
  assert len(entries) == 1
  assert entries[0].entry_id == entry.entry_id


def test_t7_2_add_income_event(tmp_path):
  """T7.2: add_entry with income event creates positive paid_total."""
  ledger_file = tmp_path / "ledger.jsonl"
  entry = add_entry(
      ledger_file,
      receipt_date="2026-03-01",
      amount=2500.00,
      event_type="income",
      merchant="Consulting Client",
      category="Income",
  )
  assert entry.paid_total == 2500.00
  assert entry.category == "Income"

  entries = list_entries(ledger_file)
  assert len(entries) == 1
  assert entries[0].paid_total == 2500.00


def test_t7_3_add_validation_invariants(tmp_path):
  """T7.3: Invalid date, amount, or event_type raises ValueError before modifying files."""
  ledger_file = tmp_path / "ledger.jsonl"

  with pytest.raises(ValueError, match="Invalid receipt_date"):
    add_entry(ledger_file, "not-a-date", 10.0, "recurring", "Shop")

  with pytest.raises(ValueError, match="Invalid amount"):
    add_entry(ledger_file, "2026-01-01", "not-a-number", "recurring", "Shop")

  with pytest.raises(ValueError, match="Invalid event_type"):
    add_entry(ledger_file, "2026-01-01", 10.0, "fake_event", "Shop")

  assert not ledger_file.exists()
