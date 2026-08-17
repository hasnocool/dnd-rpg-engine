# src/dnd_rpg_engine/adventure/npcs.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.models import (
    ControllerKind,
    Entity,
    EntityKind,
    Position,
    ResourcePool,
    Stats,
)


class NPCProfile(BaseModel):
    """Reusable NPC definition plus its adventure relationships.

    Earlier versions stored only relationship metadata here. The profile now
    also carries enough entity state to instantiate the NPC into a live world,
    while keeping all of the original dialogue/shop/faction/personality/schedule
    fields backward compatible.
    """

    entity_id: str
    name: str | None = None
    description: str = ""
    role: str = "resident"
    controller: ControllerKind = ControllerKind.AI
    stats: Stats = Field(default_factory=Stats)
    resources: ResourcePool = Field(default_factory=ResourcePool)
    position: Position = Field(default_factory=Position)
    tags: set[str] = Field(default_factory=set)
    appearance: dict[str, Any] = Field(default_factory=dict)
    ai_profile: str = "ambient_npc"
    dialogue_id: str | None = None
    shop_id: str | None = None
    faction_id: str | None = None
    personality_id: str | None = None
    schedule_id: str | None = None
    knowledge_tags: set[str] = Field(default_factory=set)

    def to_entity(self) -> Entity:
        components: dict[str, dict[str, Any]] = {
            "npc": {
                "role": self.role,
                "dialogue_id": self.dialogue_id,
                "shop_id": self.shop_id,
                "personality_id": self.personality_id,
                "schedule_id": self.schedule_id,
            },
            "ai": {"profile": self.ai_profile},
        }
        if self.appearance:
            components["appearance"] = dict(self.appearance)
        if self.faction_id:
            components["faction"] = {"id": self.faction_id}
        return Entity(
            id=self.entity_id,
            name=self.name or self.entity_id,
            kind=EntityKind.NPC,
            controller=self.controller,
            stats=self.stats.model_copy(deep=True),
            resources=self.resources.model_copy(deep=True),
            position=self.position.model_copy(deep=True),
            tags={"npc", *self.tags},
            components=components,
        )


class NPCRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, NPCProfile] = {}

    def register(self, profile: NPCProfile) -> None:
        self._profiles[profile.entity_id] = profile

    def get(self, entity_id: str) -> NPCProfile | None:
        return self._profiles.get(entity_id)

    def require(self, entity_id: str) -> NPCProfile:
        try:
            return self._profiles[entity_id]
        except KeyError as exc:
            raise KeyError(f"unknown NPC profile: {entity_id}") from exc

    def remove(self, entity_id: str) -> NPCProfile | None:
        return self._profiles.pop(entity_id, None)

    def all(self) -> tuple[NPCProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))
