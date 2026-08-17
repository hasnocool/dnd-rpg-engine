# src/dnd_rpg_engine/adventure/npcs.py
from __future__ import annotations

from pydantic import BaseModel, Field


class NPCProfile(BaseModel):
    entity_id: str
    role: str = "resident"
    dialogue_id: str | None = None
    shop_id: str | None = None
    faction_id: str | None = None
    personality_id: str | None = None
    schedule_id: str | None = None
    knowledge_tags: set[str] = Field(default_factory=set)


class NPCRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, NPCProfile] = {}

    def register(self, profile: NPCProfile) -> None:
        self._profiles[profile.entity_id] = profile

    def get(self, entity_id: str) -> NPCProfile | None:
        return self._profiles.get(entity_id)
