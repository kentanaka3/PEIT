"""Unit and integration tests for the PEIT Multi-Graph Dashboard Visualizer."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from peit.cli import main as cli_main
from peit.dashboard import (
    aggregate_category_breakdown,
    aggregate_cumulative_balance,
    aggregate_event_types,
    aggregate_timeline,
    aggregate_top_merchants,
    compute_inflation_and_welfare,
    compute_summary_kpis,
    create_dashboard,
    create_index_report,
    generate_dashboard_html,
    generate_index_html,
    parse_benchmark_csv,
)
from peit.ledger import LedgerDatabase, LedgerEntry, add_entry


def make_entry(
    entry_id: str = "e1",
    receipt_id: str = "R1",
    receipt_date: str = "2026-01-15",
    account: str = "default:checking",
    merchant: str = "SuperMart",
    item: str = "milk",
    brand: str = "Lala",
    category: str = "Groceries",
    quantity: float = 2.0,
    pack_size: float = 1.0,
    unit: str = "liter",
    unit_price: float = 15.0,
    currency: str = "MXN",
    discount: float = 0.0,
    fee: float = 0.0,
    tax: float = 0.0,
    deposit: float = 0.0,
    paid_total: float = -30.0,
    event_type: str = "one_off",
    store_tier: str = "A",
    store_rating: float = 5.0,
    brand_tier: str = "A",
    brand_rating: float = 5.0,
    product_tier: str = "A",
    product_rating: float = 5.0,
    availability: str = "in_stock",
    notes: str = "",
    recorded_at: str = "2026-01-15T12:00:00Z",
) -> LedgerEntry:
  return LedgerEntry(
      entry_id=entry_id,
      receipt_id=receipt_id,
      receipt_date=receipt_date,
      account=account,
      merchant=merchant,
      item=item,
      brand=brand,
      category=category,
      quantity=quantity,
      pack_size=pack_size,
      unit=unit,
      unit_price=unit_price,
      currency=currency,
      discount=discount,
      fee=fee,
      tax=tax,
      deposit=deposit,
      paid_total=paid_total,
      event_type=event_type,
      store_tier=store_tier,
      store_rating=store_rating,
      brand_tier=brand_tier,
      brand_rating=brand_rating,
      product_tier=product_tier,
      product_rating=product_rating,
      availability=availability,
      notes=notes,
      recorded_at=recorded_at,
  )


def test_compute_summary_kpis():
  entries = [
      make_entry(entry_id="1", paid_total=5000.0, event_type="income"),
      make_entry(entry_id="2", paid_total=-1200.0, event_type="recurring"),
      make_entry(entry_id="3", paid_total=-350.50, event_type="one_off"),
      make_entry(entry_id="4", paid_total=-500.0, event_type="transfer"),
      make_entry(entry_id="5", paid_total=80.0, event_type="refund"),
  ]
  kpis = compute_summary_kpis(entries)
  assert kpis["total_income"] == 5000.0
  assert kpis["total_expenditure"] == 1550.50
  assert kpis["net_transfers"] == -500.0
  assert kpis["net_refunds"] == 80.0
  assert kpis["net_balance"] == round(
      5000.0 - 1200.0 - 350.50 - 500.0 + 80.0, 2
  )
  assert kpis["transaction_count"] == 5


def test_aggregate_category_breakdown():
  entries = [
      make_entry(
          entry_id="1", category="Food", paid_total=-100.0,
          event_type="one_off"
      ),
      make_entry(
          entry_id="2", category="Transport", paid_total=-50.0,
          event_type="recurring"
      ),
      make_entry(
          entry_id="3", category="Food", paid_total=-50.0,
          event_type="one_off"
      ),
      make_entry(
          entry_id="4", category="Income", paid_total=1000.0,
          event_type="income"
      ),
  ]
  breakdown = aggregate_category_breakdown(entries)
  assert len(breakdown) == 2
  assert breakdown[0]["category"] == "Food"
  assert breakdown[0]["total_spent"] == 150.0
  assert breakdown[0]["percentage"] == 75.0
  assert breakdown[0]["count"] == 2
  assert "color" in breakdown[0]

  assert breakdown[1]["category"] == "Transport"
  assert breakdown[1]["total_spent"] == 50.0
  assert breakdown[1]["percentage"] == 25.0
  assert breakdown[1]["count"] == 1

  # Total percentage reconciliation check
  total_pct = sum(item["percentage"] for item in breakdown)
  assert total_pct == 100.0


def test_aggregate_timeline_monthly_and_daily():
  entries = [
      make_entry(
          entry_id="1", receipt_date="2026-01-10", paid_total=2000.0,
          event_type="income"
      ),
      make_entry(
          entry_id="2", receipt_date="2026-01-15", paid_total=-500.0,
          event_type="recurring"
      ),
      make_entry(
          entry_id="3", receipt_date="2026-02-05", paid_total=-300.0,
          event_type="one_off"
      ),
  ]

  # Monthly
  t_monthly = aggregate_timeline(entries, month_filter=None)
  assert t_monthly["labels"] == ["2026-01", "2026-02"]
  assert t_monthly["income_series"] == [2000.0, 0.0]
  assert t_monthly["expense_series"] == [500.0, 300.0]

  # Daily (with month filter)
  t_daily = aggregate_timeline(entries, month_filter="2026-01")
  assert "2026-01-10" in t_daily["labels"]
  assert "2026-01-15" in t_daily["labels"]


def test_aggregate_top_merchants_with_other():
  entries = []
  for idx in range(12):
    entries.append(
        make_entry(
            entry_id=str(idx),
            merchant=f"Merchant_{idx:02d}",
            paid_total=-float(100 - idx * 5),
            event_type="one_off",
        )
    )

  top = aggregate_top_merchants(entries, top_n=10)
  assert len(top) == 11  # 10 merchants + 'Other'
  assert top[0]["merchant"] == "Merchant_00"
  assert top[-1]["merchant"] == "Other"
  assert top[-1]["count"] == 2


def test_aggregate_event_types():
  entries = [
      make_entry(entry_id="1", event_type="income", paid_total=500.0),
      make_entry(entry_id="2", event_type="recurring", paid_total=-100.0),
      make_entry(entry_id="3", event_type="one_off", paid_total=-50.0),
      make_entry(entry_id="4", event_type="transfer", paid_total=-200.0),
      make_entry(entry_id="5", event_type="refund", paid_total=30.0),
  ]
  etypes = aggregate_event_types(entries)
  type_names = {item["event_type"] for item in etypes}
  assert type_names == {"income", "recurring", "one_off", "transfer", "refund"}
  sum_pct = sum(item["percentage"] for item in etypes)
  assert round(sum_pct, 1) == 100.0


def test_aggregate_cumulative_balance():
  entries = [
      make_entry(entry_id="1", receipt_date="2026-01-01", paid_total=1000.0),
      make_entry(entry_id="2", receipt_date="2026-01-05", paid_total=-200.0),
      make_entry(entry_id="3", receipt_date="2026-01-10", paid_total=-300.0),
  ]
  cum = aggregate_cumulative_balance(entries)
  assert cum["labels"] == ["2026-01-01", "2026-01-05", "2026-01-10"]
  assert cum["balance_series"] == [1000.0, 800.0, 500.0]


def test_bennett_decomposition_zero_residual():
  # Month 1: Milk (qty 10, price 2.0 -> spend 20), Bread (qty 5, price 3.0 -> spend 15)
  # Month 2: Milk (qty 12, price 3.0 -> spend 36), Bread (qty 4, price 3.5 -> spend 14)
  entries = [
      make_entry(
          entry_id="m1_1", receipt_date="2026-01-10",
          item="milk", brand="Lala", category="Dairy", quantity=10.0,
          pack_size=1.0, unit_price=2.0, paid_total=-20.0,
      ),
      make_entry(
          entry_id="m1_2", receipt_date="2026-01-15",
          item="bread", brand="Bimbo", category="Bakery", quantity=5.0,
          pack_size=1.0, unit_price=3.0, paid_total=-15.0,
      ),
      make_entry(
          entry_id="m2_1", receipt_date="2026-02-10",
          item="milk", brand="Lala", category="Dairy", quantity=12.0,
          pack_size=1.0, unit_price=3.0, paid_total=-36.0,
      ),
      make_entry(
          entry_id="m2_2", receipt_date="2026-02-15",
          item="bread", brand="Bimbo", category="Bakery", quantity=4.0,
          pack_size=1.0, unit_price=3.5, paid_total=-14.0,
      ),
  ]

  res = compute_inflation_and_welfare(entries)
  assert res["has_data"] is True
  bennett = res["bennett"]
  assert bennett is not None
  assert bennett["matched_count"] == 2
  assert bennett["base_expenditure"] == 35.0  # 20 + 15
  assert bennett["current_expenditure"] == 50.0  # 36 + 14
  assert bennett["delta_expenditure"] == 15.0  # 50 - 35

  # Bennett exact zero residual verification:
  delta_p = bennett["price_effect"]
  delta_q = bennett["quantity_effect"]
  assert round(delta_p + delta_q, 2) == bennett["delta_expenditure"]
  assert bennett["residual"] == 0.0

  # Category inflation contributions check
  cat_infl = res["category_inflation"]
  assert len(cat_infl) == 2
  total_ppc = sum(c["ppc"] for c in cat_infl)
  assert round(total_ppc, 1) == round(res["latest_kpis"]["personal_mom"], 1)


def test_inflation_graceful_degradation():
  # Single month data should degrade gracefully
  entries = [
      make_entry(entry_id="1", paid_total=-50.0),
  ]
  res = compute_inflation_and_welfare(entries)
  assert res["has_data"] is False
  assert res["status"] == "insufficient_history"
  assert "At least 2 months" in res["message"]


def test_parse_benchmark_csv(tmp_path: Path):
  csv_file = tmp_path / "benchmark.csv"
  csv_file.write_text(
      "month,country,series_name,cpi_index,mom_inflation_percent,yoy_inflation_percent,source\n"
      "2026-01,MEX,INEGI_INPC,138.452,0.49,4.21,INEGI\n"
      "2026-02,MEX,INEGI_INPC,138.937,0.35,4.15,INEGI\n",
      encoding="utf-8",
  )

  data = parse_benchmark_csv(csv_file)
  assert "2026-01" in data
  assert data["2026-01"]["cpi_index"] == 138.452
  assert data["2026-02"]["mom_inflation_percent"] == 0.35


def test_generate_dashboard_html_structure():
  entries = [
      make_entry(
          entry_id="1", paid_total=2500.0, event_type="income",
          merchant="Employer"
      ),
      make_entry(
          entry_id="2", paid_total=-85.50, event_type="one_off",
          merchant="<script>alert('XSS')</script>"
      ),
  ]
  kpis = compute_summary_kpis(entries)
  cat = aggregate_category_breakdown(entries)
  timeline = aggregate_timeline(entries)
  merch = aggregate_top_merchants(entries)
  etypes = aggregate_event_types(entries)
  cum = aggregate_cumulative_balance(entries)
  infl = compute_inflation_and_welfare(entries)

  html_out = generate_dashboard_html(
      entries=entries,
      summary_kpis=kpis,
      category_breakdown=cat,
      timeline_data=timeline,
      top_merchants=merch,
      event_type_distribution=etypes,
      cumulative_balance=cum,
      inflation_data=infl,
  )

  # Check standard HTML5 markers
  assert "<!DOCTYPE html>" in html_out
  assert "chart.js" in html_out.lower()

  # Check Tab IDs
  assert 'id="tab-cashflow"' in html_out
  assert 'id="tab-inflation"' in html_out
  assert 'id="tab-ledger"' in html_out

  # Check search element and table
  assert 'id="table-search"' in html_out
  assert 'id="transactions-table"' in html_out

  # Check XSS escaping
  assert "<script>alert('XSS')</script>" not in html_out
  assert (
      "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;" in html_out or
      "&lt;script&gt;" in html_out
  )


def test_create_dashboard_api(tmp_path: Path):
  ledger_file = tmp_path / "test_ledger.jsonl"
  # Add entries into ledger
  add_entry(
      ledger_path=ledger_file,
      receipt_date="2026-01-10",
      amount=5000.0,
      event_type="income",
      merchant="Salary",
  )
  add_entry(
      ledger_path=ledger_file,
      receipt_date="2026-01-15",
      amount=250.0,
      event_type="one_off",
      merchant="Costco",
      category="Groceries",
  )

  # Default auto-derived output path
  out_path = create_dashboard(ledger_path=ledger_file, open_browser=False)
  assert out_path.exists()
  assert out_path.name == "test_ledger_dashboard.html"
  content = out_path.read_text(encoding="utf-8")
  assert "Costco" in content
  assert "Salary" in content

  # Custom output path
  custom_out = tmp_path / "custom_dir" / "report.html"
  out_custom = create_dashboard(
      ledger_path=ledger_file, output_path=custom_out, open_browser=False
  )
  assert out_custom.exists()
  assert out_custom == custom_out.resolve()


def test_cli_dashboard_integration(tmp_path: Path, monkeypatch, capsys):
  ledger_file = tmp_path / "cli_ledger.jsonl"
  add_entry(
      ledger_path=ledger_file,
      receipt_date="2026-02-01",
      amount=100.0,
      event_type="one_off",
      merchant="StoreA",
  )

  out_html = tmp_path / "cli_dashboard.html"
  exit_code = cli_main([
      "--ledger", str(ledger_file), "--dashboard", "-o", str(out_html)
  ])
  assert exit_code == 0
  assert out_html.exists()

  captured = capsys.readouterr()
  assert "Dashboard generated successfully at:" in captured.out

  # Verify --html flag behaves identically
  out_html2 = tmp_path / "cli_dashboard_html_flag.html"
  exit_code2 = cli_main([
      "--ledger", str(ledger_file),
      "--html", "-o", str(out_html2)])
  assert exit_code2 == 0
  assert out_html2.exists()


def test_generate_index_html():
  report = [
      {
          "month": "2026-01",
          "fixed_basket_index": 100.0,
          "changing_basket_expenditure_index": 100.0,
          "coverage_percent": 100.0,
          "expenditure": 500.0,
          "status": "derived",
          "mom_percent": None,
      },
      {
          "month": "2026-02",
          "fixed_basket_index": 102.5,
          "changing_basket_expenditure_index": 104.0,
          "coverage_percent": 95.0,
          "expenditure": 520.0,
          "status": "derived",
          "mom_percent": 2.5,
      },
  ]
  html_str = generate_index_html(report, source_name="Test Source")
  assert "<!DOCTYPE html>" in html_str
  assert "Test Source" in html_str
  assert "100.00" in html_str
  assert "102.50" in html_str
  assert "indexTrajectoryChart" in html_str

  # Empty report edge case
  html_empty = generate_index_html([], source_name="Empty Source")
  assert "<!DOCTYPE html>" in html_empty
  assert "No inflation index data available." in html_empty


def test_create_index_report_api(tmp_path: Path):
  report = [
      {
          "month": "2026-01",
          "fixed_basket_index": 100.0,
          "changing_basket_expenditure_index": 100.0,
          "coverage_percent": 100.0,
          "expenditure": 150.0,
          "status": "derived",
          "mom_percent": None,
      }
  ]
  csv_file = tmp_path / "my_receipts.csv"
  csv_file.write_text("dummy", encoding="utf-8")

  # Default output path
  out_path = create_index_report(report, csv_file, open_browser=False)
  assert out_path.exists()
  assert out_path.name == "my_receipts_index.html"
  content = out_path.read_text(encoding="utf-8")
  assert "my_receipts Price Index Report" in content

  # Custom output path
  custom_out = tmp_path / "custom" / "report.html"
  out_custom = create_index_report(
      report, csv_file, output_path=custom_out, open_browser=False)
  assert out_custom.exists()
  assert out_custom == custom_out.resolve()
