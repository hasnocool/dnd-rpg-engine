# src/dnd_rpg_engine/adventure/shops.py
from __future__ import annotations

from pydantic import BaseModel, Field


class Shop(BaseModel):
    id: str
    name: str
    keeper_id: str | None = None
    stock: dict[str, int] = Field(default_factory=dict)
    buy_multiplier: float = Field(default=1.0, gt=0)
    sell_multiplier: float = Field(default=0.5, gt=0)
    restock_world_minutes: float = Field(default=1440.0, gt=0)
    last_restock_at: float = 0.0

    def take(self, item_id: str, quantity: int) -> None:
        available = self.stock.get(item_id, 0)
        if available < quantity:
            raise ValueError("shop does not have enough stock")
        left = available - quantity
        if left:
            self.stock[item_id] = left
        else:
            self.stock.pop(item_id, None)

    def add(self, item_id: str, quantity: int) -> None:
        self.stock[item_id] = self.stock.get(item_id, 0) + quantity


class ShopRegistry:
    def __init__(self) -> None:
        self._shops: dict[str, Shop] = {}

    def register(self, shop: Shop) -> None:
        self._shops[shop.id] = shop

    def all(self) -> tuple[Shop, ...]:
        return tuple(self._shops.values())

    def require(self, shop_id: str) -> Shop:
        try:
            return self._shops[shop_id]
        except KeyError as exc:
            raise KeyError(f"unknown shop: {shop_id}") from exc
