"""PEIT Profiler package.

Separates consumer behavior (signal) from market price dynamics (noise).
Provides dataclasses, JSON profiles, market models, and receipt simulation.
"""

from __future__ import annotations

from peit.profiler.generator import HEADERS, generate
from peit.profiler.market import (
    CatalogItem,
    CharmPricing,
    Market,
    PackTierPriceCurve,
)
from peit.profiler.profile import (
    BasketItem,
    BrandPreference,
    FinancialBehavior,
    IncomeSource,
    ItemPreferences,
    ProductPreference,
    Profile,
    Scenario,
    SchedulePolicy,
    StorePreference,
    TieredPreference,
)

__all__ = [
    "Profile",
    "Market",
    "generate",
    "HEADERS",
    "BasketItem",
    "BrandPreference",
    "CatalogItem",
    "CharmPricing",
    "FinancialBehavior",
    "IncomeSource",
    "ItemPreferences",
    "PackTierPriceCurve",
    "ProductPreference",
    "Scenario",
    "SchedulePolicy",
    "StorePreference",
    "TieredPreference",
]
