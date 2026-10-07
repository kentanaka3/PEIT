"""Consumer Profile dataclass layer for PEIT receipt generation.

Separates consumer identity (signal) from market price dynamics (noise).
Provides serialization, deserialization, and schedule policy validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import random
from typing import Any, Literal


@dataclass
class TieredPreference:
  """Base class for tiered preferences with weight, quality tier, and rating."""

  name: str
  weight: float
  tier: str = "A"
  rating: float = 5.0

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError(f"StorePreference weight must be non-negative, got {self.weight}")


@dataclass
class BrandPreference:
    """Brand preference with selection weight."""

    brand: str
    weight: float

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError(f"BrandPreference weight must be non-negative, got {self.weight}")


@dataclass
class SchedulePolicy:
  """Co-living Deterministic Interval and Renewal / Hazard scheduling."""

  mode: Literal["count", "deterministic", "hazard"]
  # For count mode: fixed purchase count per month (e.g., weekly=4, biweekly=2, daily=30)
  count: int = 1
  # For deterministic mode: periodic cycle (e.g. interval_months=2 for bimonthly)
  interval_months: int = 1
  offset_months: int = 0
  # Specific calendar months (e.g. [12] for annual)
  target_months: list[int] | None = None
  # For hazard/renewal mode: depletion / wear-and-tear renewal process
  expected_interval_months: float = 3.0
  # Weibull shape (k > 1 increases hazard as gap grows)
  hazard_shape: float = 2.5
  min_gap_months: int = 1  # Refractory period
  max_gap_months: int = 6  # Forced renewal ceiling

  def __post_init__(self) -> None:
    if self.mode not in ("count", "deterministic", "hazard"):
      raise ValueError(
          f"Invalid SchedulePolicy mode: '{self.mode}'. "
          "Must be one of 'count', 'deterministic', 'hazard'."
      )
    if self.mode == "count":
      if self.count < 1:
        raise ValueError(f"count mode requires count >= 1, got {self.count}")
    elif self.mode == "deterministic":
      if self.interval_months < 1:
        raise ValueError(
            f"deterministic mode requires interval_months >= 1, got {self.interval_months}")
      if self.target_months is not None:
        for m in self.target_months:
          if not (1 <= m <= 12):
            raise ValueError(
                f"target_months must contain valid calendar months (1-12), got {m}")
    elif self.mode == "hazard":
      if self.expected_interval_months <= 0:
        raise ValueError(
            f"hazard mode requires expected_interval_months > 0, got {self.expected_interval_months}"
        )
      if self.hazard_shape <= 0:
        raise ValueError(
            f"hazard mode requires hazard_shape > 0, got {self.hazard_shape}")
      if self.min_gap_months < 0:
        raise ValueError(
            f"hazard mode requires min_gap_months >= 0, got {self.min_gap_months}")
      if self.max_gap_months < self.min_gap_months:
        raise ValueError(
            f"max_gap_months ({self.max_gap_months}) cannot be less than "
            f"min_gap_months ({self.min_gap_months})"
        )


@dataclass(init=False)
class BasketItem:
  """Consumer basket item with purchase cadence and preferences."""

  item: str  # normalized key ("milk 1 l")
  product: str  # human-readable product name ("Leche Entera")
  category: str
  unit: str
  scheduling: SchedulePolicy
  quantity: int = 1  # packs per purchase occasion
  pack_size: int = 1  # units per pack (default 1)
  preferences: ItemPreferences = field(
      default_factory=lambda: ItemPreferences())
  variant: str = ""  # product variant ("Pasteurizada", "Deslactosada", "")
  description_template: str = "{product} {brand} {variant} {pack_size}{unit}"
  description_casing: Literal["natural", "upper", "abbr"] = "natural"

  def __init__(
      self,
      item: str,
      product: str,
      category: str,
      unit: str,
      scheduling: SchedulePolicy,
      quantity: int = 1,
      pack_size: int = 1,
      store_preferences: list[StorePreference] | None = None,
      brand_preferences: list[BrandPreference] | None = None,
      variant: str = "",
      description_template: str = "{product} {brand} {variant} {pack_size}{unit}",
      description_casing: Literal["natural", "upper", "abbr"] = "natural",
      preferences: ItemPreferences | None = None,
      product_preferences: list[ProductPreference] | None = None,
  ) -> None:
    self.item = item
    self.product = product
    self.category = category
    self.unit = unit
    self.scheduling = scheduling
    self.quantity = quantity
    self.pack_size = pack_size
    self.variant = variant
    self.description_template = description_template
    self.description_casing = description_casing

    if preferences is not None:
      self.preferences = preferences
      if product_preferences and not self.preferences.products:
        self.preferences.products = product_preferences
      if store_preferences and not self.preferences.stores:
        self.preferences.stores = store_preferences
      if brand_preferences and not self.preferences.brands:
        self.preferences.brands = brand_preferences
    else:
      stores = store_preferences if store_preferences is not None else []
      brands = brand_preferences if brand_preferences is not None else []
      products = product_preferences if product_preferences is not None else []
      self.preferences = ItemPreferences(
          stores=stores, brands=brands, products=products)

  @property
  def store_preferences(self) -> list[StorePreference]:
    return self.preferences.stores

  @store_preferences.setter
  def store_preferences(self, val: list[StorePreference]) -> None:
    self.preferences.stores = val

  @property
  def brand_preferences(self) -> list[BrandPreference]:
    return self.preferences.brands

  @brand_preferences.setter
  def brand_preferences(self, val: list[BrandPreference]) -> None:
    self.preferences.brands = val

  @property
  def product_preferences(self) -> list[ProductPreference]:
    return self.preferences.products

  @product_preferences.setter
  def product_preferences(self, val: list[ProductPreference]) -> None:
    self.preferences.products = val

  def render_description(self, brand: str, product: str | None = None) -> str:
    """Render raw item description string using template and casing."""
    rendered = self.description_template.format(
        product=product if product is not None else self.product,
        brand=brand,
        variant=self.variant,
        pack_size=self.pack_size,
        unit=self.unit,
    )
    # Collapse multi-spaces when optional elements like variant are empty
    cleaned = " ".join(rendered.split())
    if self.description_casing == "upper":
      return cleaned.upper()
    return cleaned


@dataclass
class IncomeSource:
  """Periodic income source definition."""

  item: str  # normalized key ("salary payroll biweekly")
  merchant: str
  description: str
  category: str
  amount: float
  frequency: str  # "biweekly", "monthly", "annual"
  schedule: list[int]  # day-of-month list (e.g., [15, 28])
  event_type: str = "income"
  # low σ for Gaussian noise (0.005 for salary, 0.10 for tips)
  volatility: float = 0.0

  def __post_init__(self) -> None:
    if self.volatility < 0:
      raise ValueError(
          f"Income volatility must be non-negative, got {self.volatility}")

  def to_dict(self) -> dict[str, Any]:
    """Convert IncomeSource to dictionary."""
    return {
        "item": self.item,
        "merchant": self.merchant,
        "description": self.description,
        "category": self.category,
        "amount": self.amount,
        "frequency": self.frequency,
        "schedule": list(self.schedule),
        "event_type": self.event_type,
        "volatility": self.volatility,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> IncomeSource:
    """Instantiate IncomeSource from dictionary."""
    return cls(
        item=data["item"],
        merchant=data["merchant"],
        description=data["description"],
        category=data["category"],
        amount=float(data["amount"]),
        frequency=data["frequency"],
        schedule=list(data["schedule"]),
        event_type=data.get("event_type", "income"),
        volatility=float(data.get("volatility", 0.0)),
    )


@dataclass
class FinancialBehavior:
  """Financial parameters governing savings, discounts, and returns."""

  savings_rate: float  # fraction of income saved per month
  # probability of seeking/accepting promotions
  discount_seeking_probability: float
  refund_probability: float  # probability of returning an item per month
  savings_merchant: str  # e.g., "Banco Ahorro Inversión"
  savings_description: str


@dataclass
class Scenario:
  """Deterministic pedagogical row injected at a specific month offset."""

  month_offset: int  # 0-indexed month from start
  row: dict[str, Any]  # exact CSV row dict


@dataclass
class Profile:
  """Top-level consumer profile identity and parameters."""

  name: str
  currency: str
  start_year: int
  months_count: int
  basket: list[BasketItem]
  income: list[IncomeSource]
  financial_behavior: FinancialBehavior
  scenarios: list[Scenario] | None = None

  def to_dict(self) -> dict[str, Any]:
    """Convert Profile dataclass tree to a standard JSON-compatible dict."""
    res: dict[str, Any] = {
        "name": self.name,
        "currency": self.currency,
        "start_year": self.start_year,
        "months_count": self.months_count,
        "financial_behavior": self.financial_behavior.to_dict(),
        "income": [inc.to_dict() for inc in self.income],
        "basket": [bi.to_dict() for bi in self.basket],
    }
    if self.scenarios is not None:
      res["scenarios"] = [sc.to_dict() for sc in self.scenarios]
    return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Instantiate Profile dataclass tree from dictionary with nested deserialization."""
        basket: list[BasketItem] = []
        for bi in data.get("basket", []):
            sched_data = bi["scheduling"]
            if isinstance(sched_data, dict):
                scheduling = SchedulePolicy(
                    mode=sched_data["mode"],
                    count=sched_data.get("count", 1),
                    interval_months=sched_data.get("interval_months", 1),
                    offset_months=sched_data.get("offset_months", 0),
                    target_months=sched_data.get("target_months"),
                    expected_interval_months=float(sched_data.get("expected_interval_months", 3.0)),
                    hazard_shape=float(sched_data.get("hazard_shape", 2.5)),
                    min_gap_months=int(sched_data.get("min_gap_months", 1)),
                    max_gap_months=int(sched_data.get("max_gap_months", 6)),
                )
            else:
                scheduling = sched_data

            store_prefs = [
                StorePreference(merchant=sp["merchant"], weight=float(sp["weight"]))
                if isinstance(sp, dict)
                else sp
                for sp in bi.get("store_preferences", [])
            ]
            brand_prefs = [
                BrandPreference(brand=bp["brand"], weight=float(bp["weight"]))
                if isinstance(bp, dict)
                else bp
                for bp in bi.get("brand_preferences", [])
            ]

            basket.append(
                BasketItem(
                    item=bi["item"],
                    product=bi["product"],
                    category=bi["category"],
                    unit=bi["unit"],
                    scheduling=scheduling,
                    quantity=int(bi.get("quantity", 1)),
                    pack_size=int(bi.get("pack_size", 1)),
                    store_preferences=store_prefs,
                    brand_preferences=brand_prefs,
                    variant=bi.get("variant", ""),
                    description_template=bi.get(
                        "description_template",
                        "{product} {brand} {variant} {pack_size}{unit}",
                    ),
                    description_casing=bi.get("description_casing", "natural"),
                )
            )

        income: list[IncomeSource] = []
        for inc in data.get("income", []):
            if isinstance(inc, dict):
                income.append(
                    IncomeSource(
                        item=inc["item"],
                        merchant=inc["merchant"],
                        description=inc["description"],
                        category=inc["category"],
                        amount=float(inc["amount"]),
                        frequency=inc["frequency"],
                        schedule=list(inc["schedule"]),
                        event_type=inc.get("event_type", "income"),
                        volatility=float(inc.get("volatility", 0.0)),
                    )
                )
            else:
                income.append(inc)

    fb_data = data["financial_behavior"]
    if isinstance(fb_data, dict):
      financial_behavior = FinancialBehavior.from_dict(fb_data)
    else:
      financial_behavior = fb_data

    scenarios: list[Scenario] | None = None
    if data.get("scenarios") is not None:
      scenarios = [
          Scenario.from_dict(sc) if isinstance(sc, dict) else sc
          for sc in data["scenarios"]
      ]

    return cls(
        name=data["name"],
        currency=data["currency"],
        start_year=int(data["start_year"]),
        months_count=int(data["months_count"]),
        basket=basket,
        income=income,
        financial_behavior=financial_behavior,
        scenarios=scenarios,
    )

  def to_json(self, path: Path | str, indent: int = 2) -> None:
    """Serialize Profile to JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
      json.dump(self.to_dict(), f, indent=indent, ensure_ascii=False)

  @classmethod
  def from_json(cls, path: Path | str) -> Profile:
    """Load Profile from JSON file."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
      data = json.load(f)
    return cls.from_dict(data)
