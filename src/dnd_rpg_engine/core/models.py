# src/dnd_rpg_engine/core/models.py
from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeMode(StrEnum):
    TURN_BASED = "turn_based"
    TIMED_TURN_BASED = "timed_turn_based"
    REAL_TIME = "real_time"
    REAL_TIME_WITH_PAUSE = "real_time_with_pause"
    HYBRID = "hybrid"


class EntityKind(StrEnum):
    PLAYER = "player"
    NPC = "npc"
    CREATURE = "creature"
    OBJECT = "object"
    LOCATION = "location"


class ControllerKind(StrEnum):
    HUMAN = "human"
    AI = "ai"
    SCRIPT = "script"
    NONE = "none"


class Stats(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    strength: int = Field(default=10, ge=1, le=40)
    dexterity: int = Field(default=10, ge=1, le=40)
    constitution: int = Field(default=10, ge=1, le=40)
    intelligence: int = Field(default=10, ge=1, le=40)
    wisdom: int = Field(default=10, ge=1, le=40)
    charisma: int = Field(default=10, ge=1, le=40)

    def modifier(self, ability: str) -> int:
        value = getattr(self, ability)
        return (value - 10) // 2


class Position(BaseModel):
    area_id: str = "start"
    node_id: str | None = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: Position) -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2) ** 0.5


class ResourcePool(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    hp: int = Field(default=10, ge=0)
    max_hp: int = Field(default=10, ge=1)
    energy: int = Field(default=0, ge=0)
    max_energy: int = Field(default=0, ge=0)

    @field_validator("hp")
    @classmethod
    def _hp_nonnegative(cls, value: int) -> int:
        return max(0, value)

    def apply_damage(self, amount: int) -> int:
        before = self.hp
        self.hp = max(0, self.hp - max(0, amount))
        return before - self.hp

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + max(0, amount))
        return self.hp - before


class Entity(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    kind: EntityKind = EntityKind.NPC
    controller: ControllerKind = ControllerKind.NONE
    owner_id: str | None = None
    stats: Stats = Field(default_factory=Stats)
    resources: ResourcePool = Field(default_factory=ResourcePool)
    position: Position = Field(default_factory=Position)
    tags: set[str] = Field(default_factory=set)
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)
    alive: bool = True

    def component(self, name: str) -> dict[str, Any]:
        return self.components.setdefault(name, {})


class GameConfig(BaseModel):
    """Runtime timing policy. The rules engine itself remains timeline-driven."""

    time_mode: TimeMode = TimeMode.HYBRID
    ticks_per_second: int = Field(default=20, ge=1, le=240)
    time_scale: float = Field(default=1.0, gt=0, le=100)
    world_minutes_per_sim_second: float = Field(default=1.0, ge=0, le=1440)
    default_action_time_seconds: float = Field(default=6.0, gt=0)
    player_decision_timeout_seconds: float | None = Field(default=10.0, gt=0)
    pause_when_player_ready: bool = True
    enemies_continue_while_player_idle: bool = True
    timeout_behavior: str = "continue_timeline"
    reaction_timeout_seconds: float = Field(default=3.0, ge=0)
    snapshot_every_events: int = Field(default=100, ge=1)
    seed: int = 1

    @property
    def realtime_enabled(self) -> bool:
        return self.time_mode in {
            TimeMode.REAL_TIME,
            TimeMode.REAL_TIME_WITH_PAUSE,
            TimeMode.HYBRID,
            TimeMode.TIMED_TURN_BASED,
        }


class CampaignState(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "New Campaign"
    seed: int = 1
    simulation_time: float = 0.0
    world_minutes: float = 0.0
    entities: dict[str, Entity] = Field(default_factory=dict)
    active_map_id: str | None = None
    flags: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_entity(self, entity: Entity) -> None:
        if entity.id in self.entities:
            raise ValueError(f"entity already exists: {entity.id}")
        self.entities[entity.id] = entity

    def require_entity(self, entity_id: str) -> Entity:
        try:
            return self.entities[entity_id]
        except KeyError as exc:
            raise KeyError(f"unknown entity: {entity_id}") from exc
