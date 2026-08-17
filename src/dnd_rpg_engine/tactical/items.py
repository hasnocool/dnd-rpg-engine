# src/dnd_rpg_engine/tactical/items.py
from __future__ import annotations

from pydantic import BaseModel, Field


class ItemDefinition(BaseModel):
    id: str
    name: str
    value: int = Field(default=0, ge=0)
    stackable: bool = True
    max_stack: int = Field(default=99, ge=1)
    use_time: float = Field(default=4.0, gt=0)
    heal: str | None = None
    energy_restore: int = Field(default=0, ge=0)
    applies_condition: str | None = None
    tags: set[str] = Field(default_factory=set)


class ItemStack(BaseModel):
    item_id: str
    quantity: int = Field(default=1, ge=1)


class Inventory(BaseModel):
    items: dict[str, int] = Field(default_factory=dict)
    currency: int = Field(default=0, ge=0)

    def add(self, item_id: str, quantity: int = 1) -> None:
        if quantity < 1:
            raise ValueError("quantity must be positive")
        self.items[item_id] = self.items.get(item_id, 0) + quantity

    def remove(self, item_id: str, quantity: int = 1) -> None:
        if self.items.get(item_id, 0) < quantity:
            raise ValueError("insufficient item quantity")
        remaining = self.items[item_id] - quantity
        if remaining:
            self.items[item_id] = remaining
        else:
            self.items.pop(item_id, None)


class ItemRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ItemDefinition] = {}

    def register(self, item: ItemDefinition) -> None:
        self._items[item.id] = item

    def require(self, item_id: str) -> ItemDefinition:
        try:
            return self._items[item_id]
        except KeyError as exc:
            raise KeyError(f"unknown item: {item_id}") from exc

    def all(self) -> tuple[ItemDefinition, ...]:
        return tuple(self._items.values())


def default_items() -> ItemRegistry:
    registry = ItemRegistry()
    registry.register(ItemDefinition(id="minor_restorative", name="Minor Restorative", value=25, heal="2d4+2"))
    registry.register(
        ItemDefinition(id="focus_tonic", name="Focus Tonic", value=20, energy_restore=3, tags={"consumable"})
    )
    return registry
