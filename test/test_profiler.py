"""Tests for the PEIT Profiler dataclasses, serialization, and market dynamics."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import random
import subprocess
import sys

import pytest

from peit.profiler import (
    HEADERS,
    BasketItem,
    BrandPreference,
    CatalogItem,
    CharmPricing,
    FinancialBehavior,
    IncomeSource,
    ItemPreferences,
    Market,
    PackTierPriceCurve,
    ProductPreference,
    Profile,
    Scenario,
    SchedulePolicy,
    StorePreference,
    TieredPreference,
)


# ---------------------------------------------------------------------------
# 1. SchedulePolicy validation and parsing tests
# ---------------------------------------------------------------------------


def test_schedule_policy_valid_modes():
  """Verify valid initialization across count, deterministic, and hazard modes."""
  sp_count = SchedulePolicy(mode="count", count=4)
  assert sp_count.mode == "count"
  assert sp_count.count == 4

  sp_det = SchedulePolicy(
      mode="deterministic",
      interval_months=2,
      offset_months=1,
      target_months=[6, 12],
  )
  assert sp_det.mode == "deterministic"
  assert sp_det.interval_months == 2
  assert sp_det.target_months == [6, 12]

  sp_haz = SchedulePolicy(
      mode="hazard",
      expected_interval_months=4.5,
      hazard_shape=2.0,
      min_gap_months=1,
      max_gap_months=8,
  )
  assert sp_haz.mode == "hazard"
  assert sp_haz.expected_interval_months == 4.5
  assert sp_haz.min_gap_months == 1
  assert sp_haz.max_gap_months == 8


def test_schedule_policy_invalid_modes():
  """Verify SchedulePolicy raises ValueError for invalid mode or parameters."""
  with pytest.raises(ValueError, match="Invalid SchedulePolicy mode"):
    SchedulePolicy(mode="random_mode")  # type: ignore

  with pytest.raises(ValueError, match="count mode requires count >= 1"):
    SchedulePolicy(mode="count", count=0)

  with pytest.raises(
      ValueError, match="deterministic mode requires interval_months >= 1"
  ):
    SchedulePolicy(mode="deterministic", interval_months=0)

  with pytest.raises(
      ValueError, match="target_months must contain valid calendar months"
  ):
    SchedulePolicy(mode="deterministic", target_months=[0, 13])

  with pytest.raises(
      ValueError, match="hazard mode requires expected_interval_months > 0"
  ):
    SchedulePolicy(mode="hazard", expected_interval_months=0.0)

  with pytest.raises(
      ValueError, match="hazard mode requires hazard_shape > 0"
  ):
    SchedulePolicy(mode="hazard", hazard_shape=-1.0)

  with pytest.raises(
      ValueError, match="hazard mode requires min_gap_months >= 0"
  ):
    SchedulePolicy(mode="hazard", min_gap_months=-1)

  with pytest.raises(ValueError, match="cannot be less than min_gap_months"):
    SchedulePolicy(mode="hazard", min_gap_months=5, max_gap_months=3)


# ---------------------------------------------------------------------------
# 2. Store & Brand Preferences and Description Rendering
# ---------------------------------------------------------------------------


def test_store_and_brand_preferences_validation():
  """
  Verify TieredPreference base class and Store/Brand/Product preference
  subclasses.
  """
  # Base class validation
  tp = TieredPreference(name="test", weight=1.0, tier="A", rating=5.0)
  assert tp.name == "test"
  assert tp.weight == 1.0
  assert tp.tier == "A"
  assert tp.rating == 5.0
  assert tp.to_dict() == {
      "name": "test",
      "weight": 1.0,
      "tier": "A",
      "rating": 5.0
  }
  tp_reconstructed = TieredPreference.from_dict(tp.to_dict())
  assert tp_reconstructed == tp

  with pytest.raises(ValueError, match="weight must be non-negative"):
    TieredPreference(name="test", weight=-0.1)

  with pytest.raises(ValueError, match="tier must be in A-E"):
    TieredPreference(name="test", weight=1.0, tier="Z")

  with pytest.raises(ValueError, match="rating must be between 1.0 and 5.0"):
    TieredPreference(name="test", weight=1.0, rating=0.5)

  with pytest.raises(ValueError, match="rating must be between 1.0 and 5.0"):
    TieredPreference(name="test", weight=1.0, rating=5.5)

  # StorePreference
  sp = StorePreference(merchant="Store A", weight=0.8, tier="A", rating=4.8)
  assert sp.merchant == "Store A"
  assert sp.name == "Store A"
  assert sp.weight == 0.8
  assert sp.tier == "A"
  assert sp.rating == 4.8
  sp.merchant = "Store B"
  assert sp.name == "Store B"
  assert "Store B" in repr(sp)
  sp_dict = sp.to_dict()
  assert sp_dict == {
      "merchant": "Store B",
      "weight": 0.8,
      "tier": "A",
      "rating": 4.8
  }
  sp_loaded = StorePreference.from_dict(sp_dict)
  assert sp_loaded.merchant == "Store B"
  assert sp_loaded.weight == 0.8
  assert sp_loaded.tier == "A"
  assert sp_loaded.rating == 4.8

  with pytest.raises(ValueError, match="weight must be non-negative"):
    StorePreference(merchant="Store A", weight=-0.1)

  with pytest.raises(ValueError, match="tier must be in A-E"):
    StorePreference(merchant="Store A", weight=1.0, tier="X")

  # BrandPreference
  bp = BrandPreference(brand="Brand A", weight=0.5, tier="B", rating=4.5)
  assert bp.brand == "Brand A"
  assert bp.name == "Brand A"
  assert bp.weight == 0.5
  assert bp.tier == "B"
  assert bp.rating == 4.5
  bp.brand = "Brand C"
  assert bp.name == "Brand C"
  assert "Brand C" in repr(bp)
  bp_dict = bp.to_dict()
  assert bp_dict == {
      "brand": "Brand C",
      "weight": 0.5,
      "tier": "B",
      "rating": 4.5
  }
  bp_loaded = BrandPreference.from_dict(bp_dict)
  assert bp_loaded.brand == "Brand C"
  assert bp_loaded.weight == 0.5
  assert bp_loaded.tier == "B"
  assert bp_loaded.rating == 4.5

  with pytest.raises(ValueError, match="weight must be non-negative"):
    BrandPreference(brand="Brand A", weight=-1.0)

  # ProductPreference
  pp = ProductPreference(product="Prod A", weight=1.0, tier="C", rating=3.5)
  assert pp.product == "Prod A"
  assert pp.name == "Prod A"
  assert pp.weight == 1.0
  assert pp.tier == "C"
  assert pp.rating == 3.5
  pp.product = "Prod D"
  assert pp.name == "Prod D"
  assert "Prod D" in repr(pp)
  pp_dict = pp.to_dict()
  assert pp_dict == {"product": "Prod D",
                     "weight": 1.0, "tier": "C", "rating": 3.5}
  pp_loaded = ProductPreference.from_dict(pp_dict)
  assert pp_loaded.product == "Prod D"
  assert pp_loaded.weight == 1.0
  assert pp_loaded.tier == "C"
  assert pp_loaded.rating == 3.5

  with pytest.raises(ValueError, match="weight must be non-negative"):
    ProductPreference(product="Prod A", weight=-0.5)


def test_item_preferences_validation_and_sampling():
  """Verify ItemPreferences sampling, empty fallbacks, and serialization."""
  sp1 = StorePreference("Store 1", 1.0, "A", 4.9)
  bp1 = BrandPreference("Brand 1", 1.0, "B", 4.2)
  pp1 = ProductPreference("Prod 1", 1.0, "C", 3.8)

  prefs = ItemPreferences(stores=[sp1], brands=[bp1], products=[pp1])
  rng = random.Random(42)

  chosen_s = prefs.choose_store(rng)
  assert chosen_s.merchant == "Store 1"
  assert chosen_s.tier == "A"
  assert chosen_s.rating == 4.9

  chosen_b = prefs.choose_brand(rng)
  assert chosen_b.brand == "Brand 1"
  assert chosen_b.tier == "B"
  assert chosen_b.rating == 4.2

  chosen_p = prefs.choose_product(rng, default_name="Fallback")
  assert chosen_p.product == "Prod 1"
  assert chosen_p.tier == "C"
  assert chosen_p.rating == 3.8

  # Serialization roundtrip
  d = prefs.to_dict()
  loaded_prefs = ItemPreferences.from_dict(d)
  assert len(loaded_prefs.stores) == 1
  assert loaded_prefs.stores[0].merchant == "Store 1"
  assert len(loaded_prefs.brands) == 1
  assert loaded_prefs.brands[0].brand == "Brand 1"
  assert len(loaded_prefs.products) == 1
  assert loaded_prefs.products[0].product == "Prod 1"

  # Empty fallbacks
  empty_prefs = ItemPreferences()
  fallback_s = empty_prefs.choose_store(rng)
  assert fallback_s.merchant == "Store"
  assert fallback_s.tier == "A"
  assert fallback_s.rating == 5.0

  fallback_b = empty_prefs.choose_brand(rng)
  assert fallback_b.brand == ""
  assert fallback_b.tier == "A"
  assert fallback_b.rating == 5.0

  fallback_p = empty_prefs.choose_product(rng, default_name="DefaultProd")
  assert fallback_p.product == "DefaultProd"
  assert fallback_p.tier == "A"
  assert fallback_p.rating == 5.0


def test_basket_item_preferences_and_properties():
  """
  Verify BasketItem construction with preferences or individual lists, and
  properties.
  """
  sched = SchedulePolicy(mode="count", count=1)
  sp = StorePreference("Store A", 1.0, "A", 4.8)
  bp = BrandPreference("Brand B", 1.0, "B", 4.5)
  pp = ProductPreference("Leche", 1.0, "A", 5.0)

  # 1. Constructed with individual preference lists
  item1 = BasketItem(
      item="milk 1 l",
      product="Leche Entera",
      category="Food and beverages",
      unit="L",
      scheduling=sched,
      store_preferences=[sp],
      brand_preferences=[bp],
      product_preferences=[pp],
  )
  assert len(item1.store_preferences) == 1
  assert item1.store_preferences[0].merchant == "Store A"
  assert len(item1.brand_preferences) == 1
  assert item1.brand_preferences[0].brand == "Brand B"
  assert len(item1.product_preferences) == 1
  assert item1.product_preferences[0].product == "Leche"
  assert isinstance(item1.preferences, ItemPreferences)

  # 2. Constructed with preferences: ItemPreferences
  item_prefs = ItemPreferences(stores=[sp], brands=[bp], products=[pp])
  item2 = BasketItem(
      item="milk 1 l",
      product="Leche Entera",
      category="Food and beverages",
      unit="L",
      scheduling=sched,
      preferences=item_prefs,
  )
  assert item2.preferences == item_prefs
  assert item2.store_preferences == [sp]
  assert item2.brand_preferences == [bp]
  assert item2.product_preferences == [pp]

  # Test serialization
  item_dict = item2.to_dict()
  assert "store_preferences" in item_dict
  assert "brand_preferences" in item_dict
  assert "product_preferences" in item_dict
  item_loaded = BasketItem.from_dict(item_dict)
  assert item_loaded.store_preferences[0].merchant == "Store A"
  assert item_loaded.store_preferences[0].tier == "A"
  assert item_loaded.brand_preferences[0].brand == "Brand B"
  assert item_loaded.brand_preferences[0].tier == "B"
  assert item_loaded.product_preferences[0].product == "Leche"


def test_basket_item_description_rendering():
  """
  Verify description template rendering with variant, pack_size, unit, and
  casing.
  """
  sched = SchedulePolicy(mode="count", count=1)
  item = BasketItem(
      item="milk 1 l",
      product="Leche Entera",
      category="Food and beverages",
      unit="L",
      scheduling=sched,
      quantity=1,
      pack_size=1,
      variant="Pasteurizada",
      description_template="{product} {brand} {variant} {pack_size}{unit}",
      description_casing="natural",
  )

  desc = item.render_description("Lala")
  assert desc == "Leche Entera Lala Pasteurizada 1L"

  # With upper casing
  item.description_casing = "upper"
  assert item.render_description("Lala") == "LECHE ENTERA LALA PASTEURIZADA 1L"

  # Empty variant should not produce double spaces
  item.variant = ""
  item.description_casing = "natural"
  assert item.render_description("Alpura") == "Leche Entera Alpura 1L"


def test_store_and_brand_weighted_selection():
  """Verify weighted selection behavior with random.choices."""
  sp1 = StorePreference(merchant="Super Central", weight=0.9)
  sp2 = StorePreference(merchant="Tienda Express", weight=0.1)

  merchants = [sp1.merchant, sp2.merchant]
  weights = [sp1.weight, sp2.weight]

  rng = random.Random(42)
  selections = rng.choices(merchants, weights=weights, k=1000)
  central_count = selections.count("Super Central")

  # With 0.9 weight out of 1000, should be close to 900 (e.g. > 850)
  assert central_count > 850


def test_basket_item_and_income_source_tier_and_rating_validation():
  """Verify tier and rating validation on BasketItem and IncomeSource."""
  sched = SchedulePolicy(mode="count", count=1)

  # Valid defaults
  item = BasketItem("milk", "Milk", "Food", "L", sched)
  assert item.tier == "A"
  assert item.rating == 5.0

  # Valid custom tier and rating
  item_custom = BasketItem(
      "milk", "Milk", "Food", "L", sched, tier="C", rating=3.5
  )
  assert item_custom.tier == "C"
  assert item_custom.rating == 3.5

  # Invalid tier on BasketItem
  with pytest.raises(ValueError, match="Invalid tier"):
    BasketItem("milk", "Milk", "Food", "L", sched, tier="Z")

  # Invalid rating on BasketItem (< 1.0 or > 5.0)
  with pytest.raises(ValueError, match="Invalid rating"):
    BasketItem("milk", "Milk", "Food", "L", sched, rating=0.5)

  with pytest.raises(ValueError, match="Invalid rating"):
    BasketItem("milk", "Milk", "Food", "L", sched, rating=5.5)

  # IncomeSource valid defaults
  inc = IncomeSource("sal", "Corp", "Pay", "Income", 1000.0, "monthly", [1])
  assert inc.tier == "A"
  assert inc.rating == 5.0

  # IncomeSource valid custom
  inc_custom = IncomeSource(
      "sal", "Corp", "Pay", "Income", 1000.0, "monthly", [1], tier="B",
      rating=4.0
  )
  assert inc_custom.tier == "B"
  assert inc_custom.rating == 4.0

  # Invalid tier on IncomeSource
  with pytest.raises(ValueError, match="Invalid tier"):
    IncomeSource(
        "sal", "Corp", "Pay", "Income", 1000.0, "monthly", [1], tier="F"
    )

  # Invalid rating on IncomeSource
  with pytest.raises(ValueError, match="Invalid rating"):
    IncomeSource(
        "sal", "Corp", "Pay", "Income", 1000.0, "monthly", [1], rating=0.9
    )

  with pytest.raises(ValueError, match="Invalid rating"):
    IncomeSource(
        "sal", "Corp", "Pay", "Income", 1000.0, "monthly", [1], rating=5.1
    )


# ---------------------------------------------------------------------------
# 3. Profile Dataclass and JSON Round-trip
# ---------------------------------------------------------------------------


def test_profile_creation_and_dict_roundtrip():
  """Test manual creation of Profile and round-trip to/from dict."""
  sched = SchedulePolicy(mode="count", count=4)
  basket_item = BasketItem(
      item="milk 1 l",
      product="Leche",
      category="Food",
      unit="L",
      scheduling=sched,
      quantity=1,
      pack_size=1,
      store_preferences=[StorePreference("Store A", 1.0)],
      brand_preferences=[BrandPreference("Brand B", 1.0)],
      variant="Fresca",
  )
  income = IncomeSource(
      item="salary payroll biweekly",
      merchant="Corp",
      description="Nómina",
      category="Income",
      amount=20000.0,
      frequency="biweekly",
      schedule=[15, 30],
      volatility=0.005,
  )
  fb = FinancialBehavior(
      savings_rate=0.20,
      discount_seeking_probability=0.25,
      refund_probability=0.01,
      savings_merchant="Bank",
      savings_description="Ahorro",
  )
  scenario = Scenario(
      month_offset=11,
      row={"item": "bonus", "amount": 10000.0, "event_type": "income"},
  )

  profile = Profile(
      name="test_profile",
      currency="MXN",
      start_year=2024,
      months_count=12,
      basket=[basket_item],
      income=[income],
      financial_behavior=fb,
      scenarios=[scenario],
  )

  data = profile.to_dict()
  assert data["name"] == "test_profile"
  assert len(data["basket"]) == 1
  assert data["basket"][0]["scheduling"]["mode"] == "count"
  assert len(data["scenarios"]) == 1

  # Deserialization
  reconstructed = Profile.from_dict(data)
  assert reconstructed.name == profile.name
  assert reconstructed.currency == profile.currency
  assert reconstructed.start_year == profile.start_year
  assert reconstructed.months_count == profile.months_count
  assert reconstructed.financial_behavior.savings_rate == 0.20
  assert len(reconstructed.basket) == 1
  assert reconstructed.basket[0].item == "milk 1 l"
  assert reconstructed.basket[0].scheduling.count == 4
  assert reconstructed.basket[0].tier == "A"
  assert reconstructed.basket[0].rating == 5.0
  assert len(reconstructed.income) == 1
  assert reconstructed.income[0].amount == 20000.0
  assert reconstructed.income[0].tier == "A"
  assert reconstructed.income[0].rating == 5.0
  assert reconstructed.scenarios is not None
  assert reconstructed.scenarios[0].month_offset == 11
  assert reconstructed.scenarios[0].row["amount"] == 10000.0


def test_profile_json_file_roundtrip(tmp_path: Path):
  """Test Profile saving to JSON and loading from JSON file."""
  sched = SchedulePolicy(
      mode="deterministic", interval_months=2, offset_months=1
  )
  basket_item = BasketItem(
      item="cfe electricity",
      product="CFE",
      category="Utilities",
      unit="service",
      scheduling=sched,
      store_preferences=[StorePreference("CFE Direct", 1.0)],
      brand_preferences=[BrandPreference("CFE", 1.0)],
  )
  fb = FinancialBehavior(
      savings_rate=0.10,
      discount_seeking_probability=0.10,
      refund_probability=0.00,
      savings_merchant="Treasury",
      savings_description="CETES",
  )
  profile = Profile(
      name="json_test",
      currency="MXN",
      start_year=2024,
      months_count=24,
      basket=[basket_item],
      income=[],
      financial_behavior=fb,
  )

  json_path = tmp_path / "subdir" / "test_profile.json"
  profile.to_json(json_path)

  assert json_path.exists()
  loaded = Profile.from_json(json_path)
  assert loaded.name == "json_test"
  assert loaded.basket[0].item == "cfe electricity"
  assert loaded.basket[0].scheduling.interval_months == 2
  assert loaded.scenarios is None


# ---------------------------------------------------------------------------
# 4. Market Dataclass and JSON Round-trip
# ---------------------------------------------------------------------------


def test_market_creation_and_json_roundtrip(tmp_path: Path):
  """Test Market creation, dict serialization, and JSON file roundtrip."""
  charm = CharmPricing(grid_step=0.50, psychological_endings=[99, 49])
  tiers = [
      PackTierPriceCurve(pack_size=6, unit_price_multiplier=0.90),
      PackTierPriceCurve(pack_size=12, unit_price_multiplier=0.85),
  ]
  catalog_item = CatalogItem(
      item="milk 1 l",
      base_price=25.0,
      volatility=0.02,
      inflation_rate=0.05,
      menu_cost_band=0.05,
      calvo_jump_prob=0.20,
      charm=charm,
      pack_tiers=tiers,
      seasonal_modifiers={12: 1.10, 1: 1.05},
  )
  market = Market(
      name="test_market",
      currency="MXN",
      catalog=[catalog_item],
      global_inflation_rate=0.04,
  )

  json_path = tmp_path / "test_market.json"
  market.to_json(json_path)
  assert json_path.exists()

  loaded = Market.from_json(json_path)
  assert loaded.name == "test_market"
  assert loaded.currency == "MXN"
  assert loaded.global_inflation_rate == 0.04
  assert len(loaded.catalog) == 1

  item = loaded.get_item("milk 1 l")
  assert item.base_price == 25.0
  assert item.volatility == 0.02
  assert item.charm is not None
  assert item.charm.grid_step == 0.50
  assert item.charm.psychological_endings == [99, 49]
  assert item.pack_tiers is not None
  assert len(item.pack_tiers) == 2
  assert item.pack_tiers[0].pack_size == 6
  assert item.pack_tiers[0].unit_price_multiplier == 0.90
  assert item.seasonal_modifiers == {12: 1.10, 1: 1.05}


def test_catalog_item_validation():
  """Verify validation on CatalogItem parameters."""
  with pytest.raises(ValueError, match="base_price must be non-negative"):
    CatalogItem(
        item="item", base_price=-5.0, volatility=0.01, inflation_rate=0.05
    )

  with pytest.raises(ValueError, match="volatility must be non-negative"):
    CatalogItem(
        item="item", base_price=10.0, volatility=-0.01, inflation_rate=0.05
    )

  with pytest.raises(ValueError, match="menu_cost_band must be non-negative"):
    CatalogItem(
        item="item",
        base_price=10.0,
        volatility=0.01,
        inflation_rate=0.05,
        menu_cost_band=-0.05,
    )

  with pytest.raises(
      ValueError, match="calvo_jump_prob must be between 0.0 and 1.0"
  ):
    CatalogItem(
        item="item",
        base_price=10.0,
        volatility=0.01,
        inflation_rate=0.05,
        calvo_jump_prob=1.5,
    )


# ---------------------------------------------------------------------------
# 5. Dual-Mode Charm Pricing Tests
# ---------------------------------------------------------------------------


def test_charm_pricing_grid_quantization_only():
  """Verify quantization grid rounding when psychological endings are None."""
  charm = CharmPricing(grid_step=0.50, psychological_endings=None)
  assert charm.apply(25.12) == 25.00
  assert charm.apply(25.35) == 25.50
  assert charm.apply(25.80) == 26.00

  charm_10 = CharmPricing(grid_step=10.00, psychological_endings=None)
  assert charm_10.apply(54.00) == 50.00
  assert charm_10.apply(56.00) == 60.00


def test_charm_pricing_psychological_endings_only():
  """Verify snapping to psychological endings without grid step."""
  charm = CharmPricing(grid_step=0.0, psychological_endings=[99, 49])
  # 25.00: candidate 24.99 has diff 0.01; candidate 25.49 has diff 0.49
  assert charm.apply(25.00) == 24.99
  # 25.30: candidate 25.49 has diff 0.19; candidate 24.99 has diff 0.31
  assert charm.apply(25.30) == 25.49


def test_charm_pricing_dual_mode():
  """Verify combined quantization grid + psychological endings snapping."""
  charm = CharmPricing(grid_step=0.50, psychological_endings=[99, 49, 95])
  # 25.00 -> grid 25.00 -> nearest ending 24.99 (diff 0.01)
  assert charm.apply(25.00) == 24.99
  # 25.35 -> grid 25.50 -> nearest ending 25.49 (diff 0.01)
  assert charm.apply(25.35) == 25.49
  # 25.90 -> grid 26.00 -> nearest ending 25.99 (diff 0.01)
  assert charm.apply(25.90) == 25.99


# ---------------------------------------------------------------------------
# 6. Market.price_at sticky price, (s, S) band locking, and Calvo jumps
# ---------------------------------------------------------------------------


def test_market_price_at_deterministic_drift():
  """Verify latent price calculation with zero noise and no charm."""
  cat_item = CatalogItem(
      item="item_a",
      base_price=100.0,
      volatility=0.0,
      inflation_rate=0.12,  # 12% per year
      menu_cost_band=0.05,
      calvo_jump_prob=0.0,
      charm=None,
  )
  market = Market(
      name="test",
      currency="MXN",
      catalog=[cat_item],
      global_inflation_rate=0.0,
  )
  rng = random.Random(0)

  # month 0 -> 100.00
  p0 = market.price_at("item_a", "Store", month_offset=0, pack_size=1, rng=rng)
  assert p0 == 100.00

  # month 12 -> 100 * (1.12)^1 = 112.00
  p12 = market.price_at(
      "item_a", "Store", month_offset=12, pack_size=1, rng=rng
  )
  assert p12 == 112.00


def test_market_price_at_seasonal_modifiers():
  """
  Verify seasonal modifiers affect latent price for target calendar months.
  """
  cat_item = CatalogItem(
      item="fruit",
      base_price=50.0,
      volatility=0.0,
      inflation_rate=0.0,
      seasonal_modifiers={12: 1.20, 6: 0.80},
  )
  market = Market(
      name="test",
      currency="MXN",
      catalog=[cat_item],
      global_inflation_rate=0.0,
  )
  rng = random.Random(0)

  # month_offset 11 -> calendar month 12 (December) -> 50 * 1.20 = 60.00
  p_dec = market.price_at(
      "fruit", "Store", month_offset=11, pack_size=1, rng=rng
  )
  assert p_dec == 60.00

  # month_offset 5 -> calendar month 6 (June) -> 50 * 0.80 = 40.00
  p_jun = market.price_at(
      "fruit", "Store", month_offset=5, pack_size=1, rng=rng
  )
  assert p_jun == 40.00

  # month_offset 0 -> calendar month 1 (January) -> unaffected = 50.00
  p_jan = market.price_at(
      "fruit", "Store", month_offset=0, pack_size=1, rng=rng
  )
  assert p_jan == 50.00


def test_market_price_at_pack_tier_discount():
  """Verify discrete pack tiers apply unit price discount."""
  cat_item = CatalogItem(
      item="soda",
      base_price=20.00,
      volatility=0.0,
      inflation_rate=0.0,
      pack_tiers=[
          PackTierPriceCurve(pack_size=6, unit_price_multiplier=0.90),
          PackTierPriceCurve(pack_size=12, unit_price_multiplier=0.80),
      ],
  )
  market = Market(
      name="test",
      currency="MXN",
      catalog=[cat_item],
      global_inflation_rate=0.0,
  )
  rng = random.Random(0)

  # pack_size 1 -> multiplier 1.0 -> 20.00
  assert market.price_at("soda", "Store", 0, pack_size=1, rng=rng) == 20.00

  # pack_size 6 -> multiplier 0.90 -> 18.00 unit price
  assert market.price_at("soda", "Store", 0, pack_size=6, rng=rng) == 18.00

  # pack_size 12 -> multiplier 0.80 -> 16.00 unit price
  assert market.price_at("soda", "Store", 0, pack_size=12, rng=rng) == 16.00

  # unmatched pack_size (e.g. 3) -> default 1.0 -> 20.00
  assert market.price_at("soda", "Store", 0, pack_size=3, rng=rng) == 20.00


def test_market_price_at_sticky_menu_cost_locking():
  """Verify (s, S) menu cost band locks price when deviation is within band."""
  cat_item = CatalogItem(
      item="coffee",
      base_price=100.0,
      volatility=0.0,
      inflation_rate=0.12,  # 1% per month roughly
      menu_cost_band=0.05,  # 5% threshold
      calvo_jump_prob=0.0,  # disable Calvo jump to test pure (s, S)
  )
  market = Market(
      name="test",
      currency="MXN",
      catalog=[cat_item],
      global_inflation_rate=0.0,
  )
  rng = random.Random(0)

  # Initial shelf price
  shelf_price = 100.00

  # Month 1:
  # P* = 100 * (1.12)^(1/12) ≈ 100.95 -> rel diff ≈ 0.95% < 5% -> stays locked!
  p_m1 = market.price_at(
      "coffee",
      "Store",
      month_offset=1,
      pack_size=1,
      rng=rng,
      current_shelf_price=shelf_price,
  )
  assert p_m1 == 100.00

  # Month 3:
  # P* = 100 * (1.12)^(3/12) ≈ 102.87 -> rel diff ≈ 2.87% < 5% -> stays locked!
  p_m3 = market.price_at(
      "coffee",
      "Store",
      month_offset=3,
      pack_size=1,
      rng=rng,
      current_shelf_price=shelf_price,
  )
  assert p_m3 == 100.00

  # Month 6:
  # P* = 100 * (1.12)^(6/12) ≈ 105.83
  # -> rel diff ≈ 5.83% >= 5% -> breaches band and updates!
  p_m6 = market.price_at(
      "coffee",
      "Store",
      month_offset=6,
      pack_size=1,
      rng=rng,
      current_shelf_price=shelf_price,
  )
  assert p_m6 == 105.83


def test_market_price_at_calvo_jump():
  """
  Verify Calvo jump forces price update even when deviation is within menu cost
  band.
  """
  cat_item = CatalogItem(
      item="milk",
      base_price=25.0,
      volatility=0.0,
      inflation_rate=0.05,
      menu_cost_band=0.20,  # Very wide band (20%)
      calvo_jump_prob=1.0,  # 100% Calvo jump probability
  )
  market = Market(
      name="test",
      currency="MXN",
      catalog=[cat_item],
      global_inflation_rate=0.0,
  )
  rng = random.Random(0)

  # Drift is small (month 1 ≈ 25.10, diff ≈ 0.4% << 20%),
  # but calvo_jump_prob=1.0 forces update
  p_m1 = market.price_at(
      "milk",
      "Store",
      month_offset=1,
      pack_size=1,
      rng=rng,
      current_shelf_price=25.00,
  )
  assert p_m1 != 25.00
  assert p_m1 > 25.00


def test_market_unknown_item_raises():
  """Verify KeyError when querying item not in market catalog."""
  market = Market(
      name="test", currency="MXN", catalog=[], global_inflation_rate=0.0
  )
  with pytest.raises(KeyError, match="not found in market catalog"):
    market.price_at("nonexistent", "Store", 0, 1, random.Random(0))


# ---------------------------------------------------------------------------
# 7. Verification of Project JSON Configuration Files
# ---------------------------------------------------------------------------


def test_default_profile_configuration_validity():
  """Verify config/profiles/default.json exists, parses, and matches schema."""
  path = Path("config/profiles/default.json")
  assert path.exists(), f"Missing {path}"

  profile = Profile.from_json(path)
  assert profile.name == "default"
  assert profile.currency == "MXN"
  assert profile.start_year == 2021
  assert profile.months_count == 60
  assert len(profile.basket) >= 15
  assert len(profile.income) >= 1
  assert profile.financial_behavior.savings_rate > 0.0

  # Ensure all basket items have store and brand preferences with positive
  # weights
  for bi in profile.basket:
    assert len(bi.store_preferences) > 0
    assert sum(sp.weight for sp in bi.store_preferences) > 0
    assert len(bi.brand_preferences) > 0
    assert sum(bp.weight for bp in bi.brand_preferences) > 0
    # Check description rendering
    rendered = bi.render_description(bi.brand_preferences[0].brand)
    assert len(rendered) > 0


def test_alice_profile_configuration_validity():
  """
  Verify config/profiles/alice.json exists, parses, and includes scenarios.
  """
  path = Path("config/profiles/alice.json")
  assert path.exists(), f"Missing {path}"

  profile = Profile.from_json(path)
  assert profile.name == "alice"
  assert profile.currency == "MXN"
  assert profile.start_year == 2024
  assert profile.months_count == 24
  assert len(profile.basket) >= 15
  assert profile.scenarios is not None
  assert len(profile.scenarios) >= 1
  assert profile.scenarios[0].month_offset == 11
  assert profile.scenarios[0].row["item"] == "annual bonus"


def test_mexico_2024_market_configuration_validity():
  """Verify config/markets/mexico_2024.json exists and has catalog items."""
  path = Path("config/markets/mexico_2024.json")
  assert path.exists(), f"Missing {path}"

  market = Market.from_json(path)
  assert market.name == "mexico_2024"
  assert market.currency == "MXN"
  assert market.global_inflation_rate == 0.045
  assert len(market.catalog) >= 20


def test_catalog_covers_all_profile_basket_items():
  """
  Verify every item in default and alice baskets exists in mexico_2024 market
  catalog.
  """
  market = Market.from_json("config/markets/mexico_2024.json")
  market_items = {ci.item for ci in market.catalog}

  default_prof = Profile.from_json("config/profiles/default.json")
  alice_prof = Profile.from_json("config/profiles/alice.json")

  for bi in default_prof.basket:
    assert (
        bi.item in market_items
    ), f"Item '{bi.item}' from default profile missing in mexico_2024 catalog"

  for bi in alice_prof.basket:
    assert (
        bi.item in market_items
    ), f"Item '{bi.item}' from alice profile missing in mexico_2024 catalog"


def test_schema_headers_definition():
  """
  Verify HEADERS list matches 25-column Schema with store/brand/product tiers
  and ratings.
  """
  expected = [
      "receipt_id",
      "receipt_date",
      "merchant",
      "description",
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
      "notes",
  ]
  assert HEADERS == expected
  assert len(HEADERS) == 25


# ---------------------------------------------------------------------------
# 8. Generator Engine Tests (Schema, Determinism, Dynamics & Manifest)
# ---------------------------------------------------------------------------


def test_generator_schema_compliance():
  """
  Verify generated rows strictly match 25-column Schema headers and order.
  """
  from peit.profiler.generator import HEADERS as GEN_HEADERS, generate

  profile = Profile.from_json("config/profiles/alice.json")
  market = Market.from_json("config/markets/mexico_2024.json")

  rows, manifest = generate(profile, market, seed=42)
  assert len(rows) > 0

  for row in rows:
    assert list(row.keys()) == GEN_HEADERS
    assert len(row) == 25
    # Check required fields are populated
    assert (
        row["receipt_id"].startswith("REC-") or
        row["receipt_id"].startswith("SCEN-")
    )
    assert len(row["receipt_date"]) == 10  # YYYY-MM-DD
    assert row["currency"] == "MXN"
    assert (row["event_type"] in (
        "recurring", "income", "transfer", "refund", "one_off"
    ))
    assert row["store_tier"] in {"A", "B", "C", "D", "E"}
    assert 1.0 <= float(row["store_rating"]) <= 5.0
    assert row["brand_tier"] in {"A", "B", "C", "D", "E"}
    assert 1.0 <= float(row["brand_rating"]) <= 5.0
    assert row["product_tier"] in {"A", "B", "C", "D", "E"}
    assert 1.0 <= float(row["product_rating"]) <= 5.0
    # Check numeric conversions
    float(row["unit_price"])
    float(row["discount"])
    float(row["paid_total"])


def test_generator_determinism_with_seed():
  """Verify exact bitwise reproducibility when identical seed is provided."""
  from peit.profiler.generator import generate

  profile = Profile.from_json("config/profiles/alice.json")
  market = Market.from_json("config/markets/mexico_2024.json")

  rows1, m1 = generate(profile, market, seed=999)
  rows2, m2 = generate(profile, market, seed=999)

  assert len(rows1) == len(rows2)
  assert rows1 == rows2
  assert m1 == m2


def test_generator_stochasticity_without_seed():
  """
  Verify different receipt streams are drawn across runs when seed is None.
  """
  from peit.profiler.generator import generate

  profile = Profile.from_json("config/profiles/alice.json")
  market = Market.from_json("config/markets/mexico_2024.json")

  rows1, _ = generate(profile, market, seed=None)
  rows2, _ = generate(profile, market, seed=None)

  assert rows1 != rows2


def test_generator_discount_seeking_behavior():
  """
  Verify discount seeking probability generates expected discounts and signs.
  """
  from peit.profiler.generator import generate

  sched = SchedulePolicy(mode="count", count=5)
  item = BasketItem(
      item="milk 1 l",
      product="Leche",
      category="Food and beverages",
      unit="L",
      scheduling=sched,
      quantity=1,
      pack_size=1,
      store_preferences=[StorePreference("Store A", 1.0)],
      brand_preferences=[BrandPreference("Brand B", 1.0)],
  )
  market = Market.from_json("config/markets/mexico_2024.json")

  # Profile with 0% discount seeking
  fb_no_disc = FinancialBehavior(
      savings_rate=0.0,
      discount_seeking_probability=0.0,
      refund_probability=0.0,
      savings_merchant="Bank",
      savings_description="Savings",
  )
  prof_no_disc = Profile("no_disc", "MXN", 2024, 1, [item], [], fb_no_disc)
  rows_no_disc, _ = generate(prof_no_disc, market, seed=42)
  assert len(rows_no_disc) == 5
  for r in rows_no_disc:
    assert float(r["discount"]) == 0.0
    assert float(r["paid_total"]) == -float(r["unit_price"])

  # Profile with 100% discount seeking
  fb_full_disc = FinancialBehavior(
      savings_rate=0.0,
      discount_seeking_probability=1.0,
      refund_probability=0.0,
      savings_merchant="Bank",
      savings_description="Savings",
  )
  prof_full_disc = Profile(
      "full_disc", "MXN", 2024, 1, [item], [], fb_full_disc
  )
  rows_full_disc, _ = generate(prof_full_disc, market, seed=42)
  assert len(rows_full_disc) == 5
  for r in rows_full_disc:
    disc = float(r["discount"])
    gross = float(r["unit_price"])
    assert disc > 0.0
    assert float(r["paid_total"]) == -round(gross - disc, 2)


def test_generator_income_and_volatility():
  """
  Verify income source generation, volatility noise, and positive paid_total.
  """
  from peit.profiler.generator import generate

  inc_fixed = IncomeSource(
      item="salary",
      merchant="Corp",
      description="Salary",
      category="Income",
      amount=15000.0,
      frequency="monthly",
      schedule=[15, 30],
      volatility=0.0,
  )
  inc_noisy = IncomeSource(
      item="tips",
      merchant="Client",
      description="Tips",
      category="Income",
      amount=2000.0,
      frequency="monthly",
      schedule=[20],
      volatility=0.10,
  )
  fb = FinancialBehavior(0.0, 0.0, 0.0, "Bank", "Ahorro")
  prof = Profile(
      "income_test", "MXN", 2024, 2, [], [inc_fixed, inc_noisy], fb
  )
  market = Market.from_json("config/markets/mexico_2024.json")

  rows, _ = generate(prof, market, seed=42)
  # Each month has 2 fixed + 1 noisy = 3 rows; 2 months = 6 rows
  assert len(rows) == 6

  fixed_rows = [r for r in rows if r["item"] == "salary"]
  assert len(fixed_rows) == 4
  for r in fixed_rows:
    assert r["event_type"] == "income"
    assert float(r["paid_total"]) == 15000.00
    assert r["paid_total"] == r["unit_price"]
    assert r["store_tier"] == "A"
    assert r["store_rating"] == "5.0"
    assert r["brand_tier"] == "A"
    assert r["brand_rating"] == "5.0"
    assert r["product_tier"] == "A"
    assert r["product_rating"] == "5.0"

  noisy_rows = [r for r in rows if r["item"] == "tips"]
  assert len(noisy_rows) == 2
  # Noisy amounts should vary but remain around 2000
  for r in noisy_rows:
    assert r["event_type"] == "income"
    assert float(r["paid_total"]) > 0.0
    assert 1500.0 <= float(r["paid_total"]) <= 2500.0
    assert r["store_tier"] == "A"
    assert r["store_rating"] == "5.0"
    assert r["brand_tier"] == "A"
    assert r["brand_rating"] == "5.0"
    assert r["product_tier"] == "A"
    assert r["product_rating"] == "5.0"


def test_generator_savings_and_refund_behaviors():
  """Verify savings transfer out of checking and refund event generation."""
  from peit.profiler.generator import generate

  inc = IncomeSource(
      "sal", "Corp", "Nómina", "Income", 20000.0, "monthly", [15], "income"
  )
  item = BasketItem(
      item="milk 1 l",
      product="Leche",
      category="Food",
      unit="L",
      scheduling=SchedulePolicy(mode="count", count=2),
      store_preferences=[StorePreference("Store", 1.0)],
      brand_preferences=[BrandPreference("Brand", 1.0)],
  )
  fb = FinancialBehavior(
      savings_rate=0.25,  # 25% of 20000 = 5000
      discount_seeking_probability=0.0,
      refund_probability=1.0,  # 100% refund guarantee
      savings_merchant="Banco CETES",
      savings_description="Ahorro Automático CETES",
  )
  prof = Profile("fin_test", "MXN", 2024, 1, [item], [inc], fb)
  market = Market.from_json("config/markets/mexico_2024.json")

  rows, _ = generate(prof, market, seed=42)
  # 1 income + 2 recurring purchases + 1 savings transfer + 1 refund = 5 rows
  assert len(rows) == 5

  transfer_rows = [r for r in rows if r["event_type"] == "transfer"]
  assert len(transfer_rows) == 1
  assert float(transfer_rows[0]["paid_total"]) == -5000.00
  assert transfer_rows[0]["merchant"] == "Banco CETES"
  assert transfer_rows[0]["store_tier"] == "A"
  assert transfer_rows[0]["store_rating"] == "5.0"
  assert transfer_rows[0]["brand_tier"] == "A"
  assert transfer_rows[0]["brand_rating"] == "5.0"
  assert transfer_rows[0]["product_tier"] == "A"
  assert transfer_rows[0]["product_rating"] == "5.0"

  refund_rows = [r for r in rows if r["event_type"] == "refund"]
  assert len(refund_rows) == 1
  assert float(refund_rows[0]["paid_total"]) > 0.0
  assert "Reembolso:" in refund_rows[0]["description"]
  assert refund_rows[0]["store_tier"] == "A"
  assert refund_rows[0]["store_rating"] == "5.0"
  assert refund_rows[0]["brand_tier"] == "A"
  assert refund_rows[0]["brand_rating"] == "5.0"
  assert refund_rows[0]["product_tier"] == "A"
  assert refund_rows[0]["product_rating"] == "5.0"


def test_generator_distinct_store_brand_product_tiers_and_ratings():
  """
  Verify purchase rows emit distinct store, brand, and product tiers and
  ratings.
  """
  from peit.profiler.generator import generate

  sp = StorePreference("Boutique Gourmet", 1.0, tier="B", rating=4.2)
  bp = BrandPreference("Artisanal Brand", 1.0, tier="D", rating=2.5)
  pp = ProductPreference("Specialty Item", 1.0, tier="C", rating=3.8)

  item = BasketItem(
      item="specialty coffee flat white",
      product="Flat White",
      category="Dining",
      unit="cup",
      scheduling=SchedulePolicy(mode="count", count=3),
      store_preferences=[sp],
      brand_preferences=[bp],
      product_preferences=[pp],
  )
  fb = FinancialBehavior(0.0, 0.0, 0.0, "Bank", "Ahorro")
  prof = Profile("distinct_tiers", "MXN", 2024, 1, [item], [], fb)
  market = Market.from_json("config/markets/mexico_2024.json")

  rows, _ = generate(prof, market, seed=42)
  assert len(rows) == 3
  for r in rows:
    assert r["merchant"] == "Boutique Gourmet"
    assert r["store_tier"] == "B"
    assert r["store_rating"] == "4.2"
    assert r["brand"] == "Artisanal Brand"
    assert r["brand_tier"] == "D"
    assert r["brand_rating"] == "2.5"
    assert r["product_tier"] == "C"
    assert r["product_rating"] == "3.8"


def test_generator_hazard_scheduling_dynamics():
  """
  Verify renewal hazard model respects refractory min gap and forced max gap.
  """
  from peit.profiler.generator import generate

  item = BasketItem(
      item="dental checkup cleaning",
      product="Limpieza",
      category="Health",
      unit="visit",
      scheduling=SchedulePolicy(
          mode="hazard",
          expected_interval_months=6.0,
          hazard_shape=3.0,
          min_gap_months=3,  # Cannot purchase until at least 3 months have passed
          max_gap_months=8,  # Guaranteed purchase at 8 months
      ),
      store_preferences=[StorePreference("Clinic", 1.0)],
      brand_preferences=[BrandPreference("Dental", 1.0)],
  )
  fb = FinancialBehavior(0.0, 0.0, 0.0, "Bank", "Ahorro")
  # Run over 24 months
  prof = Profile("hazard_test", "MXN", 2024, 24, [item], [], fb)
  market = Market.from_json("config/markets/mexico_2024.json")

  rows, manifest = generate(prof, market, seed=42)
  assert len(rows) > 0

  # Check intervals between purchases
  purchase_months = [
      int(r["receipt_date"].split("-")[0]) * 12 +
      int(r["receipt_date"].split("-")[1]) for r in rows
  ]
  intervals = [
      purchase_months[i + 1] - purchase_months[i]
      for i in range(len(purchase_months) - 1)
  ]

  for interval in intervals:
    # Every interval must respect min_gap_months
    assert interval >= item.scheduling.min_gap_months
    # Every interval must not exceed max_gap_months
    assert interval <= item.scheduling.max_gap_months


def test_generator_persistent_shelf_prices_per_store():
  """
  Verify shelf prices are tracked per (item, merchant) pair across months.
  """
  from peit.profiler.generator import generate

  item = BasketItem(
      item="milk 1 l",
      product="Leche",
      category="Food and beverages",
      unit="L",
      scheduling=SchedulePolicy(mode="count", count=4),
      store_preferences=[
          StorePreference("Supermercado Central", 0.5),
          StorePreference("Tienda Express", 0.5),
      ],
      brand_preferences=[BrandPreference("Lala", 1.0)],
  )
  fb = FinancialBehavior(0.0, 0.0, 0.0, "Bank", "Ahorro")
  prof = Profile("shelf_test", "MXN", 2024, 6, [item], [], fb)
  market = Market.from_json("config/markets/mexico_2024.json")

  rows, manifest = generate(prof, market, seed=42)
  assert len(manifest["final_shelf_prices"]) >= 1
  # Both stores should appear if both were drawn
  stores_used = {r["merchant"] for r in rows}
  for store in stores_used:
    assert f"milk 1 l@{store}" in manifest["final_shelf_prices"]


def test_generator_ground_truth_manifest_completeness():
  """
  Verify ground truth manifest contains full configuration snapshot and
  metrics.
  """
  from peit.profiler.generator import generate

  profile = Profile.from_json("config/profiles/alice.json")
  market = Market.from_json("config/markets/mexico_2024.json")

  rows, manifest = generate(profile, market, seed=42)

  assert manifest["seed"] == 42
  assert manifest["total_rows"] == len(rows)
  assert manifest["profile"]["name"] == "alice"
  assert manifest["market"]["name"] == "mexico_2024"
  assert isinstance(manifest["item_counts"], dict)
  assert isinstance(manifest["store_counts"], dict)
  assert isinstance(manifest["brand_counts"], dict)
  assert isinstance(manifest["price_trajectories"], dict)
  assert isinstance(manifest["final_shelf_prices"], dict)
  assert len(manifest["item_counts"]) > 0


# ---------------------------------------------------------------------------
# 9. CLI Interface and System Integration Tests
# ---------------------------------------------------------------------------


def test_cli_generate_command_success(tmp_path):
  """
  Verify 'generate' sub-command generates Schema CSV and JSON manifest.
  """
  from peit.profiler import cli

  out_csv = tmp_path / "receipts.csv"
  out_manifest = tmp_path / "ground_truth.json"

  argv = [
      "generate",
      "--profile",
      "config/profiles/alice.json",
      "--market",
      "config/markets/mexico_2024.json",
      "--seed",
      "42",
      "-o",
      str(out_csv),
      "--manifest",
      str(out_manifest),
  ]

  ret = cli.main(argv)
  assert ret == 0
  assert out_csv.exists()
  assert out_manifest.exists()

  # Verify CSV structure matches 19 Schema columns
  with out_csv.open("r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    assert header == cli.HEADERS
    rows = list(reader)
    assert len(rows) > 0

  # Verify manifest structure
  with out_manifest.open("r", encoding="utf-8") as f:
    data = json.load(f)
    assert data["seed"] == 42
    assert data["total_rows"] == len(rows)
    assert data["profile"]["name"] == "alice"


def test_cli_direct_flags_invocation(tmp_path):
  """
  Verify running profiler CLI directly with flags
  (without 'generate' sub-command).
  """
  from peit.profiler import cli

  out_csv = tmp_path / "receipts_direct.csv"

  argv = [
      "--profile",
      "config/profiles/default.json",
      "--market",
      "config/markets/mexico_2024.json",
      "--seed",
      "100",
      "-o",
      str(out_csv),
  ]

  ret = cli.main(argv)
  assert ret == 0
  assert out_csv.exists()

  with out_csv.open("r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    assert header == cli.HEADERS
    rows = list(reader)
    assert len(rows) > 0


def test_cli_subprocess_module_execution(tmp_path):
  """
  Verify python -m peit.profiler generate executes as a module via subprocess.
  """
  out_csv = tmp_path / "subp_receipts.csv"
  out_manifest = tmp_path / "subp_manifest.json"

  cmd = [
      sys.executable,
      "-m",
      "peit.profiler",
      "generate",
      "--profile",
      "config/profiles/alice.json",
      "--market",
      "config/markets/mexico_2024.json",
      "--seed",
      "42",
      "-o",
      str(out_csv),
      "--manifest",
      str(out_manifest),
  ]

  env = dict(os.environ)
  env["PYTHONPATH"] = "src"

  result = subprocess.run(cmd, capture_output=True, text=True, env=env)
  assert result.returncode == 0
  assert out_csv.exists()
  assert out_manifest.exists()
  assert out_csv.stat().st_size > 0
  assert out_manifest.stat().st_size > 0


def test_cli_import_ledger_integration(tmp_path):
  """
  Verify --import-ledger adapter maps Schema rows into SQLite/JSONL ledger.
  """
  from peit.ledger import LedgerDatabase
  from peit.profiler import cli

  out_csv = tmp_path / "alice_receipts.csv"
  ledger_db = tmp_path / "alice_ledger.db"

  argv = [
      "generate",
      "--profile",
      "config/profiles/alice.json",
      "--market",
      "config/markets/mexico_2024.json",
      "--seed",
      "42",
      "-o",
      str(out_csv),
      "--import-ledger",
      str(ledger_db),
  ]

  ret = cli.main(argv)
  assert ret == 0
  assert out_csv.exists()
  assert ledger_db.exists()

  # The companion jsonl must also exist
  ledger_jsonl = tmp_path / "alice_ledger.jsonl"
  assert ledger_jsonl.exists()

  # Verify ledger entries match generated receipts
  db = LedgerDatabase(ledger_jsonl)
  entries = db.list_entries()
  assert len(entries) > 0

  with out_csv.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)

  assert len(entries) == len(csv_rows)

  # Verify adapter field conversions
  entry_by_id = {e.receipt_id: e for e in entries}
  for csv_row in csv_rows:
    entry = entry_by_id[csv_row["receipt_id"]]
    assert entry.month == csv_row["receipt_date"][:7]
    assert entry.description == csv_row["description"]
    assert entry.item == csv_row["item"]
    assert entry.unit_price == float(csv_row["unit_price"])
    assert entry.paid_total == float(csv_row["paid_total"])

  # Test idempotency: importing again skips duplicates
  ret2 = cli.main(argv)
  assert ret2 == 0
  entries2 = db.list_entries()
  assert len(entries2) == len(entries)


def test_cli_error_handling_and_exit_codes():
  """Verify CLI error reporting and exit codes for invalid inputs."""
  from peit.profiler import cli

  # Missing profile
  assert (
      cli.main([
          "generate",
          "--profile",
          "nonexistent_profile.json",
          "--market",
          "config/markets/mexico_2024.json",
      ])
      == 2
  )

  # Missing market
  assert (cli.main([
      "generate",
      "--profile",
      "config/profiles/alice.json",
      "--market",
      "nonexistent_market.json",
  ]) == 2)

  # Missing required flags
  assert cli.main(["generate"]) == 2

  # No arguments
  assert cli.main([]) == 2
