"""
PEIT Multi-Graph Dashboard Visualizer.

Generates self-contained, interactive HTML5 dashboards with cash flow analysis,
spending distributions, economic inflation and welfare metrics (Bennett
additive decomposition, category PPC/ADI contributions, national CPI tracking),
and a real-time searchable transaction ledger.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
import webbrowser
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from peit.core import MONTH_RE, calculate_indices
from peit.ledger import LedgerDatabase, LedgerEntry, get_category_breakdown, list_entries
from peit.schema import EventType

DEFAULT_PALETTE = [
    "#3b82f6",  # Blue
    "#10b981",  # Emerald
    "#f59e0b",  # Amber
    "#ef4444",  # Red
    "#8b5cf6",  # Violet
    "#06b6d4",  # Cyan
    "#ec4899",  # Pink
    "#84cc16",  # Lime
    "#f97316",  # Orange
    "#6366f1",  # Indigo
    "#14b8a6",  # Teal
    "#e11d48",  # Rose
    "#a855f7",  # Purple
    "#64748b",  # Slate
]


def _safe_json_dumps(obj: Any) -> str:
  """Serialize object to JSON safe for embedding inside HTML script tags."""
  return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def compute_summary_kpis(entries: Sequence[LedgerEntry]) -> dict[str, Any]:
  """Compute high-level summary KPIs across ledger entries.

  Returns a dictionary containing total_income, total_expenditure,
  net_transfers, net_refunds, net_balance, and transaction_count.
  """
  total_income = 0.0
  total_expenditure = 0.0
  net_transfers = 0.0
  net_refunds = 0.0
  net_balance = 0.0

  for e in entries:
    paid = float(e.paid_total)
    net_balance += paid

    if e.event_type == EventType.INCOME.value:
      total_income += paid
    elif e.event_type in (EventType.RECURRING.value, EventType.ONE_OFF.value):
      total_expenditure += abs(paid)
    elif e.event_type == EventType.TRANSFER.value:
      net_transfers += paid
    elif e.event_type == EventType.REFUND.value:
      net_refunds += paid

  return {
      "total_income": round(total_income, 2),
      "total_expenditure": round(total_expenditure, 2),
      "net_transfers": round(net_transfers, 2),
      "net_refunds": round(net_refunds, 2),
      "net_balance": round(net_balance, 2),
      "transaction_count": len(entries),
  }


def aggregate_category_breakdown(
    entries: Sequence[LedgerEntry],
    db_breakdown: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
  """
  Aggregate consumption expenditure by category with colors and reconciled
  100.0% percentages.

  Uses db_breakdown if provided, otherwise calculates directly from entries.
  """
  if db_breakdown is not None:
    raw_breakdown = [dict(item) for item in db_breakdown]
  else:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for e in entries:
      if e.event_type in (EventType.RECURRING.value, EventType.ONE_OFF.value):
        cat = e.category or "General"
        totals[cat] += abs(float(e.paid_total))
        counts[cat] += 1

    total_exp = sum(totals.values())
    raw_breakdown = []
    for cat, spent in sorted(totals.items(), key=lambda x: x[1], reverse=True):
      pct = (spent / total_exp * 100.0) if total_exp > 0 else 0.0
      raw_breakdown.append({
          "category": cat,
          "total_spent": round(spent, 2),
          "percentage": round(pct, 2),
          "count": counts[cat],
      })

  total_spend = sum(item["total_spent"] for item in raw_breakdown)
  if raw_breakdown and total_spend > 0:
    sum_pct = round(sum(item["percentage"] for item in raw_breakdown), 2)
    diff = round(100.0 - sum_pct, 2)
    if abs(diff) > 0.0 and abs(diff) < 0.1:
      raw_breakdown[0]["percentage"] = round(
          raw_breakdown[0]["percentage"] + diff, 2)

  # Assign palette colors
  for idx, item in enumerate(raw_breakdown):
    item["color"] = DEFAULT_PALETTE[idx % len(DEFAULT_PALETTE)]

  return raw_breakdown


def aggregate_timeline(
    entries: Sequence[LedgerEntry],
    month_filter: str | None = None,
) -> dict[str, Any]:
  """
  Aggregate income and expense time-series over months or days.

  If month_filter is supplied, aggregates daily (YYYY-MM-DD); otherwise monthly
  (YYYY-MM).
  Returns {'labels': [...], 'income_series': [...], 'expense_series': [...]}.
  """
  income_map: dict[str, float] = defaultdict(float)
  expense_map: dict[str, float] = defaultdict(float)

  for e in entries:
    time_key = (
        e.receipt_date if month_filter else e.month or e.receipt_date[:7]
    )

    paid = float(e.paid_total)
    if e.event_type == EventType.INCOME.value:
      income_map[time_key] += paid
    elif e.event_type in (EventType.RECURRING.value, EventType.ONE_OFF.value):
      expense_map[time_key] += abs(paid)

  all_keys = sorted(set(income_map.keys()) | set(expense_map.keys()))
  labels: list[str] = []
  income_series: list[float] = []
  expense_series: list[float] = []

  for k in all_keys:
    labels.append(k)
    income_series.append(round(income_map[k], 2))
    expense_series.append(round(expense_map[k], 2))

  return {
      "labels": labels,
      "income_series": income_series,
      "expense_series": expense_series,
  }


def aggregate_top_merchants(
    entries: Sequence[LedgerEntry],
    top_n: int = 10,
) -> list[dict[str, Any]]:
  """
  Aggregate top N merchants by total expenditure, grouping the rest into
  'Other'.

  Returns a list of dicts with merchant, total_spent, percentage, and count.
  """
  totals: dict[str, float] = defaultdict(float)
  counts: dict[str, int] = defaultdict(int)

  for e in entries:
    if e.event_type in (EventType.RECURRING.value, EventType.ONE_OFF.value):
      m = e.merchant or "Unknown"
      totals[m] += abs(float(e.paid_total))
      counts[m] += 1

  total_spend = sum(totals.values())
  sorted_merchants = sorted(totals.items(), key=lambda x: x[1], reverse=True)

  top_items = sorted_merchants[:top_n]
  remainder_items = sorted_merchants[top_n:]

  result: list[dict[str, Any]] = []
  for m, spent in top_items:
    pct = (spent / total_spend * 100.0) if total_spend > 0 else 0.0
    result.append({
        "merchant": m,
        "total_spent": round(spent, 2),
        "percentage": round(pct, 2),
        "count": counts[m],
    })

  if remainder_items:
    other_spent = sum(item[1] for item in remainder_items)
    other_count = sum(counts[item[0]] for item in remainder_items)
    other_pct = (other_spent / total_spend * 100.0) if total_spend > 0 else 0.0
    result.append({
        "merchant": "Other",
        "total_spent": round(other_spent, 2),
        "percentage": round(other_pct, 2),
        "count": other_count,
    })

  return result


def aggregate_event_types(
    entries: Sequence[LedgerEntry]
) -> list[dict[str, Any]]:
  """Aggregate transaction volume and counts across event types."""
  counts: dict[str, int] = defaultdict(int)
  volumes: dict[str, float] = defaultdict(float)

  for e in entries:
    etype = e.event_type
    counts[etype] += 1
    volumes[etype] += abs(float(e.paid_total))

  total_count = len(entries)
  result: list[dict[str, Any]] = []
  for etype in sorted(counts.keys()):
    pct = (counts[etype] / total_count * 100.0) if total_count > 0 else 0.0
    result.append({
        "event_type": etype,
        "count": counts[etype],
        "volume": round(volumes[etype], 2),
        "percentage": round(pct, 2),
    })

  return result


def aggregate_cumulative_balance(
    entries: Sequence[LedgerEntry]
) -> dict[str, Any]:
  """Compute chronological running prefix sum of all signed transactions."""
  sorted_entries = sorted(
      entries,
      key=lambda e: (e.receipt_date, e.receipt_id, e.entry_id),
  )

  labels: list[str] = []
  balance_series: list[float] = []
  current_balance = 0.0

  for e in sorted_entries:
    current_balance += float(e.paid_total)
    labels.append(e.receipt_date)
    balance_series.append(round(current_balance, 2))

  return {
      "labels": labels,
      "balance_series": balance_series,
  }


def parse_benchmark_csv(
    benchmark_path: str | Path
) -> dict[str, dict[str, Any]]:
  """Parse a benchmark national CPI CSV file.

  Supports standard columns: month, cpi_index, mom_inflation_percent, etc.
  Returns a mapping of month (YYYY-MM) -> metric dict.
  """
  p = Path(benchmark_path).resolve()
  if not p.exists():
    return {}

  result: dict[str, dict[str, Any]] = {}
  with p.open("r", encoding="utf-8", errors="replace") as f:
    reader = csv.DictReader(f)
    if not reader.fieldnames:
      return {}
    for row in reader:
      month = row.get("month", "").strip()
      if not month:
        continue
      cpi_val = None
      for key in ("cpi_index", "benchmark_cpi", "cpi", "index", "inpc"):
        if key in row and row[key]:
          try:
            cpi_val = float(row[key])
            break
          except ValueError:
            pass

      mom_val = None
      for key in (
          "mom_inflation_percent", "mom_percent", "mom", "inflation_mom"
      ):
        if key in row and row[key]:
          try:
            mom_val = float(row[key])
            break
          except ValueError:
            pass

      series_name = (
          row.get("series_name")
          or row.get("source")
          or row.get("country")
          or "National Benchmark"
      )
      result[month] = {
          "month": month,
          "cpi_index": cpi_val,
          "mom_inflation_percent": mom_val,
          "series_name": series_name,
      }
  return result


def compute_inflation_and_welfare(
    entries: Sequence[LedgerEntry], benchmark_path: str | Path | None = None,
) -> dict[str, Any]:
  """
  Compute personal inflation, Bennett exact decomposition, category PPC/ADI,
  and benchmark gap.

  Provides graceful degradation when fewer than 2 distinct months are present
  or when benchmark data is unavailable.
  """
  consumption_entries = [
      e for e in entries if e.event_type in (EventType.RECURRING.value, EventType.ONE_OFF.value)
  ]
  months_grouped: dict[str, list[LedgerEntry]] = defaultdict(list)
  for e in consumption_entries:
    m = e.month or e.receipt_date[:7]
    months_grouped[m].append(e)

  sorted_months = sorted(months_grouped.keys())

  if len(sorted_months) < 2:
    return {
        "status": "insufficient_history",
        "message": "At least 2 months of consumption history are required for inflation and welfare decomposition.",
        "has_data": False,
        "months": sorted_months,
        "bennett": None,
        "category_inflation": [],
        "cpi_comparison": {
            "labels": sorted_months,
            "personal_cpi": [100.0] if sorted_months else [],
            "national_cpi": [],
            "gap_series": [],
        },
        "latest_kpis": {
            "personal_mom": None,
            "benchmark_mom": None,
            "gap": None,
        },
    }

  # 1. Compute monthly item unit prices and quantities
  # For item i: quantity q_i, unit price p_i
  monthly_item_data: dict[str, dict[str, dict[str, float]]] = {}
  monthly_category_map: dict[str, dict[str, str]] = {}

  for m in sorted_months:
    item_qtys: dict[str, float] = defaultdict(float)
    item_totals: dict[str, float] = defaultdict(float)
    item_cat: dict[str, str] = {}

    for e in months_grouped[m]:
      item = e.item
      cat = e.category or "General"
      qty = float(e.quantity) if float(e.quantity) > 0 else 1.0
      paid = abs(float(e.paid_total))
      item_qtys[item] += qty
      item_totals[item] += paid
      item_cat[item] = cat

    monthly_item_data[m] = {
        item: {
            "q": item_qtys[item],
            "p": (
                item_totals[item] / item_qtys[item] if item_qtys[item] > 0
                else 0.0
            ),
            "spend": item_totals[item],
        } for item in item_qtys
    }
    monthly_category_map[m] = item_cat

  # 2. Bennett exact additive decomposition for the latest consecutive month
  # pair
  prev_m = sorted_months[-2]
  curr_m = sorted_months[-1]

  prev_items = monthly_item_data[prev_m]
  curr_items = monthly_item_data[curr_m]
  matched_items = sorted(set(prev_items.keys()) & set(curr_items.keys()))

  bennett: dict[str, Any] | None = None
  category_inflation: list[dict[str, Any]] = []
  personal_mom: float | None = None

  if matched_items:
    base_exp = sum(prev_items[i]["spend"] for i in matched_items)
    curr_exp = sum(curr_items[i]["spend"] for i in matched_items)
    delta_exp = curr_exp - base_exp

    delta_price = 0.0
    delta_quantity = 0.0

    for i in matched_items:
      p0, q0 = prev_items[i]["p"], prev_items[i]["q"]
      p1, q1 = curr_items[i]["p"], curr_items[i]["q"]

      delta_price += ((q0 + q1) / 2.0) * (p1 - p0)
      delta_quantity += ((p0 + p1) / 2.0) * (q1 - q0)

    # Bennett Exact Additive Invariant:
    # delta_price + delta_quantity == delta_exp
    bennett = {
        "prev_month": prev_m,
        "curr_month": curr_m,
        "matched_count": len(matched_items),
        "base_expenditure": round(base_exp, 2),
        "current_expenditure": round(curr_exp, 2),
        "delta_expenditure": round(delta_exp, 2),
        "price_effect": round(delta_price, 2),
        "quantity_effect": round(delta_quantity, 2),
        "residual": round(delta_exp - (delta_price + delta_quantity), 6),
        "waterfall_labels": [
            f"Base ({prev_m})",
            "Price Effect (Inflation)",
            "Quantity Effect (Volume)",
            f"Current ({curr_m})",
        ],
        "waterfall_values": [
            round(base_exp, 2),
            round(delta_price, 2),
            round(delta_quantity, 2),
            round(curr_exp, 2),
        ],
    }

    # 3. Category Inflation Decomposition (PPC & ADI)
    cat_matched_items: dict[str, list[str]] = defaultdict(list)
    for i in matched_items:
      cat = (
          monthly_category_map[curr_m].get(i) or
          monthly_category_map[prev_m].get(i, "General")
      )
      cat_matched_items[cat].append(i)

    total_matched_base = sum(prev_items[i]["spend"] for i in matched_items)

    for cat, items in sorted(cat_matched_items.items()):
      cat_base_spend = sum(prev_items[i]["spend"] for i in items)
      cat_curr_spend = sum(
          prev_items[i]["q"] * curr_items[i]["p"] for i in items
      )
      weight = (cat_base_spend /
                total_matched_base) if total_matched_base > 0 else 0.0

      # Laspeyres price inflation for category
      cat_infl = (cat_curr_spend / cat_base_spend -
                  1.0) if cat_base_spend > 0 else 0.0
      ppc = weight * cat_infl * 100.0
      adi = sum(
          prev_items[i]["q"] * (curr_items[i]["p"] - prev_items[i]["p"])
          for i in items
      )

      category_inflation.append({
          "category": cat,
          "base_spend": round(cat_base_spend, 2),
          "weight_percent": round(weight * 100.0, 2),
          "inflation_percent": round(cat_infl * 100.0, 2),
          "ppc": round(ppc, 2),
          "adi": round(adi, 2),
      })

    # Overall matched personal inflation MoM
    if total_matched_base > 0:
      matched_curr_laspeyres = sum(
          prev_items[i]["q"] * curr_items[i]["p"] for i in matched_items
      )
      personal_mom = round(
          (matched_curr_laspeyres / total_matched_base - 1.0) * 100.0, 2
      )

  # 4. Personal CPI Index series across all months
  # Base month is index 100.0
  personal_cpi_series: list[float] = [100.0]
  personal_mom_by_month: dict[str, float] = {}

  for idx in range(1, len(sorted_months)):
    m_prev = sorted_months[idx - 1]
    m_curr = sorted_months[idx]
    p_items = monthly_item_data[m_prev]
    c_items = monthly_item_data[m_curr]
    common = set(p_items.keys()) & set(c_items.keys())

    if common:
      base_val = sum(p_items[i]["spend"] for i in common)
      curr_val = sum(p_items[i]["q"] * c_items[i]["p"] for i in common)
      rel = (curr_val / base_val) if base_val > 0 else 1.0
      mom_pct = (rel - 1.0) * 100.0
      personal_mom_by_month[m_curr] = mom_pct
      personal_cpi_series.append(round(personal_cpi_series[-1] * rel, 2))
    else:
      personal_cpi_series.append(personal_cpi_series[-1])

  # 5. Benchmark comparisons
  benchmark_data = (
      parse_benchmark_csv(benchmark_path) if benchmark_path else {}
  )
  national_cpi_series: list[float | None] = []
  gap_series: list[float | None] = []
  benchmark_mom: float | None = None
  inflation_gap: float | None = None

  if benchmark_data:
    base_benchmark_cpi = None
    base_m = sorted_months[0]
    if (
        base_m in benchmark_data and
        benchmark_data[base_m]["cpi_index"] is not None
    ):
      base_benchmark_cpi = benchmark_data[base_m]["cpi_index"]

    for idx, m in enumerate(sorted_months):
      if m in benchmark_data:
        bm_info = benchmark_data[m]
        cpi = bm_info.get("cpi_index")
        if cpi is not None and base_benchmark_cpi:
          norm_cpi = round((cpi / base_benchmark_cpi) * 100.0, 2)
          national_cpi_series.append(norm_cpi)
          gap_series.append(round(personal_cpi_series[idx] - norm_cpi, 2))
        else:
          national_cpi_series.append(None)
          gap_series.append(None)
      else:
        national_cpi_series.append(None)
        gap_series.append(None)

    # Check latest month benchmark MoM
    if curr_m in benchmark_data:
      bm_info = benchmark_data[curr_m]
      if bm_info.get("mom_inflation_percent") is not None:
        benchmark_mom = round(float(bm_info["mom_inflation_percent"]), 2)
      elif (
          curr_m in benchmark_data
          and prev_m in benchmark_data
          and benchmark_data[curr_m].get("cpi_index")
          and benchmark_data[prev_m].get("cpi_index")
      ):
        c0 = benchmark_data[prev_m]["cpi_index"]
        c1 = benchmark_data[curr_m]["cpi_index"]
        if c0 > 0:
          benchmark_mom = round(((c1 / c0) - 1.0) * 100.0, 2)

    if personal_mom is not None and benchmark_mom is not None:
      inflation_gap = round(personal_mom - benchmark_mom, 2)

  return {
      "status": "success",
      "has_data": True,
      "months": sorted_months,
      "bennett": bennett,
      "category_inflation": category_inflation,
      "cpi_comparison": {
          "labels": sorted_months,
          "personal_cpi": personal_cpi_series,
          "national_cpi": national_cpi_series,
          "gap_series": gap_series,
      },
      "latest_kpis": {
          "personal_mom": personal_mom,
          "benchmark_mom": benchmark_mom,
          "gap": inflation_gap,
      },
  }


def generate_dashboard_html(
    entries: Sequence[LedgerEntry],
    summary_kpis: dict[str, Any],
    category_breakdown: list[dict[str, Any]],
    timeline_data: dict[str, Any],
    top_merchants: list[dict[str, Any]],
    event_type_distribution: list[dict[str, Any]],
    cumulative_balance: dict[str, Any],
    inflation_data: dict[str, Any],
    ledger_name: str = "PEIT Ledger",
    filter_description: str = "All Transactions",
) -> str:
  """
  Generate a self-contained, interactive HTML5 multi-graph dashboard with
  Chart.js.
  """
  # Escaped strings for security
  esc_ledger_name = html.escape(ledger_name)
  esc_filter_desc = html.escape(filter_description)

  # Chart Payload Preparations
  cat_labels = [item["category"] for item in category_breakdown]
  cat_spends = [item["total_spent"] for item in category_breakdown]
  cat_colors = [item.get("color", "#3b82f6") for item in category_breakdown]

  merchant_labels = [item["merchant"] for item in top_merchants]
  merchant_spends = [item["total_spent"] for item in top_merchants]

  event_labels = [item["event_type"] for item in event_type_distribution]
  event_counts = [item["count"] for item in event_type_distribution]
  event_colors = DEFAULT_PALETTE[: len(event_labels)]

  # Inflation / Tab 2 payloads
  has_inflation = inflation_data.get("has_data", False)
  bennett = inflation_data.get("bennett") or {}
  cpi_comp = inflation_data.get("cpi_comparison") or {}
  cat_infl = inflation_data.get("category_inflation") or []
  latest_kpis = inflation_data.get("latest_kpis") or {}

  bennett_labels = bennett.get("waterfall_labels", [])
  bennett_values = bennett.get("waterfall_values", [])

  cat_infl_labels = [item["category"] for item in cat_infl]
  cat_infl_ppc = [item["ppc"] for item in cat_infl]
  cat_infl_adi = [item["adi"] for item in cat_infl]

  chart_payload = {
      "category": {
          "labels": cat_labels,
          "data": cat_spends,
          "colors": cat_colors,
      },
      "timeline": timeline_data,
      "merchants": {
          "labels": merchant_labels,
          "data": merchant_spends,
      },
      "event_types": {
          "labels": event_labels,
          "data": event_counts,
          "colors": event_colors,
      },
      "cumulative": cumulative_balance,
      "cpi": {
          "labels": cpi_comp.get("labels", []),
          "personal": cpi_comp.get("personal_cpi", []),
          "national": cpi_comp.get("national_cpi", []),
      },
      "bennett": {
          "labels": bennett_labels,
          "values": bennett_values,
      },
      "cat_infl": {
          "labels": cat_infl_labels,
          "ppc": cat_infl_ppc,
          "adi": cat_infl_adi,
      },
  }

  chart_json = _safe_json_dumps(chart_payload)

  # Prepare Transaction Ledger Rows
  table_rows: list[str] = []
  for e in entries:
    esc_date = html.escape(e.receipt_date)
    esc_rid = html.escape(e.receipt_id)
    esc_merch = html.escape(e.merchant)
    esc_cat = html.escape(e.category)
    esc_item = html.escape(e.item)
    esc_store_tier = html.escape(
      e.store_tier)
    esc_brand_tier = html.escape(
      e.brand_tier)
    esc_prod_tier = html.escape(
      e.product_tier)

    def _fmt_rating(val: Any) -> str:
      try:
        return f"{float(val):.1f}" if val is not None else "5.0"
      except (ValueError, TypeError):
        return "5.0"

    esc_store_rating = _fmt_rating(e.store_rating)
    esc_brand_rating = _fmt_rating(e.brand_rating)
    esc_prod_rating = _fmt_rating(e.product_rating)

    esc_type = html.escape(e.event_type)
    esc_acct = html.escape(e.account)
    esc_curr = html.escape(e.currency)
    amount_float = float(e.paid_total)

    badge_class = "badge-gray"
    if e.event_type == EventType.INCOME.value:
      badge_class = "badge-green"
    elif e.event_type in (EventType.RECURRING.value, EventType.ONE_OFF.value):
      badge_class = "badge-red"
    elif e.event_type == EventType.TRANSFER.value:
      badge_class = "badge-blue"
    elif e.event_type == EventType.REFUND.value:
      badge_class = "badge-teal"

    amount_str = f"{amount_float:+,.2f} {esc_curr}"
    amount_color = "#10b981" if amount_float > 0 else (
        "#ef4444" if amount_float < 0 else "#94a3b8"
    )

    table_rows.append(f"""
<tr>
  <td><code>{esc_date}</code></td>
  <td><span class="text-muted" title="{esc_rid}">{esc_rid[:16]}...</span></td>
  <td><strong>{esc_merch}</strong></td>
  <td><span class="category-pill">{esc_cat}</span></td>
  <td>{esc_item}</td>
  <td><span class="badge badge-blue">{esc_store_tier}</span></td>
  <td class="text-center">{esc_store_rating}</td>
  <td><span class="badge badge-purple">{esc_brand_tier}</span></td>
  <td class="text-center">{esc_brand_rating}</td>
  <td><span class="badge badge-teal">{esc_prod_tier}</span></td>
  <td class="text-center">{esc_prod_rating}</td>
  <td><span class="badge {badge_class}">{esc_type}</span></td>
  <td class="text-right" style="color: {amount_color}; font-weight: 600;">{amount_str}</td>
  <td><span class="text-muted">{esc_acct}</span></td>
</tr>
    """)

  rendered_table_rows = (
      "\n".join(table_rows) if table_rows
      else "<tr><td colspan='14' class='text-center text-muted'>No transactions found.</td></tr>"
  )

  # Format summary KPI cards
  net_bal = summary_kpis.get("net_balance", 0.0)
  net_bal_color = "#10b981" if net_bal > 0 else (
      "#ef4444" if net_bal < 0 else "#f8fafc")

  # Format Tab 2 KPI cards
  pers_mom = latest_kpis.get("personal_mom")
  pers_mom_str = f"{pers_mom:+.2f}%" if pers_mom is not None else "N/A"
  bm_mom = latest_kpis.get("benchmark_mom")
  bm_mom_str = f"{bm_mom:+.2f}%" if bm_mom is not None else "N/A"
  gap_val = latest_kpis.get("gap")
  gap_str = f"{gap_val:+.2f} pp" if gap_val is not None else "N/A"
  gap_class = (
      "text-red" if (gap_val and gap_val > 0)
      else ("text-green" if (gap_val and gap_val < 0) else "")
  )

  alert_banner_html = ""
  if not has_inflation:
    msg = html.escape(inflation_data.get(
        "message",
        "Insufficient multi-month history for inflation decomposition."
    ))
    alert_banner_html = f"<div class='alert-banner'>⚠️ {msg}</div>"

  bennett_p = bennett.get('price_effect', 0.0)
  bennett_q = bennett.get('quantity_effect', 0.0)
  bennett_res = bennett.get('residual', 0.0)

  html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc_ledger_name} - PEIT Multi-Graph Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg-primary: #0f172a;
      --bg-card: #1e293b;
      --bg-card-hover: #24344d;
      --border-color: #334155;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-blue: #3b82f6;
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --accent-purple: #8b5cf6;
      --accent-amber: #f59e0b;
      --accent-teal: #14b8a6;
      --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg-primary);
      color: var(--text-main);
      font-family: var(--font-family);
      line-height: 1.5;
      padding: 1.5rem;
    }}

    /* Layout & Header */
    .dashboard-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 1.5rem;
    }}
    .header-title h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      letter-spacing: -0.025em;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .header-title .tag {{
      background: rgba(59, 130, 246, 0.2);
      color: var(--accent-blue);
      font-size: 0.75rem;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-weight: 600;
      border: 1px solid rgba(59, 130, 246, 0.4);
    }}
    .header-subtitle {{
      color: var(--text-muted);
      font-size: 0.875rem;
      margin-top: 0.25rem;
    }}

    /* Tabs */
    .tabs-nav {{
      display: flex;
      gap: 0.5rem;
      background: rgba(30, 41, 59, 0.7);
      padding: 0.35rem;
      border-radius: 0.75rem;
      border: 1px solid var(--border-color);
      margin-bottom: 1.5rem;
    }}
    .tab-button {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 0.6rem 1.2rem;
      font-size: 0.875rem;
      font-weight: 600;
      border-radius: 0.5rem;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .tab-button:hover {{
      color: var(--text-main);
      background: rgba(255, 255, 255, 0.05);
    }}
    .tab-button.active {{
      color: #fff;
      background: var(--accent-blue);
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }}
    .tab-content {{
      display: none;
    }}
    .tab-content.active {{
      display: block;
      animation: fadeIn 0.25s ease;
    }}
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* KPI Grid */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .kpi-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 0.75rem;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .kpi-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }}
    .kpi-title {{
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      font-weight: 600;
    }}
    .kpi-value {{
      font-size: 1.85rem;
      font-weight: 700;
      margin: 0.35rem 0;
      letter-spacing: -0.02em;
    }}
    .kpi-meta {{
      font-size: 0.8rem;
      color: var(--text-muted);
    }}

    /* Chart Grids */
    .chart-grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
      gap: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .chart-grid-3 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .chart-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 0.75rem;
      padding: 1.25rem;
      position: relative;
    }}
    .chart-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }}
    .chart-header h3 {{
      font-size: 1rem;
      font-weight: 600;
    }}
    .chart-container {{
      position: relative;
      height: 280px;
      width: 100%;
    }}

    /* Table & Search */
    .table-container {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 0.75rem;
      overflow: hidden;
    }}
    .table-toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1rem;
      border-bottom: 1px solid var(--border-color);
      background: rgba(15, 23, 42, 0.4);
    }}
    .search-box {{
      position: relative;
      width: 320px;
      max-width: 100%;
    }}
    .search-input {{
      width: 100%;
      background: var(--bg-primary);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 0.5rem 0.85rem;
      border-radius: 0.5rem;
      font-size: 0.875rem;
      outline: none;
      transition: border-color 0.2s;
    }}
    .search-input:focus {{
      border-color: var(--accent-blue);
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
      text-align: left;
    }}
    .data-table th {{
      background: rgba(15, 23, 42, 0.6);
      color: var(--text-muted);
      font-weight: 600;
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border-color);
      white-space: nowrap;
    }}
    .data-table td {{
      padding: 0.75rem 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    }}
    .data-table tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
    }}

    /* Badges & Utilities */
    .badge {{
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 0.25rem;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    .badge-green {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
    .badge-red {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
    .badge-blue {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; }}
    .badge-purple {{ background: rgba(139, 92, 246, 0.2); color: #c084fc; }}
    .badge-teal {{ background: rgba(20, 184, 166, 0.2); color: #2dd4bf; }}
    .badge-gray {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }}
    .category-pill {{
      background: rgba(255, 255, 255, 0.06);
      padding: 0.15rem 0.45rem;
      border-radius: 0.35rem;
      font-size: 0.78rem;
    }}
    .text-right {{ text-align: right; }}
    .text-center {{ text-align: center; }}
    .text-muted {{ color: var(--text-muted); }}
    .text-green {{ color: var(--accent-green); }}
    .text-red {{ color: var(--accent-red); }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8em;
    }}
    .alert-banner {{
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid rgba(245, 158, 11, 0.3);
      color: #fde68a;
      padding: 1rem;
      border-radius: 0.5rem;
      margin-bottom: 1.5rem;
      font-size: 0.9rem;
    }}

    @media (max-width: 768px) {{
      .chart-grid-2, .chart-grid-3 {{ grid-template-columns: 1fr; }}
      .table-toolbar {{ flex-direction: column; gap: 0.75rem; align-items: stretch; }}
      .search-box {{ width: 100%; }}
    }}
  </style>
</head>
<body>

  <!-- Header -->
  <header class="dashboard-header">
    <div class="header-title">
      <h1>
        {esc_ledger_name}
        <span class="tag">PEIT Analytics</span>
      </h1>
      <p class="header-subtitle">Filter Scope: {esc_filter_desc} &bull; Generated: {date.today().isoformat()}</p>
    </div>
    <div class="header-actions">
      <span class="text-muted" style="font-size: 0.85rem;">Total Transactions: <strong>{summary_kpis.get('transaction_count', 0)}</strong></span>
    </div>
  </header>

  <!-- Tab Navigation -->
  <nav class="tabs-nav">
    <button class="tab-button active" onclick="switchTab('tab-cashflow')">
      <span>📊 Cash Flow & Spending</span>
    </button>
    <button class="tab-button" onclick="switchTab('tab-inflation')">
      <span>📈 Inflation & Welfare</span>
    </button>
    <button class="tab-button" onclick="switchTab('tab-ledger')">
      <span>📋 Transaction Ledger</span>
    </button>
  </nav>

  <!-- TAB 1: Cash Flow & Spending -->
  <main id="tab-cashflow" class="tab-content active">
    <!-- 4 KPI Cards -->
    <section class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-title">Total Income</span>
        <div class="kpi-value text-green">${summary_kpis.get('total_income', 0.0):,.2f}</div>
        <span class="kpi-meta">Earned revenue & compensation</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Total Expenditure</span>
        <div class="kpi-value text-red">${summary_kpis.get('total_expenditure', 0.0):,.2f}</div>
        <span class="kpi-meta">Consumption & recurring bills</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Net Balance</span>
        <div class="kpi-value" style="color: {net_bal_color};">${net_bal:+,.2f}</div>
        <span class="kpi-meta">Cash flow delta across events</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Transfers & Refunds</span>
        <div class="kpi-value">${(summary_kpis.get('net_transfers', 0.0) + summary_kpis.get('net_refunds', 0.0)):+,.2f}</div>
        <span class="kpi-meta">Transfers: ${summary_kpis.get('net_transfers', 0.0):+,.2f} &bull; Refunds: ${summary_kpis.get('net_refunds', 0.0):+,.2f}</span>
      </div>
    </section>

    <!-- 5 Charts -->
    <div class="chart-grid-2">
      <!-- Chart 1: Category Breakdown Donut -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Category Expenditure Breakdown</h3>
          <span class="text-muted" style="font-size: 0.75rem;">100% Reconciled</span>
        </div>
        <div class="chart-container">
          <canvas id="chart-category"></canvas>
        </div>
      </div>

      <!-- Chart 2: Timeline Dual Bar -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Income vs. Expenditure Timeline</h3>
          <span class="text-muted" style="font-size: 0.75rem;">Chronological Cash Flow</span>
        </div>
        <div class="chart-container">
          <canvas id="chart-timeline"></canvas>
        </div>
      </div>
    </div>

    <div class="chart-grid-3">
      <!-- Chart 3: Top Merchants Horizontal Bar -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Top Merchants by Spend</h3>
        </div>
        <div class="chart-container">
          <canvas id="chart-merchants"></canvas>
        </div>
      </div>

      <!-- Chart 4: Event Type Distribution -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Event Type Distribution</h3>
        </div>
        <div class="chart-container">
          <canvas id="chart-event-types"></canvas>
        </div>
      </div>

      <!-- Chart 5: Cumulative Balance Area Line -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Cumulative Net Balance</h3>
        </div>
        <div class="chart-container">
          <canvas id="chart-cumulative"></canvas>
        </div>
      </div>
    </div>
  </main>

  <!-- TAB 2: Inflation & Welfare Analytics -->
  <main id="tab-inflation" class="tab-content">
    {alert_banner_html}

    <!-- 3 Inflation KPI Cards -->
    <section class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-title">Personal MoM Inflation</span>
        <div class="kpi-value text-red">{pers_mom_str}</div>
        <span class="kpi-meta">Matched basket price change</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">National Benchmark CPI</span>
        <div class="kpi-value text-blue">{bm_mom_str}</div>
        <span class="kpi-meta">Official headline CPI MoM rate</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Inflation Gap (Penalty)</span>
        <div class="kpi-value {gap_class}">{gap_str}</div>
        <span class="kpi-meta">Personal vs. National divergence</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Bennett Decomposition</span>
        <div class="kpi-value" style="font-size: 1.35rem;">
          P: ${bennett_p:+,.2f} / Q: ${bennett_q:+,.2f}
        </div>
        <span class="kpi-meta">Zero residual invariant: {bennett_res}</span>
      </div>
    </section>

    <!-- Tab 2 Charts -->
    <div class="chart-grid-2">
      <!-- Tab 2 Chart 1: Personal vs National CPI Index -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Personal vs. National CPI Index Tracking</h3>
          <span class="text-muted" style="font-size: 0.75rem;">Base = 100.0</span>
        </div>
        <div class="chart-container">
          <canvas id="chart-cpi"></canvas>
        </div>
      </div>

      <!-- Tab 2 Chart 2: Bennett Decomposition Waterfall -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Bennett Exact Additive Decomposition</h3>
          <span class="text-muted" style="font-size: 0.75rem;">Price Effect vs. Quantity Effect</span>
        </div>
        <div class="chart-container">
          <canvas id="chart-bennett"></canvas>
        </div>
      </div>
    </div>

    <!-- Tab 2 Chart 3: Category Inflation Contribution -->
    <div class="chart-card" style="margin-bottom: 1.5rem;">
      <div class="chart-header">
        <h3>Category Inflation Contribution (PPC & ADI)</h3>
        <span class="text-muted" style="font-size: 0.75rem;">Percentage-Point Contribution and Dollar Impact</span>
      </div>
      <div class="chart-container">
        <canvas id="chart-category-inflation"></canvas>
      </div>
    </div>
  </main>

  <!-- TAB 3: Filterable Transaction Ledger -->
  <main id="tab-ledger" class="tab-content">
    <div class="table-container">
      <div class="table-toolbar">
        <div class="search-box">
          <input type="text" id="table-search" class="search-input" placeholder="Search transactions (merchant, item, category, amount)..." onkeyup="filterLedgerTable()">
        </div>
        <div style="font-size: 0.85rem; color: var(--text-muted);">
          Showing <span id="visible-row-count">{len(entries)}</span> of {len(entries)} records
        </div>
      </div>
      <div style="overflow-x: auto;">
        <table class="data-table" id="transactions-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Receipt ID</th>
              <th>Merchant</th>
              <th>Category</th>
              <th>Item</th>
              <th>Store Tier</th>
              <th>Store Rating</th>
              <th>Brand Tier</th>
              <th>Brand Rating</th>
              <th>Product Tier</th>
              <th>Product Rating</th>
              <th>Type</th>
              <th class="text-right">Amount</th>
              <th>Account</th>
            </tr>
          </thead>
          <tbody>
            {rendered_table_rows}
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <!-- Embedded JSON Data Payload -->
  <script type="application/json" id="peit-chart-data">
    {chart_json}
  </script>

  <!-- Dashboard JavaScript Application -->
  <script>
    // Tab Switching Logic
    function switchTab(tabId) {{
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-button').forEach(el => el.classList.remove('active'));

      const activeContent = document.getElementById(tabId);
      if (activeContent) {{
        activeContent.classList.add('active');
      }}

      const clickedBtn = Array.from(document.querySelectorAll('.tab-button')).find(
        btn => btn.getAttribute('onclick').includes(tabId)
      );
      if (clickedBtn) {{
        clickedBtn.classList.add('active');
      }}
    }}

    // Real-Time Ledger Table Search Filter
    function filterLedgerTable() {{
      const query = document.getElementById('table-search').value.toLowerCase();
      const table = document.getElementById('transactions-table');
      const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
      let visibleCount = 0;

      for (let i = 0; i < rows.length; i++) {{
        const row = rows[i];
        const text = row.textContent.toLowerCase();
        if (text.indexOf(query) > -1) {{
          row.style.display = '';
          visibleCount++;
        }} else {{
          row.style.display = 'none';
        }}
      }}
      document.getElementById('visible-row-count').textContent = visibleCount;
    }}

    // Chart Initialization
    document.addEventListener('DOMContentLoaded', () => {{
      const rawData = document.getElementById('peit-chart-data').textContent;
      let chartData;
      try {{
        chartData = JSON.parse(rawData);
      }} catch (e) {{
        console.error("Failed to parse chart payload:", e);
        return;
      }}

      Chart.defaults.color = '#94a3b8';
      Chart.defaults.borderColor = '#334155';
      Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

      // 1. Category Breakdown Donut
      const catCtx = document.getElementById('chart-category');
      if (catCtx && chartData.category.labels.length > 0) {{
        new Chart(catCtx, {{
          type: 'doughnut',
          data: {{
            labels: chartData.category.labels,
            datasets: [{{
              data: chartData.category.data,
              backgroundColor: chartData.category.colors,
              borderWidth: 1,
              borderColor: '#1e293b'
            }}]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
              legend: {{ position: 'right', labels: {{
                  boxWidth: 12, padding: 12 }} }}
            }}
          }}
        }});
      }}

      // 2. Timeline Dual Bar Chart
      const timeCtx = document.getElementById('chart-timeline');
      if (timeCtx && chartData.timeline.labels.length > 0) {{
        new Chart(timeCtx, {{
          type: 'bar',
          data: {{
            labels: chartData.timeline.labels,
            datasets: [
              {{
                label: 'Income',
                data: chartData.timeline.income_series,
                backgroundColor: 'rgba(16, 185, 129, 0.85)',
                borderRadius: 4
              }},
              {{
                label: 'Expenditure',
                data: chartData.timeline.expense_series,
                backgroundColor: 'rgba(239, 68, 68, 0.85)',
                borderRadius: 4
              }}
            ]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            scales: {{
              x: {{ grid: {{ display: false }} }},
              y: {{ beginAtZero: true }}
            }}
          }}
        }});
      }}

      // 3. Top Merchants Horizontal Bar
      const merchCtx = document.getElementById('chart-merchants');
      if (merchCtx && chartData.merchants.labels.length > 0) {{
        new Chart(merchCtx, {{
          type: 'bar',
          data: {{
            labels: chartData.merchants.labels,
            datasets: [{{
              label: 'Spend',
              data: chartData.merchants.data,
              backgroundColor: 'rgba(59, 130, 246, 0.8)',
              borderRadius: 4
            }}]
          }},
          options: {{
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
              x: {{ beginAtZero: true, grid: {{ display: false }} }}
            }}
          }}
        }});
      }}

      // 4. Event Types Distribution Donut
      const eventCtx = document.getElementById('chart-event-types');
      if (eventCtx && chartData.event_types.labels.length > 0) {{
        new Chart(eventCtx, {{
          type: 'polarArea',
          data: {{
            labels: chartData.event_types.labels,
            datasets: [{{
              data: chartData.event_types.data,
              backgroundColor: chartData.event_types.colors
            }}]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
              legend: {{ position: 'right', labels: {{
                  boxWidth: 10, padding: 8 }} }}
            }}
          }}
        }});
      }}

      // 5. Cumulative Balance Area Line
      const cumCtx = document.getElementById('chart-cumulative');
      if (cumCtx && chartData.cumulative.labels.length > 0) {{
        new Chart(cumCtx, {{
          type: 'line',
          data: {{
            labels: chartData.cumulative.labels,
            datasets: [{{
              label: 'Balance',
              data: chartData.cumulative.balance_series,
              fill: true,
              backgroundColor: 'rgba(59, 130, 246, 0.15)',
              borderColor: '#3b82f6',
              tension: 0.25,
              pointRadius: 2
            }}]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            scales: {{
              x: {{ grid: {{ display: false }} }},
              y: {{ grid: {{ color: 'rgba(255, 255, 255, 0.05)' }} }}
            }}
          }}
        }});
      }}

      // Tab 2: CPI Comparison Chart
      const cpiCtx = document.getElementById('chart-cpi');
      if (cpiCtx && chartData.cpi.labels.length > 0) {{
        const cpiDatasets = [{{
          label: 'Personal CPI (Matched)',
          data: chartData.cpi.personal,
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          tension: 0.2,
          pointRadius: 4
        }}];

        if (chartData.cpi.national && chartData.cpi.national.some(v => v !== null)) {{
          cpiDatasets.push({{
            label: 'National Benchmark CPI',
            data: chartData.cpi.national,
            borderColor: '#3b82f6',
            backgroundColor: 'transparent',
            borderDash: [5, 5],
            tension: 0.2,
            pointRadius: 4
          }});
        }}

        new Chart(cpiCtx, {{
          type: 'line',
          data: {{
            labels: chartData.cpi.labels,
            datasets: cpiDatasets
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            scales: {{
              x: {{ grid: {{ display: false }} }},
              y: {{ beginAtZero: false }}
            }}
          }}
        }});
      }}

      // Tab 2: Bennett Waterfall Chart
      const bennettCtx = document.getElementById('chart-bennett');
      if (bennettCtx && chartData.bennett.labels.length > 0) {{
        const bValues = chartData.bennett.values;
        const bColors = bValues.map((v, idx) => {{
          if (idx === 0 || idx === bValues.length - 1) return '#3b82f6';
          return v >= 0 ? '#ef4444' : '#10b981';
        }});

        new Chart(bennettCtx, {{
          type: 'bar',
          data: {{
            labels: chartData.bennett.labels,
            datasets: [{{
              label: 'Amount ($)',
              data: bValues,
              backgroundColor: bColors,
              borderRadius: 4
            }}]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            scales: {{
              x: {{ grid: {{ display: false }} }},
              y: {{ beginAtZero: true }}
            }}
          }}
        }});
      }}

      // Tab 2: Category Inflation Diverging Bar Chart
      const catInflCtx = document.getElementById('chart-category-inflation');
      if (catInflCtx && chartData.cat_infl.labels.length > 0) {{
        new Chart(catInflCtx, {{
          type: 'bar',
          data: {{
            labels: chartData.cat_infl.labels,
            datasets: [
              {{
                label: 'Contribution to Inflation (pp)',
                data: chartData.cat_infl.ppc,
                backgroundColor: 'rgba(239, 68, 68, 0.8)',
                borderRadius: 4
              }},
              {{
                label: 'Dollar Impact ($)',
                data: chartData.cat_infl.adi,
                backgroundColor: 'rgba(245, 158, 11, 0.8)',
                borderRadius: 4
              }}
            ]
          }},
          options: {{
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {{
              x: {{ beginAtZero: true, grid: {{ display: false }} }}
            }}
          }}
        }});
      }}
    }});
  </script>
</body>
</html>
"""
  return html_template


def create_dashboard(
    ledger_path: str | Path,
    output_path: str | Path | None = None,
    month: str | None = None,
    category: str | None = None,
    merchant: str | None = None,
    event_type: str | None = None,
    account: str | None = None,
    benchmark_path: str | Path | None = None,
    open_browser: bool = False,
) -> Path:
  """Main entry point to compile and emit the PEIT interactive HTML dashboard.

  Auto-derives output_path if not provided.
  """
  ledger_file = Path(ledger_path).resolve()
  if not ledger_file.exists():
    raise FileNotFoundError(f"Ledger file not found: {ledger_file}")

  if output_path is None:
    output_file = ledger_file.parent / f"{ledger_file.stem}_dashboard.html"
  else:
    output_file = Path(output_path).resolve()

  # Query entries from authoritative ledger projection
  entries = list_entries(
      ledger_path=ledger_file,
      month=month,
      category=category,
      merchant=merchant,
      event_type=event_type,
      account=account,
  )

  # Fetch breakdown for category reconciled percentages
  db_breakdown = get_category_breakdown(
      ledger_file, month=month, account=account)

  # Execute data aggregations
  summary_kpis = compute_summary_kpis(entries)
  category_breakdown = aggregate_category_breakdown(
      entries, db_breakdown=db_breakdown)
  timeline_data = aggregate_timeline(entries, month_filter=month)
  top_merchants = aggregate_top_merchants(entries, top_n=10)
  event_type_distribution = aggregate_event_types(entries)
  cumulative_balance = aggregate_cumulative_balance(entries)
  inflation_data = compute_inflation_and_welfare(
      entries, benchmark_path=benchmark_path)

  # Filter description text
  filter_parts = []
  if month:
    filter_parts.append(f"Month: {month}")
  if category:
    filter_parts.append(f"Category: {category}")
  if merchant:
    filter_parts.append(f"Merchant: {merchant}")
  if event_type:
    filter_parts.append(f"Type: {event_type}")
  if account:
    filter_parts.append(f"Account: {account}")

  filter_desc = " &bull; ".join(
      filter_parts) if filter_parts else "All Records"

  # Generate self-contained HTML
  html_content = generate_dashboard_html(
      entries=entries,
      summary_kpis=summary_kpis,
      category_breakdown=category_breakdown,
      timeline_data=timeline_data,
      top_merchants=top_merchants,
      event_type_distribution=event_type_distribution,
      cumulative_balance=cumulative_balance,
      inflation_data=inflation_data,
      ledger_name=f"{ledger_file.stem.capitalize()} Ledger",
      filter_description=filter_desc,
  )

  # Write to disk
  output_file.parent.mkdir(parents=True, exist_ok=True)
  output_file.write_text(html_content, encoding="utf-8")

  # Open in browser if requested
  if open_browser:
    webbrowser.open(output_file.as_uri())

  return output_file


def generate_index_html(
    report: list[dict[str, Any]],
    source_name: str = "Price Index Report",
) -> str:
  """Generate a self-contained, interactive HTML5 price and expenditure index report with Chart.js."""
  esc_source_name = html.escape(source_name)

  # Prepare report data
  labels = [str(item.get("month", "")) for item in report]
  fixed_basket = [item.get("fixed_basket_index") for item in report]
  changing_exp = [item.get("changing_basket_expenditure_index")
                  for item in report]
  coverages = [item.get("coverage_percent") for item in report]
  moms = [item.get("mom_percent") for item in report]

  chart_payload = {
      "labels": labels,
      "fixed_basket": fixed_basket,
      "changing_expenditure": changing_exp,
      "coverage": coverages,
      "mom": moms,
  }
  chart_json = _safe_json_dumps(chart_payload)

  total_months = len(report)
  base_month = str(report[0].get("month", "N/A")) if report else "N/A"
  latest_month = str(report[-1].get("month", "N/A")) if report else "N/A"
  latest_fixed = report[-1].get("fixed_basket_index") if report else None
  latest_changing = report[-1].get(
      "changing_basket_expenditure_index") if report else None
  latest_mom = report[-1].get("mom_percent") if report else None
  avg_cov = round(sum(float(r.get("coverage_percent", 0.0) or 0.0)
                      for r in report) / total_months, 2) if total_months else 0.0
  total_exp = round(sum(float(r.get("expenditure", 0.0) or 0.0)
                        for r in report), 2) if total_months else 0.0

  latest_fixed_str = f"{latest_fixed:.2f}" if latest_fixed is not None else "N/A"
  latest_changing_str = f"{latest_changing:.2f}" if latest_changing is not None else "N/A"
  latest_mom_str = f"{latest_mom:+.2f}%" if latest_mom is not None else "N/A"
  latest_mom_color = "#ef4444" if (latest_mom and latest_mom > 0) else (
      "#10b981" if (latest_mom and latest_mom < 0) else "#94a3b8")

  # Build table rows
  table_rows: list[str] = []
  for item in report:
    m = html.escape(str(item.get("month", "")))
    fb = f"{item['fixed_basket_index']:.2f}" if item.get(
        "fixed_basket_index") is not None else "N/A"
    ce = f"{item['changing_basket_expenditure_index']:.2f}" if item.get(
        "changing_basket_expenditure_index") is not None else "N/A"
    cov_val = item.get("coverage_percent")
    cov_str = f"{cov_val:.1f}%" if cov_val is not None else "N/A"
    mom_val = item.get("mom_percent")
    mom_str = f"{mom_val:+.2f}%" if mom_val is not None else "—"
    mom_clr = "#ef4444" if (mom_val and mom_val > 0) else (
        "#10b981" if (mom_val and mom_val < 0) else "#94a3b8")
    exp_val = item.get("expenditure")
    exp_str = f"{exp_val:,.2f}" if exp_val is not None else "N/A"

    badge_cov = "badge-green" if (cov_val and cov_val >= 90) else (
        "badge-amber" if (cov_val and cov_val >= 70) else "badge-red")

    table_rows.append(f"""<tr>
      <td><code>{m}</code></td>
      <td class="text-right" style="font-weight: 600; color: #3b82f6;">{fb}</td>
      <td class="text-right" style="font-weight: 600; color: #10b981;">{ce}</td>
      <td class="text-center"><span class="badge {badge_cov}">{cov_str}</span></td>
      <td class="text-right" style="color: {mom_clr}; font-weight: 600;">{mom_str}</td>
      <td class="text-right text-muted">{exp_str}</td>
    </tr>""")

  rendered_table_rows = "\n".join(
      table_rows) if table_rows else "<tr><td colspan='6' class='text-center text-muted'>No inflation index data available.</td></tr>"

  return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc_source_name} - PEIT Price Index Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg-primary: #0f172a;
      --bg-card: #1e293b;
      --bg-card-hover: #24344d;
      --border-color: #334155;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-blue: #3b82f6;
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --accent-purple: #8b5cf6;
      --accent-amber: #f59e0b;
      --accent-teal: #14b8a6;
      --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg-primary);
      color: var(--text-main);
      font-family: var(--font-family);
      line-height: 1.5;
      padding: 1.5rem;
    }}

    .dashboard-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 1.5rem;
    }}
    .header-title h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      letter-spacing: -0.025em;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .header-title p {{
      color: var(--text-muted);
      font-size: 0.875rem;
      margin-top: 0.25rem;
    }}

    .badge {{
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .badge-blue {{ background: rgba(59, 130, 246, 0.2); color: var(--accent-blue); border: 1px solid rgba(59, 130, 246, 0.3); }}
    .badge-green {{ background: rgba(16, 185, 129, 0.2); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3); }}
    .badge-amber {{ background: rgba(245, 158, 11, 0.2); color: var(--accent-amber); border: 1px solid rgba(245, 158, 11, 0.3); }}
    .badge-red {{ background: rgba(239, 68, 68, 0.2); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.3); }}

    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .kpi-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 0.75rem;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }}
    .kpi-title {{
      font-size: 0.8rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .kpi-value {{
      font-size: 1.6rem;
      font-weight: 700;
    }}

    .card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 0.75rem;
      padding: 1.25rem;
      margin-bottom: 1.5rem;
    }}
    .card-title {{
      font-size: 1.1rem;
      font-weight: 600;
      margin-bottom: 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .chart-container {{
      position: relative;
      height: 380px;
      width: 100%;
    }}

    table.data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
      text-align: left;
    }}
    table.data-table th {{
      background: rgba(15, 23, 42, 0.6);
      padding: 0.75rem 1rem;
      color: var(--text-muted);
      font-weight: 600;
      border-bottom: 1px solid var(--border-color);
      text-transform: uppercase;
      font-size: 0.75rem;
    }}
    table.data-table td {{
      padding: 0.75rem 1rem;
      border-bottom: 1px solid rgba(51, 65, 85, 0.4);
    }}
    table.data-table tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
    }}
    .text-right {{ text-align: right; }}
    .text-center {{ text-align: center; }}
    .text-muted {{ color: var(--text-muted); }}

    .invariants-box {{
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid var(--border-color);
      border-radius: 0.5rem;
      padding: 1rem;
      font-size: 0.85rem;
      color: var(--text-muted);
      line-height: 1.6;
    }}
    .invariants-box strong {{
      color: var(--text-main);
    }}
  </style>
</head>
<body>

  <header class="dashboard-header">
    <div class="header-title">
      <h1>📊 {esc_source_name}</h1>
      <p>Personal Economic Inflation Tracker &bull; On-Demand Price Index Report</p>
    </div>
    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
      <span class="badge badge-blue">CLI On-Demand</span>
      <span class="badge badge-green">Evidence-Bounded</span>
      <span class="badge badge-amber">Base Month: {html.escape(base_month)}</span>
    </div>
  </header>

  <section class="kpi-grid">
    <div class="kpi-card">
      <span class="kpi-title">Months Analyzed</span>
      <span class="kpi-value">{total_months}</span>
      <span class="text-muted" style="font-size: 0.75rem;">{html.escape(base_month)} to {html.escape(latest_month)}</span>
    </div>
    <div class="kpi-card">
      <span class="kpi-title">Latest Fixed Basket Index</span>
      <span class="kpi-value" style="color: var(--accent-blue);">{latest_fixed_str}</span>
      <span class="text-muted" style="font-size: 0.75rem;">Base = 100.00</span>
    </div>
    <div class="kpi-card">
      <span class="kpi-title">Latest Expenditure Index</span>
      <span class="kpi-value" style="color: var(--accent-green);">{latest_changing_str}</span>
      <span class="text-muted" style="font-size: 0.75rem;">Changing Basket Volume</span>
    </div>
    <div class="kpi-card">
      <span class="kpi-title">Latest MoM Price Change</span>
      <span class="kpi-value" style="color: {latest_mom_color};">{latest_mom_str}</span>
      <span class="text-muted" style="font-size: 0.75rem;">Month-over-month</span>
    </div>
    <div class="kpi-card">
      <span class="kpi-title">Avg Matched Coverage</span>
      <span class="kpi-value">{avg_cov:.1f}%</span>
      <span class="text-muted" style="font-size: 0.75rem;">Consecutive item match</span>
    </div>
    <div class="kpi-card">
      <span class="kpi-title">Total Consumption Spend</span>
      <span class="kpi-value" style="font-size: 1.4rem;">{total_exp:,.2f}</span>
      <span class="text-muted" style="font-size: 0.75rem;">Recurring + One-off</span>
    </div>
  </section>

  <section class="card">
    <div class="card-title">
      <span>📈 Monthly Index Trajectory</span>
      <span class="text-muted" style="font-size: 0.8rem; font-weight: 400;">Fixed Basket vs. Changing Expenditure</span>
    </div>
    <div class="chart-container">
      <canvas id="indexTrajectoryChart"></canvas>
    </div>
  </section>

  <section class="card">
    <div class="card-title">
      <span>📋 Inflation & Expenditure Breakdown</span>
      <span class="text-muted" style="font-size: 0.8rem; font-weight: 400;">Derived Tabular Results</span>
    </div>
    <div style="overflow-x: auto;">
      <table class="data-table">
        <thead>
          <tr>
            <th>Month</th>
            <th class="text-right">Fixed Basket Index</th>
            <th class="text-right">Changing Expenditure Index</th>
            <th class="text-center">Matched Coverage</th>
            <th class="text-right">MoM Price Change</th>
            <th class="text-right">Monthly Spend</th>
          </tr>
        </thead>
        <tbody>
          {rendered_table_rows}
        </tbody>
      </table>
    </div>
  </section>

  <section class="invariants-box">
    <strong>Scientific Methodology & Invariant Guarantees:</strong>
    <ul style="margin-left: 1.5rem; margin-top: 0.5rem;">
      <li><strong>Matched Items Discipline ($M_t = I_{{t-1}} &cap; I_t$)</strong>: Price relatives are evaluated only on items purchased in consecutive months. No synthetic observations are created.</li>
      <li><strong>Base Normalization</strong>: Base period index is calibrated to 100.00. Changing expenditure index reflects total actual outlay relative to base outlay.</li>
      <li><strong>Zero Phantom Price Changes</strong>: Basket changes are strictly isolated from genuine price level movements.</li>
    </ul>
  </section>

  <script>
    const payload = {chart_json};

    window.addEventListener('DOMContentLoaded', () => {{
      const ctx = document.getElementById('indexTrajectoryChart');
      if (!ctx || !payload.labels.length) return;

      new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: payload.labels,
          datasets: [
            {{
              label: 'Fixed Basket Price Index',
              data: payload.fixed_basket,
              borderColor: '#3b82f6',
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              borderWidth: 2.5,
              pointBackgroundColor: '#3b82f6',
              pointRadius: 4,
              pointHoverRadius: 6,
              tension: 0.2,
              fill: false
            }},
            {{
              label: 'Changing Basket Expenditure Index',
              data: payload.changing_expenditure,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderWidth: 2.5,
              pointBackgroundColor: '#10b981',
              pointRadius: 4,
              pointHoverRadius: 6,
              tension: 0.2,
              fill: false
            }}
          ]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          interaction: {{
            mode: 'index',
            intersect: false
          }},
          plugins: {{
            legend: {{
              position: 'top',
              labels: {{
                color: '#f8fafc',
                font: {{
                  family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                }}
              }}
            }},
            tooltip: {{
              backgroundColor: '#1e293b',
              titleColor: '#f8fafc',
              bodyColor: '#94a3b8',
              borderColor: '#334155',
              borderWidth: 1,
              padding: 10,
              callbacks: {{
                afterBody: function(items) {{
                  const idx = items[0].dataIndex;
                  const cov = payload.coverage[idx];
                  const mom = payload.mom[idx];
                  return [
                    'Matched Coverage: ' + (cov !== null ? cov + '%' : 'N/A'),
                    'MoM Inflation: ' + (mom !== null ? (mom > 0 ? '+' : '') + mom + '%' : 'None')
                  ];
                }}
              }}
            }}
          }},
          scales: {{
            x: {{
              grid: {{ color: 'rgba(51, 65, 85, 0.3)' }},
              ticks: {{ color: '#94a3b8' }}
            }},
            y: {{
              grid: {{ color: 'rgba(51, 65, 85, 0.3)' }},
              ticks: {{ color: '#94a3b8' }},
              title: {{
                display: true,
                text: 'Index Value (Base = 100.0)',
                color: '#94a3b8'
              }}
            }}
          }}
        }}
      }});
    }});
  </script>
</body>
</html>"""


def create_index_report(
    report: list[dict[str, Any]],
    csv_path: str | Path,
    output_path: str | Path | None = None,
    open_browser: bool = False,
) -> Path:
  """Generate self-contained HTML5 price index report and write to disk."""
  csv_file = Path(csv_path).resolve()
  output_file = (
      Path(output_path).resolve() if output_path is not None
      else csv_file.parent / f"{csv_file.stem}_index.html"
  )

  html_content = generate_index_html(
      report=report,
      source_name=f"{csv_file.stem} Price Index Report",
  )

  output_file.parent.mkdir(parents=True, exist_ok=True)
  output_file.write_text(html_content, encoding="utf-8")

  if open_browser:
    webbrowser.open(output_file.as_uri())

  return output_file


def main(argv: list[str] | None = None) -> int:
  """Standalone command line entry point for python -m peit.dashboard."""
  parser = argparse.ArgumentParser(
      prog="python -m peit.dashboard",
      description="Generate interactive HTML5 visualizer dashboard for PEIT ledger",
  )
  parser.add_argument(
      "--html", action="store_true",
      help="Generate HTML dashboard (default mode)",
  )
  parser.add_argument(
      "--ledger", type=Path, required=True, metavar="LEDGER_PATH",
      help="Path to authoritative JSONL ledger file",
  )
  parser.add_argument(
      "-o", "--output", type=Path, metavar="OUTPUT_PATH",
      help="Output HTML file path (default: <ledger_stem>_dashboard.html)",
  )
  parser.add_argument(
      "--month", type=str, metavar="YYYY-MM",
      help="Filter by month in YYYY-MM format",
  )
  parser.add_argument(
      "--category", type=str, metavar="CATEGORY", help="Filter by category",
  )
  parser.add_argument(
      "--merchant", type=str, metavar="MERCHANT", help="Filter by merchant",
  )
  parser.add_argument(
      "--event-type", type=str, metavar="EVENT_TYPE",
      help="Filter by event type",
  )
  parser.add_argument(
      "--account", type=str, metavar="ACCOUNT",
      help="Filter by account identifier",
  )
  parser.add_argument(
      "--benchmark", type=Path, metavar="BENCHMARK_CSV",
      help="Path to reference national CPI benchmark CSV file",
  )
  parser.add_argument(
      "--open", action="store_true",
      help="Open generated dashboard in default browser",
  )

  args = parser.parse_args(argv)

  if args.month and not MONTH_RE.match(args.month):
    sys.stderr.write(
        f"Error: Invalid month format '{args.month}'. Expected YYYY-MM.\n"
    )
    return 2

  account_filter = (
      None if (args.account and args.account.lower() in ("all", "*", "none"))
      else args.account
  )

  try:
    out = create_dashboard(
        ledger_path=args.ledger,
        output_path=args.output,
        month=args.month,
        category=args.category,
        merchant=args.merchant,
        event_type=args.event_type,
        account=account_filter,
        benchmark_path=args.benchmark,
        open_browser=args.open,
    )
    print(f"Dashboard generated successfully at: {out}")
    return 0
  except Exception as e:
    sys.stderr.write(f"Error: {e}\n")
    return 2


if __name__ == "__main__":
  sys.exit(main())
