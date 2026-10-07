"""
End-to-end integration and unit tests for the PEIT command-line interface
(Suite 8).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest

from peit.cli import build_parser, main

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CSV = PROJECT_ROOT / "data" / "example_month.csv"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
  """Execute PEIT CLI in a subprocess with appropriate PYTHONPATH."""
  cmd = [sys.executable, "-m", "peit.cli", *args]
  env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")}
  return subprocess.run(
      cmd,
      capture_output=True,
      text=True,
      cwd=str(PROJECT_ROOT),
      env=env,
  )


# ============================================================================
# Suite 8: Command-Line Interface Tests
# ============================================================================


def test_t8_1_cli_inflation_calculation():
  """T8.1: CLI Inflation Calculation (--index).

  Given: Valid data/example_month.csv.
  When: Running peit --index data/example_month.csv.
  Then: Outputs inflation table, exits with code 0.
  """
  proc = run_cli("--index", str(EXAMPLE_CSV))
  assert proc.returncode == 0
  assert "month" in proc.stdout
  assert "fixed_basket" in proc.stdout
  assert "changing_expenditure" in proc.stdout
  assert "coverage" in proc.stdout
  assert "2021-01" in proc.stdout


def test_t8_2_cli_inflation_calculation_json():
  """T8.2: CLI Inflation Calculation JSON (--index --json).

  Given: Valid data/example_month.csv.
  When: Running peit --index data/example_month.csv --json.
  Then: Emits valid JSON parseable by json.loads().
  """
  proc = run_cli("--index", str(EXAMPLE_CSV), "--json")
  assert proc.returncode == 0
  data = json.loads(proc.stdout)
  assert isinstance(data, list)
  assert len(data) > 0
  first = data[0]
  assert first["month"] == "2021-01"
  assert "fixed_basket_index" in first
  assert "changing_basket_expenditure_index" in first
  assert "coverage_percent" in first


def test_t8_3_cli_ledger_import(tmp_path: Path):
  """T8.3: CLI Ledger Import (--ledger --import).

  Given: A new ledger path and data/example_month.csv.
  When: Running peit --ledger /tmp/ledger.jsonl --import data/example_month.csv.
  Then: Prints imported row count; creates /tmp/ledger.jsonl and /tmp/ledger.db.
  """
  ledger_path = tmp_path / "ledger.jsonl"
  db_path = tmp_path / "ledger.db"

  proc = run_cli("--ledger", str(ledger_path), "--import", str(EXAMPLE_CSV))
  assert proc.returncode == 0
  assert "Imported 10000 rows, skipped 0 duplicates." in proc.stdout
  assert ledger_path.exists()
  assert db_path.exists()

  # Test idempotence on second import
  proc_repeat = run_cli(
      "--ledger", str(ledger_path), "--import", str(EXAMPLE_CSV)
  )
  assert proc_repeat.returncode == 0
  assert "Imported 0 rows, skipped 10000 duplicates." in proc_repeat.stdout


def test_t8_4_cli_ledger_balance(tmp_path: Path):
  """T8.4: CLI Ledger Balance (--ledger --balance).

  Given: A populated ledger.
  When: Running peit --ledger /tmp/ledger.jsonl --balance and with --json.
  Then: Formatted table output in text mode; valid JSON dictionary in JSON mode.
  """
  ledger_path = tmp_path / "ledger.jsonl"
  # Populate ledger
  run_cli("--ledger", str(ledger_path), "--import", str(EXAMPLE_CSV))

  # Test text balance table
  proc_text = run_cli(
      "--ledger", str(ledger_path), "--balance", "--month", "2021-01"
  )
  assert proc_text.returncode == 0
  assert "Financial Balance Summary" in proc_text.stdout
  assert "Total Income:" in proc_text.stdout
  assert "Total Expenditure:" in proc_text.stdout
  assert "Net Balance:" in proc_text.stdout

  # Test JSON balance
  proc_json = run_cli(
      "--ledger", str(ledger_path), "--balance", "--month", "2021-01", "--json"
  )
  assert proc_json.returncode == 0
  data = json.loads(proc_json.stdout)
  assert isinstance(data, dict)
  assert "total_income" in data
  assert "total_expenditure" in data
  assert "net_balance" in data
  assert "by_month" in data
  assert "2021-01" in data["by_month"]


def test_t8_5_cli_ledger_list_with_filters(tmp_path: Path):
  """T8.5: CLI Ledger List with Filters (--ledger --list).

  Given: A populated ledger.
  When: Running peit --ledger /tmp/ledger.jsonl --list --category Food --month 2026-01.
  Then: Prints table filtered to matching transactions.
  """
  ledger_path = tmp_path / "ledger.jsonl"
  # Add specific entries
  run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-01-10",
      "--amount", "50.00",
      "--event-type", "one_off",
      "--merchant", "Grocery Store",
      "--category", "Food",
  )
  run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-01-15",
      "--amount", "100.00",
      "--event-type", "recurring",
      "--merchant", "Electric Co",
      "--category", "Utilities",
  )
  run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-02-05",
      "--amount", "60.00",
      "--event-type", "one_off",
      "--merchant", "Grocery Store",
      "--category", "Food",
  )

  # Filter by category and month
  proc_filtered = run_cli(
      "--ledger", str(ledger_path), "--list",
      "--category", "Food",
      "--month", "2026-01",
  )
  assert proc_filtered.returncode == 0
  assert "Grocery Store" in proc_filtered.stdout
  assert "Food" in proc_filtered.stdout
  assert "Electric Co" not in proc_filtered.stdout
  assert "2026-02-05" not in proc_filtered.stdout

  # Test JSON output
  proc_json = run_cli(
      "--ledger", str(ledger_path), "--list",
      "--category", "Food",
      "--month", "2026-01",
      "--json",
  )
  assert proc_json.returncode == 0
  entries = json.loads(proc_json.stdout)
  assert isinstance(entries, list)
  assert len(entries) == 1
  assert entries[0]["merchant"] == "Grocery Store"
  assert entries[0]["category"] == "Food"


def test_t8_6_cli_ledger_breakdown(tmp_path: Path):
  """T8.6: CLI Ledger Breakdown (--ledger --breakdown).

  Given: A populated ledger.
  When: Running peit --ledger /tmp/ledger.jsonl --breakdown.
  Then: Prints category spend and percentages.
  """
  ledger_path = tmp_path / "ledger.jsonl"
  run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-01-10",
      "--amount", "100.00",
      "--event-type", "one_off",
      "--merchant", "Supermarket",
      "--category", "Food",
  )
  run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-01-12",
      "--amount", "300.00",
      "--event-type", "recurring",
      "--merchant", "Landlord",
      "--category", "Housing",
  )

  # Text breakdown
  proc_text = run_cli("--ledger", str(ledger_path), "--breakdown")
  assert proc_text.returncode == 0
  assert "Category" in proc_text.stdout
  assert "Total Spent" in proc_text.stdout
  assert "Percentage" in proc_text.stdout
  assert "Housing" in proc_text.stdout
  assert "Food" in proc_text.stdout

  # JSON breakdown
  proc_json = run_cli("--ledger", str(ledger_path), "--breakdown", "--json")
  assert proc_json.returncode == 0
  breakdown = json.loads(proc_json.stdout)
  assert isinstance(breakdown, list)
  assert len(breakdown) == 2
  categories = {b["category"]: b for b in breakdown}
  assert "Housing" in categories
  assert "Food" in categories
  assert categories["Housing"]["total_spent"] == 300.0
  assert categories["Food"]["total_spent"] == 100.0


def test_t8_7_cli_ledger_add(tmp_path: Path):
  """T8.7: CLI Ledger Add (--ledger --add).

  Given: Arguments for --date, --amount, --event-type, --merchant.
  When: Running peit --ledger /tmp/ledger.jsonl --add ....
  Then: Appends transaction and confirms addition on stdout.
  """
  ledger_path = tmp_path / "ledger.jsonl"
  proc = run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-03-01",
      "--amount", "2500.00",
      "--event-type", "income",
      "--merchant", "Consulting Client",
      "--category", "Salary",
      "--item", "Contract services",
      "--notes", "March retainer",
  )
  assert proc.returncode == 0
  assert "Added entry" in proc.stdout
  assert "Consulting Client" in proc.stdout
  assert "2500" in proc.stdout
  assert ledger_path.exists()

  # Verify entry exists in JSONL
  with ledger_path.open("r", encoding="utf-8") as f:
    lines = [json.loads(line) for line in f]
  assert len(lines) == 1
  entry = lines[0]
  assert entry["merchant"] == "Consulting Client"
  assert entry["paid_total"] == 2500.0
  assert entry["event_type"] == "income"
  assert entry["category"] == "Salary"
  assert entry["notes"] == "March retainer"


def test_t8_8_cli_ledger_rebuild_cache(tmp_path: Path):
  """T8.8: CLI Ledger Rebuild Cache (--ledger --rebuild-cache).

  Given: A ledger with existing JSONL.
  When: Running peit --ledger /tmp/ledger.jsonl --rebuild-cache.
  Then: Successfully rebuilds SQLite DB and exits with code 0.
  """
  ledger_path = tmp_path / "ledger.jsonl"
  db_path = tmp_path / "ledger.db"

  # Populate ledger with an entry
  run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-03-01",
      "--amount", "2500.00",
      "--event-type", "income",
      "--merchant", "Consulting Client",
  )
  assert db_path.exists()

  # Remove SQLite DB to test recreation
  db_path.unlink()
  assert not db_path.exists()

  # Run rebuild-cache
  proc = run_cli("--ledger", str(ledger_path), "--rebuild-cache")
  assert proc.returncode == 0
  assert "Cache rebuilt successfully" in proc.stdout
  assert db_path.exists()

  # Verify DB contains the entry
  conn = sqlite3.connect(str(db_path))
  try:
    cur = conn.execute("SELECT COUNT(*) FROM entries")
    assert cur.fetchone()[0] == 1
  finally:
    conn.close()


def test_t8_9_cli_error_handling_and_exit_codes(tmp_path: Path):
  """T8.9: CLI Error Handling & Exit Codes.

  Given: Missing required flags or invalid file paths.
  When: Running invalid CLI commands.
  Then: Outputs clear error messages to stderr and exits with status code 2.
  """
  ledger_path = tmp_path / "ledger.jsonl"

  # 1. No arguments provided
  proc_no_args = run_cli()
  assert proc_no_args.returncode == 2
  assert "Must specify either --index or --ledger" in proc_no_args.stderr

  # 2. Both --index and --ledger provided
  proc_both = run_cli(
      "--index", str(EXAMPLE_CSV), "--ledger", str(ledger_path)
  )
  assert proc_both.returncode == 2
  assert "Cannot specify both --index and --ledger" in proc_both.stderr

  # 3. Ledger provided without operation
  proc_no_op = run_cli("--ledger", str(ledger_path))
  assert proc_no_op.returncode == 2
  assert "Must specify one ledger operation" in proc_no_op.stderr

  # 4. Multiple conflicting operations
  proc_multi_op = run_cli("--ledger", str(ledger_path), "--balance", "--list")
  assert proc_multi_op.returncode == 2
  assert "Only one ledger operation" in proc_multi_op.stderr

  # 5. Ledger operation on --index
  proc_index_op = run_cli("--index", str(EXAMPLE_CSV), "--balance")
  assert proc_index_op.returncode == 2
  assert "Ledger operations cannot be used with --index" in proc_index_op.stderr

  # 6. Missing required arguments for --add
  proc_add_missing = run_cli("--ledger", str(ledger_path), "--add")
  assert proc_add_missing.returncode == 2
  assert "Missing required argument(s) for --add" in proc_add_missing.stderr

  # 7. Invalid date format for --add
  proc_bad_date = run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026/03/01",
      "--amount", "100.00",
      "--event-type", "one_off",
      "--merchant", "Test Store",
  )
  assert proc_bad_date.returncode == 2
  assert "Invalid date format" in proc_bad_date.stderr

  # 8. Invalid event-type for --add
  proc_bad_event = run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-03-01",
      "--amount", "100.00",
      "--event-type", "unsupported_type",
      "--merchant", "Test Store",
  )
  assert proc_bad_event.returncode == 2
  assert "Invalid event-type" in proc_bad_event.stderr

  # 9. Nonexistent CSV for --index
  proc_bad_csv = run_cli("--index", "non_existent_file.csv")
  assert proc_bad_csv.returncode == 2
  assert "CSV file not found" in proc_bad_csv.stderr

  # 10. Nonexistent CSV for --import
  proc_bad_import = run_cli(
      "--ledger", str(ledger_path), "--import", "non_existent_file.csv"
  )
  assert proc_bad_import.returncode == 2
  assert "CSV file not found" in proc_bad_import.stderr

  # 11. Invalid month format
  proc_bad_month = run_cli(
      "--ledger", str(ledger_path), "--balance", "--month", "2026-13"
  )
  assert proc_bad_month.returncode == 2
  assert "Invalid month format" in proc_bad_month.stderr

  # 12. Conflicting --json and --html on --index
  proc_index_json_html = run_cli(
      "--index", str(EXAMPLE_CSV), "--html", "--json"
  )
  assert proc_index_json_html.returncode == 2
  assert "Cannot specify both --json and --html" in proc_index_json_html.stderr

  # 13. Conflicting ledger operation with --html
  proc_ledger_conflict = run_cli(
      "--ledger", str(ledger_path), "--balance", "--html"
  )
  assert proc_ledger_conflict.returncode == 2
  assert "Only one ledger operation" in proc_ledger_conflict.stderr


def test_t8_10_cli_ledger_html_generation(tmp_path: Path):
  """T8.10: CLI Ledger HTML Dashboard Generation (--ledger ... --html).

  Given: A populated ledger.
  When: Invoking peit --ledger <path> --html with explicit output and default output.
  Then: Generates a self-contained HTML dashboard with exit code 0.
  """
  ledger_path = tmp_path / "ledger.jsonl"
  run_cli("--ledger", str(ledger_path), "--import", str(EXAMPLE_CSV))

  # Explicit output path
  out_html = tmp_path / "custom_dashboard.html"
  proc = run_cli("--ledger", str(ledger_path), "--html", "-o", str(out_html))
  assert proc.returncode == 0
  assert "Dashboard generated successfully at:" in proc.stdout
  assert out_html.exists()
  content = out_html.read_text(encoding="utf-8")
  assert "<!DOCTYPE html>" in content
  assert "PEIT Multi-Graph Dashboard" in content
  assert "chart.js" in content.lower()
  assert "data-table" in content

  # Default auto-derived output path
  proc_default = run_cli("--ledger", str(ledger_path), "--html")
  assert proc_default.returncode == 0
  expected_default = tmp_path / "ledger_dashboard.html"
  assert expected_default.exists()

  # Both --dashboard and --html combined
  out_combined = tmp_path / "combined.html"
  proc_comb = run_cli(
      "--ledger", str(ledger_path), "--dashboard", "--html", "-o",
      str(out_combined)
  )
  assert proc_comb.returncode == 0
  assert out_combined.exists()

  # Filters honored with --html
  out_filtered = tmp_path / "filtered.html"
  proc_filt = run_cli(
      "--ledger", str(ledger_path),
      "--html",
      "--month", "2021-01",
      "-o", str(out_filtered),
  )
  assert proc_filt.returncode == 0
  assert out_filtered.exists()
  filt_content = out_filtered.read_text(encoding="utf-8")
  assert "Month: 2021-01" in filt_content


def test_t8_11_cli_index_html_generation(tmp_path: Path):
  """T8.11: CLI Price Index HTML Report Generation (--index ... --html).

  Given: A valid receipt CSV.
  When: Invoking peit --index <csv> --html with explicit output and default output.
  Then: Generates a self-contained HTML price index report with exit code 0.
  """
  out_html = tmp_path / "index_report.html"
  proc = run_cli("--index", str(EXAMPLE_CSV), "--html", "-o", str(out_html))
  assert proc.returncode == 0
  assert "Index HTML report generated successfully at:" in proc.stdout
  assert out_html.exists()
  content = out_html.read_text(encoding="utf-8")
  assert "<!DOCTYPE html>" in content
  assert "PEIT Price Index Report" in content
  assert "Fixed Basket Price Index" in content
  assert "indexTrajectoryChart" in content
  assert "data-table" in content

  # Default auto-derived output path for index
  sample_csv = tmp_path / "sample.csv"
  sample_csv.write_text(
      EXAMPLE_CSV.read_text(encoding="utf-8"), encoding="utf-8"
  )
  proc_default = run_cli("--index", str(sample_csv), "--html")
  assert proc_default.returncode == 0
  expected_default = tmp_path / "sample_index.html"
  assert expected_default.exists()

  # --dashboard accepted under --index as alias
  out_dash = tmp_path / "index_from_dash.html"
  proc_dash = run_cli(
      "--index", str(EXAMPLE_CSV), "--dashboard", "-o", str(out_dash)
  )
  assert proc_dash.returncode == 0
  assert out_dash.exists()


def test_cli_direct_main_invocation(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
):
  """Verify that main(argv) direct function calls behave identically."""
  ledger_path = tmp_path / "ledger.jsonl"
  code = main([
      "--ledger", str(ledger_path), "--add", "--date", "2026-01-01",
      "--amount", "10.0", "--event-type", "income", "--merchant", "Client"
  ])
  assert code == 0
  captured = capsys.readouterr()
  assert "Added entry" in captured.out

  # Test error return
  err_code = main(["--index", "missing.csv"])
  assert err_code == 2
  captured_err = capsys.readouterr()
  assert "CSV file not found" in captured_err.err

  # Test direct HTML generation for index
  out_index = tmp_path / "direct_index.html"
  code_index = main([
      "--index", str(EXAMPLE_CSV), "--html", "-o", str(out_index)
  ])
  assert code_index == 0
  assert out_index.exists()

  # Test direct HTML generation for ledger
  out_ledger = tmp_path / "direct_ledger.html"
  code_ledger = main([
      "--ledger", str(ledger_path), "--html", "-o", str(out_ledger)
  ])
  assert code_ledger == 0
  assert out_ledger.exists()


def test_cli_add_schema_options(tmp_path: Path):
  """Verify that peit --ledger ... --add supports Schema arguments."""
  ledger_path = tmp_path / "ledger.jsonl"
  proc = run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-03-10",
      "--amount", "45.00",
      "--event-type", "one_off",
      "--merchant", "SuperMart",
      "--category", "Food",
      "--item", "milk 1 l",
      "--brand", "Lala",
      "--pack-size", "2",
      "--unit-price", "22.50",
      "--notes", "Pantry restock",
  )
  assert proc.returncode == 0
  assert "Added entry" in proc.stdout
  assert "SuperMart" in proc.stdout

  with ledger_path.open("r", encoding="utf-8") as f:
    entries = [json.loads(line) for line in f]
  assert len(entries) == 1
  e = entries[0]
  assert e["item"] == "milk 1 l"
  assert e["brand"] == "Lala"
  assert e["pack_size"] == 2.0
  assert e["unit_price"] == 22.50
  assert e["paid_total"] == -45.0
  assert e["store_tier"] == "A"
  assert e["store_rating"] == 5.0
  assert e["brand_tier"] == "A"
  assert e["brand_rating"] == 5.0
  assert e["product_tier"] == "A"
  assert e["product_rating"] == 5.0
  assert e["availability"] == "in_stock"


def test_cli_add_store_brand_product_tier_rating_options(tmp_path: Path):
  """
  Verify that peit --ledger ... --add supports --store-tier, --store-rating,
                   --brand-tier, --brand-rating, --product-tier,
                   --product-rating, --availability.
  """
  ledger_path = tmp_path / "ledger_multi_tier.jsonl"
  proc = run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-04-01",
      "--amount", "85.50",
      "--event-type", "one_off",
      "--merchant", "Gourmet Market",
      "--item", "cheese 500 g",
      "--store-tier", "A",
      "--store-rating", "4.8",
      "--brand-tier", "B",
      "--brand-rating", "4.2",
      "--product-tier", "C",
      "--product-rating", "3.9",
      "--availability", "low_stock",
  )
  assert proc.returncode == 0
  assert "Added entry" in proc.stdout

  with ledger_path.open("r", encoding="utf-8") as f:
    entries = [json.loads(line) for line in f]
  assert len(entries) == 1
  e = entries[0]
  assert e["store_tier"] == "A"
  assert e["store_rating"] == 4.8
  assert e["brand_tier"] == "B"
  assert e["brand_rating"] == 4.2
  assert e["product_tier"] == "C"
  assert e["product_rating"] == 3.9
  assert e["availability"] == "low_stock"

  # Invalid store-rating
  proc_invalid_store = run_cli(
      "--ledger", str(ledger_path), "--add",
      "--date", "2026-04-02",
      "--amount", "10.00",
      "--event-type", "one_off",
      "--merchant", "Store",
      "--store-rating", "6.0",
  )
  assert proc_invalid_store.returncode == 2
  assert (
      "store-rating must be between 1.0 and 5.0" in proc_invalid_store.stderr
  )
