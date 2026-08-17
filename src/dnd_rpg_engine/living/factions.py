# src/dnd_rpg_engine/living/factions.py
from __future__ import annotations

from pydantic import BaseModel, Field


class Faction(BaseModel):
    id: str
    name: str
    tags: set[str] = Field(default_factory=set)
    resources: float = Field(default=100.0, ge=0)
    influence: float = Field(default=50.0, ge=0)


class FactionSystem:
    def __init__(self) -> None:
        self.factions: dict[str, Faction] = {}
        self.relations: dict[tuple[str, str], int] = {}
        self.reputation: dict[tuple[str, str], int] = {}

    def register(self, faction: Faction) -> None:
        self.factions[faction.id] = faction

    def set_relation(self, a: str, b: str, value: int) -> None:
        clamped = max(-100, min(100, value))
        self.relations[(a, b)] = clamped
        self.relations[(b, a)] = clamped

    def relation(self, a: str, b: str) -> int:
        return self.relations.get((a, b), 0)

    def change_reputation(self, actor_id: str, faction_id: str, delta: int) -> int:
        key = (actor_id, faction_id)
        self.reputation[key] = max(-100, min(100, self.reputation.get(key, 0) + delta))
        return self.reputation[key]
