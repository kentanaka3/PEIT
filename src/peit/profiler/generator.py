"""Profiler generator algorithm and market dynamics simulation engine.

Produces randomized, noisy receipt streams (CSV rows matching Schema)
and ground-truth JSON manifests from Profile × Market × Seed specifications.
"""

from __future__ import annotations

import calendar
import math
import random
from typing import Any

from peit.profiler.market import Market
from peit.profiler.profile import Profile

HEADERS = [
    "receipt_id",
    "receipt_date",
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
]


def generate(
    profile: Profile,
    market: Market,
    seed: int | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
  """Generate receipt rows from Profile × Market with independent item purchases.

  Maintains persistent shelf prices per (item, merchant) across simulation months
  and tracks elapsed renewal periods for hazard scheduling.

  Args:
      profile: The consumer profile definition (ground truth signal).
      market: The market price catalog and pricing dynamics engine.
      seed: Optional RNG seed for 100% deterministic reproducibility.

  Returns:
      tuple of (rows, ground_truth_manifest)
  """
  rng = random.Random(seed)
  rows: list[dict[str, str]] = []

  # Persistent shelf prices per (item, merchant) across months
  shelf_prices: dict[tuple[str, str], float] = {}

  # State for hazard renewal scheduling: last month each item was purchased
  last_purchased_month: dict[str, int] = {
      item.item: -999 for item in profile.basket}

  # Tracking metrics for the ground truth manifest
  item_counts: dict[str, int] = {}
  store_counts: dict[str, dict[str, int]] = {}
  brand_counts: dict[str, dict[str, int]] = {}
  price_trajectories: dict[str, list[dict[str, Any]]] = {}

  receipt_counter = 1

  for month_offset in range(profile.months_count):
    year = profile.start_year + (month_offset // 12)
    calendar_month = (month_offset % 12) + 1
    month_str = f"{year:04d}-{calendar_month:02d}"
    max_days = calendar.monthrange(year, calendar_month)[1]

    purchased_this_month: list[dict[str, str]] = []
    monthly_income = 0.0

    # a. Inject deterministic scenarios matching month_offset
    if profile.scenarios:
      for sc in profile.scenarios:
        if sc.month_offset == month_offset:
          sc_row = sc.row
          row_dict: dict[str, str] = {}
          for col in HEADERS:
            val = sc_row.get(col, "")
            if isinstance(val, float):
              row_dict[col] = f"{val:.2f}"
            elif val is None:
              row_dict[col] = ""
            else:
              row_dict[col] = str(val)

          if not row_dict.get("receipt_id"):
            row_dict["receipt_id"] = (
                f"SCEN-{year:04d}{calendar_month:02d}-{receipt_counter:05d}"
            )
            receipt_counter += 1
          if not row_dict.get("receipt_date"):
            row_dict["receipt_date"] = f"{year:04d}-{calendar_month:02d}-15"
          if not row_dict.get("currency"):
            row_dict["currency"] = profile.currency
          if not row_dict.get("store_tier"):
            row_dict["store_tier"] = "A"
          if not row_dict.get("store_rating"):
            row_dict["store_rating"] = "5.0"
          if not row_dict.get("brand_tier"):
            row_dict["brand_tier"] = "A"
          if not row_dict.get("brand_rating"):
            row_dict["brand_rating"] = "5.0"
          if not row_dict.get("product_tier"):
            row_dict["product_tier"] = "A"
          if not row_dict.get("product_rating"):
            row_dict["product_rating"] = "5.0"
          if not row_dict.get("availability"):
            row_dict["availability"] = "in_stock"

          rows.append(row_dict)

    # b. Generate income rows from profile.income
    for inc in profile.income:
      for day_spec in inc.schedule:
        day = max(1, min(day_spec, max_days))
        receipt_date = f"{year:04d}-{calendar_month:02d}-{day:02d}"
        receipt_id = f"REC-{year:04d}{calendar_month:02d}-{receipt_counter:05d}"
        receipt_counter += 1

        noise = rng.gauss(0.0, inc.volatility) if inc.volatility > 0.0 else 0.0
        actual_amount = round(inc.amount * (1.0 + noise), 2)
        monthly_income += actual_amount

        income_row: dict[str, str] = {
            "receipt_id": receipt_id,
            "receipt_date": receipt_date,
            "merchant": inc.merchant,
            "item": inc.item,
            "brand": "",
            "category": inc.category,
            "quantity": "1",
            "pack_size": "1",
            "unit": "piece",
            "unit_price": f"{actual_amount:.2f}",
            "currency": profile.currency,
            "discount": "0.00",
            "fee": "0.00",
            "tax": "0.00",
            "deposit": "0.00",
            "paid_total": f"{actual_amount:.2f}",
            "event_type": inc.event_type if inc.event_type else "income",
            "store_tier": "A",
            "store_rating": "5.0",
            "brand_tier": "A",
            "brand_rating": "5.0",
            "product_tier": "A",
            "product_rating": "5.0",
            "availability": "in_stock",
            "notes": f"Income: {inc.description}",
        }
        rows.append(income_row)

    # c. For each BasketItem in profile.basket
    for basket_item in profile.basket:
      scheduling = basket_item.scheduling
      occasions = 0

      if scheduling.mode == "count":
        occasions = scheduling.count
      elif scheduling.mode == "deterministic":
        if month_offset >= scheduling.offset_months:
          interval = scheduling.interval_months
          if (month_offset - scheduling.offset_months) % interval == 0:
            if (
                scheduling.target_months is None
                or calendar_month in scheduling.target_months
            ):
              occasions = 1
      elif scheduling.mode == "hazard":
        delta_t = month_offset - \
            last_purchased_month.get(basket_item.item, -999)
        if delta_t < scheduling.min_gap_months:
          occasions = 0
        elif delta_t >= scheduling.max_gap_months:
          occasions = 1
        else:
          # Discrete Weibull renewal hazard calculation
          scale = scheduling.expected_interval_months / math.gamma(
              1.0 + 1.0 / scheduling.hazard_shape
          )
          cdf = 1.0 - math.exp(-((delta_t / scale) ** scheduling.hazard_shape))
          cdf_prev = 1.0 - math.exp(
              -(((delta_t - 1.0) / scale) ** scheduling.hazard_shape)
          )
          hazard = (cdf - cdf_prev) / \
              (1.0 - cdf_prev) if cdf_prev < 1.0 else 1.0
          if rng.random() < hazard:
            occasions = 1
          else:
            occasions = 0

      for _ in range(occasions):
        last_purchased_month[basket_item.item] = month_offset

        store_pref = basket_item.preferences.choose_store(rng)
        brand_pref = basket_item.preferences.choose_brand(rng)
        prod_pref = basket_item.preferences.choose_product(
            rng, default_name=basket_item.product
        )

        merchant = store_pref.merchant
        store_tier = store_pref.tier
        store_rating = f"{store_pref.rating:.1f}"

        brand = brand_pref.brand
        brand_tier = brand_pref.tier
        brand_rating = f"{brand_pref.rating:.1f}"

        product_tier = prod_pref.tier
        product_rating = f"{prod_pref.rating:.1f}"

        # Unit price from market dynamics with persistent shelf price
        current_shelf = shelf_prices.get((basket_item.item, merchant))
        unit_price = market.price_at(
            basket_item.item,
            merchant,
            month_offset,
            basket_item.pack_size,
            rng,
            current_shelf_price=current_shelf,
        )
        shelf_prices[(basket_item.item, merchant)] = unit_price

        # Independent receipt_date within month
        day = rng.randint(1, max_days)
        receipt_date = f"{year:04d}-{calendar_month:02d}-{day:02d}"
        receipt_id = f"REC-{year:04d}{calendar_month:02d}-{receipt_counter:05d}"
        receipt_counter += 1

        # Discount seeking behavior
        gross = basket_item.quantity * basket_item.pack_size * unit_price
        discount = 0.0
        if (
            rng.random()
            < profile.financial_behavior.discount_seeking_probability
        ):
          discount_rate = getattr(
              profile.financial_behavior, "discount_rate", 0.15
          )
          discount = round(gross * discount_rate, 2)

        paid_total = -round(gross - discount, 2)

        row = {
            "receipt_id": receipt_id,
            "receipt_date": receipt_date,
            "merchant": merchant,
            "item": basket_item.item,
            "brand": brand,
            "category": basket_item.category,
            "quantity": str(basket_item.quantity),
            "pack_size": str(basket_item.pack_size),
            "unit": basket_item.unit,
            "unit_price": f"{unit_price:.2f}",
            "currency": profile.currency,
            "discount": f"{discount:.2f}",
            "fee": "0.00",
            "tax": "0.00",
            "deposit": "0.00",
            "paid_total": f"{paid_total:.2f}",
            "event_type": "recurring",
            "store_tier": store_tier,
            "store_rating": store_rating,
            "brand_tier": brand_tier,
            "brand_rating": brand_rating,
            "product_tier": product_tier,
            "product_rating": product_rating,
            "availability": "in_stock",
            "notes": "",
        }
        rows.append(row)
        purchased_this_month.append(row)

        # Update manifest tracking counters
        item_counts[basket_item.item] = item_counts.get(
            basket_item.item, 0) + 1
        if basket_item.item not in brand_counts:
          brand_counts[basket_item.item] = {}
        brand_counts[basket_item.item][brand] = (
            brand_counts[basket_item.item].get(brand, 0) + 1
        )
        if basket_item.item not in store_counts:
          store_counts[basket_item.item] = {}
        store_counts[basket_item.item][merchant] = (
            store_counts[basket_item.item].get(merchant, 0) + 1
        )
        if basket_item.item not in price_trajectories:
          price_trajectories[basket_item.item] = []
        price_trajectories[basket_item.item].append({
            "month_offset": month_offset,
            "calendar_month": month_str,
            "merchant": merchant,
            "unit_price": unit_price,
        })

    # d. Financial behavior rows
    # Monthly savings transfer
    if profile.financial_behavior.savings_rate > 0.0 and monthly_income > 0.0:
      savings = round(
          monthly_income * profile.financial_behavior.savings_rate, 2
      )
      savings_row = {
          "receipt_id": f"REC-{year:04d}{calendar_month:02d}-{receipt_counter:05d}",
          "receipt_date": f"{year:04d}-{calendar_month:02d}-{max_days:02d}",
          "merchant": profile.financial_behavior.savings_merchant,
          "item": "savings transfer",
          "brand": "",
          "category": "Savings and investments",
          "quantity": "1",
          "pack_size": "1",
          "unit": "piece",
          "unit_price": f"{savings:.2f}",
          "currency": profile.currency,
          "discount": "0.00",
          "fee": "0.00",
          "tax": "0.00",
          "deposit": "0.00",
          "paid_total": f"{-savings:.2f}",
          "event_type": "transfer",
          "store_tier": "A",
          "store_rating": "5.0",
          "brand_tier": "A",
          "brand_rating": "5.0",
          "product_tier": "A",
          "product_rating": "5.0",
          "availability": "in_stock",
          "notes": "Monthly dedicated savings transfer",
      }
      receipt_counter += 1
      rows.append(savings_row)

    # Occasional refund
    if purchased_this_month and (
        rng.random() < profile.financial_behavior.refund_probability
    ):
      chosen = rng.choice(purchased_this_month)
      refund_day = rng.randint(1, max_days)
      chosen_paid = abs(float(chosen["paid_total"]))
      refund_row = {
          "receipt_id": f"REC-{year:04d}{calendar_month:02d}-{receipt_counter:05d}",
          "receipt_date": f"{year:04d}-{calendar_month:02d}-{refund_day:02d}",
          "merchant": chosen["merchant"],
          "item": chosen["item"],
          "brand": chosen["brand"],
          "category": chosen["category"],
          "quantity": chosen["quantity"],
          "pack_size": chosen["pack_size"],
          "unit": chosen["unit"],
          "unit_price": chosen["unit_price"],
          "currency": chosen["currency"],
          "discount": "0.00",
          "fee": "0.00",
          "tax": "0.00",
          "deposit": "0.00",
          "paid_total": f"{chosen_paid:.2f}",
          "event_type": "refund",
          "store_tier": chosen.get("store_tier", "A"),
          "store_rating": chosen.get("store_rating", "5.0"),
          "brand_tier": chosen.get("brand_tier", "A"),
          "brand_rating": chosen.get("brand_rating", "5.0"),
          "product_tier": chosen.get("product_tier", "A"),
          "product_rating": chosen.get("product_rating", "5.0"),
          "availability": chosen.get("availability", "in_stock"),
          "notes": f"Refund for {chosen['receipt_id']}",
      }
      receipt_counter += 1
      rows.append(refund_row)

  # Build ground truth manifest dict
  manifest: dict[str, Any] = {
      "seed": seed,
      "profile": profile.to_dict(),
      "market": market.to_dict(),
      "total_rows": len(rows),
      "item_counts": item_counts,
      "store_counts": store_counts,
      "brand_counts": brand_counts,
      "price_trajectories": price_trajectories,
      "final_shelf_prices": {
          f"{item}@{merchant}": price
          for (item, merchant), price in shelf_prices.items()
      },
  }

  return rows, manifest
