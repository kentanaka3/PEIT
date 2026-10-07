"""Market price dynamics dataclass layer for PEIT receipt generation.

Models latent inflation drift, Gaussian volatility noise, discrete pack tiers,
sticky regime jumps with (s, S) menu cost thresholds and Calvo jump hazards,
and dual-mode charm pricing (grid quantization + psychological endings).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import random
from typing import Any


@dataclass
class PackTierPriceCurve:
    """Discrete pack tier: pack_size -> unit_price multiplier."""

    pack_size: int
    unit_price_multiplier: float  # e.g., 0.92 for 8% volume discount

    def __post_init__(self) -> None:
        if self.pack_size < 1:
            raise ValueError(f"pack_size must be >= 1, got {self.pack_size}")
        if self.unit_price_multiplier <= 0:
            raise ValueError(
                f"unit_price_multiplier must be positive, got {self.unit_price_multiplier}"
            )


@dataclass
class CharmPricing:
    """Dual-mode charm pricing: quantization grid AND psychological endings.

    Quantization mode: round to nearest `grid_step` (e.g., 0.50 -> prices land on $X.00 or $X.50).
    Psychological mode: snap to charm endings (e.g., [99, 49, 95]) after quantization.
    Both modes can be active simultaneously.
    """

    grid_step: float = 0.50  # Quantize to this increment (e.g., 0.50)
    psychological_endings: list[int] | None = None  # Charm cent endings (e.g., [99, 49, 95])

    def apply(self, price: float) -> float:
        """Apply quantization grid and psychological charm ending snapping."""
        p = price
        if self.grid_step is not None and self.grid_step > 0:
            p = round(p / self.grid_step) * self.grid_step

        if self.psychological_endings:
            candidates = [
                d + (ending / 100.0)
                for d in (math.floor(p) - 1, math.floor(p), math.floor(p) + 1)
                for ending in self.psychological_endings
                if d + (ending / 100.0) > 0
            ]
            if candidates:
                p = min(candidates, key=lambda c: (abs(c - p), c))

        return round(p, 2)


@dataclass
class CatalogItem:
    """Catalog item pricing dynamics and menu-cost parameters."""

    item: str  # must match BasketItem.item
    base_price: float  # base unit price at pack_size=1
    volatility: float  # σ for Gaussian price noise
    inflation_rate: float  # annual compound rate (e.g., 0.045 for 4.5%)
    # Sticky price & menu cost parameters
    menu_cost_band: float = 0.05  # (s, S) threshold: stay locked if deviation < 5%
    calvo_jump_prob: float = 0.20  # Hazard probability to force price review
    charm: CharmPricing | None = None  # Dual-mode charm pricing (quantization + psychological)
    pack_tiers: list[PackTierPriceCurve] | None = None
    seasonal_modifiers: dict[int, float] | None = None  # month -> multiplier

    def __post_init__(self) -> None:
        if self.base_price < 0:
            raise ValueError(f"base_price must be non-negative, got {self.base_price}")
        if self.volatility < 0:
            raise ValueError(f"volatility must be non-negative, got {self.volatility}")
        if self.menu_cost_band < 0:
            raise ValueError(f"menu_cost_band must be non-negative, got {self.menu_cost_band}")
        if not (0.0 <= self.calvo_jump_prob <= 1.0):
            raise ValueError(
                f"calvo_jump_prob must be between 0.0 and 1.0, got {self.calvo_jump_prob}"
            )
        if self.seasonal_modifiers:
            self.seasonal_modifiers = {
                int(k): float(v) for k, v in self.seasonal_modifiers.items()
            }


@dataclass
class Market:
    """Market price catalog and sticky price generation engine."""

    name: str
    currency: str
    catalog: list[CatalogItem]
    global_inflation_rate: float  # fallback if item doesn't specify

    def get_item(self, item: str) -> CatalogItem:
        """Find catalog item by normalized item key."""
        for ci in self.catalog:
            if ci.item == item:
                return ci
        raise KeyError(f"Item '{item}' not found in market catalog '{self.name}'")

    def price_at(
        self,
        item: str,
        merchant: str,
        month_offset: int,
        pack_size: int,
        rng: random.Random,
        current_shelf_price: float | None = None,
    ) -> float:
        """Compute sticky regime-jump price for an item at a specific merchant.

        Shelf prices are tracked per (item, merchant) — the same item can
        have different shelf prices at different stores.

        Algorithm:
          1. Compute latent drift P* = P0 * (1+inf)^(t/12) * exp(gauss(0, σ))
          2. Apply seasonal modifiers if month matches
          3. Apply pack tier unit price multiplier
          4. Apply (s, S) menu cost filter and Calvo jump against current_shelf_price
          5. Apply dual-mode charm pricing (grid quantization + psychological endings)
        """
        catalog_item = self.get_item(item)

        # 1. Latent price P*
        inf_rate = (
            catalog_item.inflation_rate
            if catalog_item.inflation_rate is not None
            else self.global_inflation_rate
        )
        drift = (1.0 + inf_rate) ** (month_offset / 12.0)
        noise = math.exp(rng.gauss(0.0, catalog_item.volatility))
        p_star = catalog_item.base_price * drift * noise

        # 2. Seasonal modifiers
        cal_month = (month_offset % 12) + 1
        if catalog_item.seasonal_modifiers:
            if cal_month in catalog_item.seasonal_modifiers:
                p_star *= catalog_item.seasonal_modifiers[cal_month]
            elif str(cal_month) in catalog_item.seasonal_modifiers:
                p_star *= catalog_item.seasonal_modifiers[str(cal_month)]

        # 3. Pack tiers (discrete volume discount curve)
        pack_multiplier = 1.0
        if catalog_item.pack_tiers:
            for tier in catalog_item.pack_tiers:
                if tier.pack_size == pack_size:
                    pack_multiplier = tier.unit_price_multiplier
                    break
        p_star *= pack_multiplier

        # 4. (s, S) menu cost band & Calvo jump hazard
        if current_shelf_price is not None:
            calvo_jump = rng.random() < catalog_item.calvo_jump_prob
            rel_diff = (
                abs(p_star - current_shelf_price) / current_shelf_price
                if current_shelf_price > 0
                else 1.0
            )
            menu_cost_breach = rel_diff >= catalog_item.menu_cost_band
            if calvo_jump or menu_cost_breach:
                target_p = p_star
            else:
                return round(current_shelf_price, 2)
        else:
            target_p = p_star

        # 5. Dual-mode charm pricing
        if catalog_item.charm is not None:
            target_p = catalog_item.charm.apply(target_p)

        return round(target_p, 2)

    def to_dict(self) -> dict[str, Any]:
        """Convert Market dataclass tree to a standard JSON-compatible dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Market:
        """Instantiate Market dataclass tree from dictionary with nested deserialization."""
        global_inf = float(data.get("global_inflation_rate", 0.0))
        catalog: list[CatalogItem] = []

        for ci in data.get("catalog", []):
            charm = None
            if ci.get("charm") is not None:
                charm_data = ci["charm"]
                charm = (
                    CharmPricing(
                        grid_step=float(charm_data.get("grid_step", 0.50)),
                        psychological_endings=charm_data.get("psychological_endings"),
                    )
                    if isinstance(charm_data, dict)
                    else charm_data
                )

            pack_tiers = None
            if ci.get("pack_tiers") is not None:
                pack_tiers = [
                    PackTierPriceCurve(
                        pack_size=int(pt["pack_size"]),
                        unit_price_multiplier=float(pt["unit_price_multiplier"]),
                    )
                    if isinstance(pt, dict)
                    else pt
                    for pt in ci["pack_tiers"]
                ]

            seasonal = None
            if ci.get("seasonal_modifiers") is not None:
                seasonal = {
                    int(k): float(v) for k, v in ci["seasonal_modifiers"].items()
                }

            inf_rate = ci.get("inflation_rate")
            if inf_rate is None:
                inf_rate = global_inf
            else:
                inf_rate = float(inf_rate)

            catalog.append(
                CatalogItem(
                    item=ci["item"],
                    base_price=float(ci["base_price"]),
                    volatility=float(ci.get("volatility", 0.0)),
                    inflation_rate=inf_rate,
                    menu_cost_band=float(ci.get("menu_cost_band", 0.05)),
                    calvo_jump_prob=float(ci.get("calvo_jump_prob", 0.20)),
                    charm=charm,
                    pack_tiers=pack_tiers,
                    seasonal_modifiers=seasonal,
                )
            )

        return cls(
            name=data["name"],
            currency=data["currency"],
            catalog=catalog,
            global_inflation_rate=global_inf,
        )

    def to_json(self, path: Path | str, indent: int = 2) -> None:
        """Serialize Market to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, path: Path | str) -> Market:
        """Load Market from JSON file."""
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
