from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from dnd_rpg_engine.core.models import Stats


class RecoveryPolicy(StrEnum):
    TURN = "turn"
    ROUND = "round"
    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"
    MANUAL = "manual"


class FeatureResource(BaseModel):
    id: str
    current: int = Field(ge=0)
    maximum: int = Field(ge=0)
    recovery: RecoveryPolicy = RecoveryPolicy.LONG_REST

    def spend(self, amount: int = 1) -> None:
        if amount < 0 or self.current < amount:
            raise ValueError(f"insufficient resource: {self.id}")
        self.current -= amount

    def restore(self) -> None:
        self.current = self.maximum


class HitDiceState(BaseModel):
    die_size: int = Field(ge=4, le=12)
    current: int = Field(ge=0)
    maximum: int = Field(ge=1, le=20)


class SpellcastingState(BaseModel):
    ability: str | None = None
    known_spells: set[str] = Field(default_factory=set)
    prepared_spells: set[str] = Field(default_factory=set)
    slots: dict[int, int] = Field(default_factory=dict)
    maximum_slots: dict[int, int] = Field(default_factory=dict)
    concentration_spell_id: str | None = None

    def can_cast(self, spell_id: str, level: int) -> bool:
        if self.ability is None:
            return False
        if spell_id not in self.known_spells and spell_id not in self.prepared_spells:
            return False
        return level == 0 or self.slots.get(level, 0) > 0

    def spend_slot(self, level: int) -> None:
        if level <= 0:
            return
        remaining = self.slots.get(level, 0)
        if remaining <= 0:
            raise ValueError(f"no level {level} spell slots remaining")
        self.slots[level] = remaining - 1

    def restore_slots(self) -> None:
        self.slots = dict(self.maximum_slots)


class TurnState(BaseModel):
    active: bool = False
    action_available: bool = True
    bonus_action_available: bool = True
    reaction_available: bool = True
    movement_max: float = Field(default=30.0, ge=0)
    movement_remaining: float = Field(default=30.0, ge=0)
    free_interactions: int = Field(default=1, ge=0)
    round_index: int = Field(default=0, ge=0)

    def reset(self, movement: float | None = None) -> None:
        self.active = True
        self.action_available = True
        self.bonus_action_available = True
        self.reaction_available = True
        if movement is not None:
            self.movement_max = max(0.0, movement)
        self.movement_remaining = self.movement_max
        self.free_interactions = 1
        self.round_index += 1


class CharacterState(BaseModel):
    class_id: str
    subclass_id: str | None = None
    species_id: str
    background_id: str
    level: int = Field(default=1, ge=1, le=20)
    xp: int = Field(default=0, ge=0)
    milestone_advances: int = Field(default=0, ge=0)
    feature_ids: set[str] = Field(default_factory=set)
    feat_ids: set[str] = Field(default_factory=set)
    skill_proficiencies: set[str] = Field(default_factory=set)
    expertise: set[str] = Field(default_factory=set)
    hit_dice: HitDiceState
    resources: dict[str, FeatureResource] = Field(default_factory=dict)
    spellcasting: SpellcastingState = Field(default_factory=SpellcastingState)
    turn: TurnState = Field(default_factory=TurnState)
    inventory_attunement_ids: set[str] = Field(default_factory=set)
    advancement_log: list[dict[str, Any]] = Field(default_factory=list)


class CharacterBuildRequest(BaseModel):
    name: str
    owner_id: str | None = None
    class_id: str
    subclass_id: str | None = None
    species_id: str
    background_id: str
    level: int = Field(default=1, ge=1, le=20)
    stats: Stats = Field(default_factory=Stats)
    skill_proficiencies: set[str] = Field(default_factory=set)
    expertise: set[str] = Field(default_factory=set)
    feat_ids: set[str] = Field(default_factory=set)
    known_spells: set[str] = Field(default_factory=set)
    prepared_spells: set[str] = Field(default_factory=set)

    @model_validator(mode="after")
    def _expertise_requires_proficiency(self) -> "CharacterBuildRequest":
        self.skill_proficiencies.update(self.expertise)
        return self
