# src/dnd_rpg_engine/ai/personalities.py
from __future__ import annotations

from pydantic import BaseModel, Field


class Personality(BaseModel):
    id: str
    traits: dict[str, float] = Field(default_factory=dict)
    goals: list[str] = Field(default_factory=list)
    fears: list[str] = Field(default_factory=list)
    speech_style: str = "plain"

    def utility_bias(self, action_tag: str) -> float:
        return self.traits.get(action_tag, 0.0)


class PersonalityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Personality] = {}

    def register(self, personality: Personality) -> None:
        self._items[personality.id] = personality

    def get(self, personality_id: str | None) -> Personality | None:
        return None if personality_id is None else self._items.get(personality_id)
