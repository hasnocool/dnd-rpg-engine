# src/dnd_rpg_engine/tactical/conditions.py
from __future__ import annotations

from pydantic import BaseModel, Field


class ConditionDefinition(BaseModel):
    id: str
    name: str
    attack_modifier: int = 0
    armor_modifier: int = 0
    movement_multiplier: float = Field(default=1.0, ge=0)
    blocks_actions: bool = False
    periodic_damage: str | None = None
    periodic_interval: float | None = Field(default=None, gt=0)


class ActiveCondition(BaseModel):
    condition_id: str
    source_id: str | None = None
    expires_at: float | None = None
    stacks: int = Field(default=1, ge=1)


class ConditionRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ConditionDefinition] = {}

    def register(self, definition: ConditionDefinition) -> None:
        self._definitions[definition.id] = definition

    def require(self, condition_id: str) -> ConditionDefinition:
        try:
            return self._definitions[condition_id]
        except KeyError as exc:
            raise KeyError(f"unknown condition: {condition_id}") from exc


def default_conditions() -> ConditionRegistry:
    registry = ConditionRegistry()
    registry.register(ConditionDefinition(id="guarded", name="Guarded", armor_modifier=2))
    registry.register(ConditionDefinition(id="slowed", name="Slowed", movement_multiplier=0.5))
    registry.register(ConditionDefinition(id="stunned", name="Stunned", blocks_actions=True))
    registry.register(
        ConditionDefinition(
            id="burning_arcane",
            name="Arcane Burn",
            periodic_damage="1d4",
            periodic_interval=6.0,
        )
    )
    return registry
