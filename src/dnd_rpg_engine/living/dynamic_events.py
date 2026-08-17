# src/dnd_rpg_engine/living/dynamic_events.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.models import CampaignState


class EventPredicate(BaseModel):
    kind: str
    key: str | None = None
    operator: str = "eq"
    value: Any = True


class DynamicEventDefinition(BaseModel):
    id: str
    event_type: str
    predicates: list[EventPredicate] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    once: bool = True


class DynamicEventSystem:
    def __init__(self) -> None:
        self.rules: dict[str, DynamicEventDefinition] = {}
        self.fired: set[str] = set()

    def register(self, rule: DynamicEventDefinition) -> None:
        self.rules[rule.id] = rule

    def evaluate(self, state: CampaignState) -> list[DynamicEventDefinition]:
        matched: list[DynamicEventDefinition] = []
        for rule in self.rules.values():
            if rule.once and rule.id in self.fired:
                continue
            if all(self._matches(predicate, state) for predicate in rule.predicates):
                matched.append(rule)
                if rule.once:
                    self.fired.add(rule.id)
        return matched

    @staticmethod
    def _matches(predicate: EventPredicate, state: CampaignState) -> bool:
        if predicate.kind == "flag":
            actual = state.flags.get(predicate.key or "")
        elif predicate.kind == "world_minute":
            actual = state.world_minutes
        elif predicate.kind == "simulation_time":
            actual = state.simulation_time
        elif predicate.kind == "entity_alive":
            entity = state.entities.get(predicate.key or "")
            actual = bool(entity and entity.alive)
        else:
            return False
        if predicate.operator == "eq":
            return actual == predicate.value
        if predicate.operator == "ne":
            return actual != predicate.value
        if predicate.operator == "gte":
            return actual >= predicate.value
        if predicate.operator == "lte":
            return actual <= predicate.value
        if predicate.operator == "gt":
            return actual > predicate.value
        if predicate.operator == "lt":
            return actual < predicate.value
        return False
