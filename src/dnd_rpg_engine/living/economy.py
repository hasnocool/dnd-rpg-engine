# src/dnd_rpg_engine/living/economy.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MarketState:
    base_value: int
    supply: float = 1.0
    demand: float = 1.0

    @property
    def price(self) -> int:
        supply = max(0.1, self.supply)
        demand = max(0.1, self.demand)
        return max(1, round(self.base_value * demand / supply))


class EconomySystem:
    def __init__(self) -> None:
        self.markets: dict[str, MarketState] = {}

    def register_item(self, item_id: str, base_value: int) -> None:
        self.markets[item_id] = MarketState(base_value=base_value)

    def price(self, item_id: str, *, multiplier: float = 1.0) -> int:
        market = self.markets.get(item_id)
        if market is None:
            raise KeyError(f"unknown market item: {item_id}")
        return max(1, round(market.price * multiplier))

    def transact(self, item_id: str, quantity: int, *, buying_from_market: bool) -> None:
        market = self.markets[item_id]
        magnitude = min(0.25, quantity * 0.01)
        if buying_from_market:
            market.supply = max(0.1, market.supply - magnitude)
            market.demand = min(5.0, market.demand + magnitude / 2)
        else:
            market.supply = min(5.0, market.supply + magnitude)
            market.demand = max(0.1, market.demand - magnitude / 2)

    def decay(self, factor: float = 0.05) -> None:
        for market in self.markets.values():
            market.supply += (1.0 - market.supply) * factor
            market.demand += (1.0 - market.demand) * factor
