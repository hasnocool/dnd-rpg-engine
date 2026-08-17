# src/dnd_rpg_engine/tactical/actions.py
from __future__ import annotations

from pydantic import BaseModel, Field


class ActionDefinition(BaseModel):
    id: str
    name: str
    time_cost: float = Field(default=6.0, gt=0)
    range: float = Field(default=1.5, ge=0)
    attack_ability: str = "strength"
    damage: str = "1d6"
    damage_type: str = "physical"
    proficiency_key: str | None = None
    tags: set[str] = Field(default_factory=set)


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, ActionDefinition] = {}

    def register(self, action: ActionDefinition) -> None:
        self._actions[action.id] = action

    def require(self, action_id: str) -> ActionDefinition:
        try:
            return self._actions[action_id]
        except KeyError as exc:
            raise KeyError(f"unknown action: {action_id}") from exc

    def all(self) -> tuple[ActionDefinition, ...]:
        return tuple(self._actions.values())


def default_actions() -> ActionRegistry:
    registry = ActionRegistry()
    registry.register(
        ActionDefinition(
            id="basic_attack",
            name="Basic Attack",
            time_cost=6.0,
            range=1.5,
            attack_ability="strength",
            damage="1d6",
            damage_type="physical",
        )
    )
    registry.register(
        ActionDefinition(
            id="quick_attack",
            name="Quick Attack",
            time_cost=4.0,
            range=1.5,
            attack_ability="dexterity",
            damage="1d4",
            damage_type="physical",
            tags={"quick"},
        )
    )
    return registry
