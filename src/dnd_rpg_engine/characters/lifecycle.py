# src/dnd_rpg_engine/characters/lifecycle.py
from __future__ import annotations

import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, ResourcePool, Stats


class AdvancementMode(StrEnum):
    XP = "xp"
    MILESTONE = "milestone"


class RestKind(StrEnum):
    SHORT = "short"
    LONG = "long"


class AdvancementTrack(BaseModel):
    """Ruleset-owned advancement thresholds.

    ``thresholds[level - 1]`` is the minimum XP needed to reach ``level``.
    Milestone campaigns can use the same lifecycle service while ignoring XP.
    """

    id: str = "generic"
    mode: AdvancementMode = AdvancementMode.XP
    thresholds: tuple[int, ...] = tuple((level - 1) ** 2 * 1000 for level in range(1, 21))
    max_level: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def _validate_thresholds(self) -> "AdvancementTrack":
        if not self.thresholds:
            raise ValueError("advancement track requires at least one threshold")
        if self.thresholds[0] != 0:
            raise ValueError("level 1 threshold must be zero")
        if any(right < left for left, right in zip(self.thresholds, self.thresholds[1:])):
            raise ValueError("advancement thresholds must be non-decreasing")
        if self.max_level > len(self.thresholds):
            raise ValueError("max_level exceeds supplied advancement thresholds")
        return self

    def threshold_for_level(self, level: int) -> int:
        if level < 1 or level > self.max_level:
            raise ValueError("level is outside the advancement track")
        return self.thresholds[level - 1]


class ClassResourceDefinition(BaseModel):
    id: str
    name: str
    base_max: int = Field(default=0, ge=0)
    per_level: float = Field(default=0.0, ge=0)
    short_rest_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    long_rest_fraction: float = Field(default=1.0, ge=0.0, le=1.0)

    def maximum_for_level(self, level: int) -> int:
        return max(0, self.base_max + math.floor(self.per_level * max(0, level - 1)))


class LevelBenefit(BaseModel):
    level: int = Field(ge=1)
    feature_ids: tuple[str, ...] = ()
    hp_gain: int | None = Field(default=None, ge=1)
    ability_points: int = Field(default=0, ge=0)
    resource_max_bonus: dict[str, int] = Field(default_factory=dict)


class CharacterClassDefinition(BaseModel):
    id: str
    name: str
    hit_die: int = Field(default=8, ge=1, le=100)
    max_level: int = Field(default=20, ge=1, le=100)
    primary_abilities: tuple[str, ...] = ()
    saving_throw_proficiencies: tuple[str, ...] = ()
    spellcasting_ability: str | None = None
    resources: dict[str, ClassResourceDefinition] = Field(default_factory=dict)
    level_benefits: dict[int, LevelBenefit] = Field(default_factory=dict)
    tags: set[str] = Field(default_factory=set)


class CharacterProgress(BaseModel):
    species_id: str | None = None
    background_id: str | None = None
    classes: dict[str, int] = Field(default_factory=dict)
    xp: int = Field(default=0, ge=0)
    feature_ids: set[str] = Field(default_factory=set)
    unspent_ability_points: int = Field(default=0, ge=0)
    advancement_track_id: str = "generic"

    @property
    def total_level(self) -> int:
        return sum(self.classes.values())


class TrackedResource(BaseModel):
    id: str
    current: int = Field(default=0, ge=0)
    maximum: int = Field(default=0, ge=0)
    short_rest_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    long_rest_fraction: float = Field(default=1.0, ge=0.0, le=1.0)

    def restore_fraction(self, fraction: float) -> int:
        target = min(self.maximum, self.current + math.ceil(self.maximum * max(0.0, min(1.0, fraction))))
        restored = target - self.current
        self.current = target
        return restored

    def spend(self, amount: int) -> int:
        value = max(0, amount)
        if self.current < value:
            raise ValueError(f"insufficient {self.id}")
        self.current -= value
        return value


class EquipmentDefinition(BaseModel):
    item_id: str
    name: str
    slots: tuple[str, ...]
    modifiers: dict[str, float] = Field(default_factory=dict)
    tags: set[str] = Field(default_factory=set)
    requires_attunement: bool = False

    @model_validator(mode="after")
    def _require_slot(self) -> "EquipmentDefinition":
        if not self.slots:
            raise ValueError("equipment requires at least one slot")
        return self


class EquipmentState(BaseModel):
    slots: dict[str, str] = Field(default_factory=dict)
    attuned: set[str] = Field(default_factory=set)
    max_attuned: int = Field(default=3, ge=0, le=100)


class RestProfile(BaseModel):
    id: str
    kind: RestKind
    duration_seconds: float = Field(gt=0)
    hp_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    energy_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    temp_hp_cleared: bool = True
    resource_fraction_override: float | None = Field(default=None, ge=0.0, le=1.0)


class CharacterBuildRequest(BaseModel):
    name: str
    class_id: str
    owner_id: str | None = None
    controller: ControllerKind = ControllerKind.HUMAN
    species_id: str | None = None
    background_id: str | None = None
    stats: Stats = Field(default_factory=Stats)
    starting_level: int = Field(default=1, ge=1, le=100)
    starting_xp: int = Field(default=0, ge=0)
    starting_equipment: tuple[str, ...] = ()
    tags: set[str] = Field(default_factory=set)


class LevelUpOutcome(BaseModel):
    class_id: str
    previous_class_level: int
    class_level: int
    total_level: int
    hp_gain: int
    max_hp: int
    feature_ids_added: tuple[str, ...] = ()
    ability_points_added: int = 0
    resources: dict[str, TrackedResource] = Field(default_factory=dict)


class RestOutcome(BaseModel):
    profile_id: str
    hp_restored: int = 0
    energy_restored: int = 0
    resources_restored: dict[str, int] = Field(default_factory=dict)
    duration_seconds: float


class EquipmentOutcome(BaseModel):
    item_id: str
    equipped: bool
    slots: tuple[str, ...]
    displaced_item_ids: tuple[str, ...] = ()
    modifiers: dict[str, float] = Field(default_factory=dict)


class CharacterLifecycle:
    """Ruleset-neutral authoritative character lifecycle service.

    Rulesets provide class definitions, advancement tracks, rest profiles, and
    equipment metadata. Runtime state is stored in normal entity components so
    it automatically participates in snapshots, event sourcing, multiplayer,
    save games, and mod-pack round trips.
    """

    def __init__(
        self,
        *,
        advancement_track: AdvancementTrack | None = None,
        classes: dict[str, CharacterClassDefinition] | None = None,
        equipment: dict[str, EquipmentDefinition] | None = None,
        rest_profiles: dict[str, RestProfile] | None = None,
    ) -> None:
        self.advancement_track = advancement_track or AdvancementTrack()
        self.classes = dict(classes or {})
        self.equipment = dict(equipment or {})
        self.rest_profiles = dict(rest_profiles or default_rest_profiles())

    def register_class(self, definition: CharacterClassDefinition) -> None:
        self.classes[definition.id] = definition

    def register_equipment(self, definition: EquipmentDefinition) -> None:
        self.equipment[definition.item_id] = definition

    def register_rest_profile(self, profile: RestProfile) -> None:
        self.rest_profiles[profile.id] = profile

    def build_character(self, request: CharacterBuildRequest) -> Entity:
        definition = self.require_class(request.class_id)
        if request.starting_level > definition.max_level:
            raise ValueError("starting level exceeds class maximum")
        progress = CharacterProgress(
            species_id=request.species_id,
            background_id=request.background_id,
            classes={definition.id: 1},
            xp=request.starting_xp,
            advancement_track_id=self.advancement_track.id,
        )
        constitution_mod = request.stats.modifier("constitution")
        max_hp = max(1, definition.hit_die + constitution_mod)
        entity = Entity(
            name=request.name,
            kind=EntityKind.PLAYER,
            controller=request.controller,
            owner_id=request.owner_id,
            stats=request.stats.model_copy(deep=True),
            resources=ResourcePool(hp=max_hp, max_hp=max_hp, energy=0, max_energy=0),
            tags={"character", *request.tags},
            components={
                "character": progress.model_dump(mode="json"),
                "character_resources": {},
                "equipment": EquipmentState().model_dump(mode="json"),
                "inventory": {"items": {item_id: 1 for item_id in request.starting_equipment}, "currency": 0},
            },
        )
        self._synchronize_class_resources(entity)
        while self.progress(entity).total_level < request.starting_level:
            self.level_up(entity, definition.id, ignore_eligibility=True)
        for item_id in request.starting_equipment:
            if item_id in self.equipment:
                self.equip(entity, item_id)
        return entity

    def progress(self, entity: Entity) -> CharacterProgress:
        raw = entity.component("character")
        if not raw:
            raise ValueError("entity does not have character lifecycle state")
        return CharacterProgress.model_validate(raw)

    def set_progress(self, entity: Entity, progress: CharacterProgress) -> None:
        entity.components["character"] = progress.model_dump(mode="json")

    def resources(self, entity: Entity) -> dict[str, TrackedResource]:
        raw = entity.component("character_resources")
        return {key: TrackedResource.model_validate(value) for key, value in raw.items()}

    def set_resources(self, entity: Entity, resources: dict[str, TrackedResource]) -> None:
        entity.components["character_resources"] = {
            key: value.model_dump(mode="json") for key, value in sorted(resources.items())
        }

    def equipment_state(self, entity: Entity) -> EquipmentState:
        return EquipmentState.model_validate(entity.component("equipment"))

    def set_equipment_state(self, entity: Entity, state: EquipmentState) -> None:
        entity.components["equipment"] = state.model_dump(mode="json")

    def require_class(self, class_id: str) -> CharacterClassDefinition:
        try:
            return self.classes[class_id]
        except KeyError as exc:
            raise KeyError(f"unknown character class: {class_id}") from exc

    def award_xp(self, entity: Entity, amount: int) -> CharacterProgress:
        if amount < 0:
            raise ValueError("XP award cannot be negative")
        progress = self.progress(entity)
        progress.xp += amount
        self.set_progress(entity, progress)
        return progress

    def eligible_for_level(self, entity: Entity, target_total_level: int | None = None) -> bool:
        progress = self.progress(entity)
        next_level = target_total_level or progress.total_level + 1
        if next_level > self.advancement_track.max_level:
            return False
        if self.advancement_track.mode is AdvancementMode.MILESTONE:
            return bool(entity.component("advancement").get("milestone_ready", False))
        return progress.xp >= self.advancement_track.threshold_for_level(next_level)

    def level_up(self, entity: Entity, class_id: str, *, ignore_eligibility: bool = False) -> LevelUpOutcome:
        progress = self.progress(entity)
        definition = self.require_class(class_id)
        previous_class_level = progress.classes.get(class_id, 0)
        if previous_class_level >= definition.max_level:
            raise ValueError("class is already at maximum level")
        if progress.total_level >= self.advancement_track.max_level:
            raise ValueError("character is already at maximum total level")
        if not ignore_eligibility and not self.eligible_for_level(entity):
            raise ValueError("character is not eligible to gain a level")

        class_level = previous_class_level + 1
        benefit = definition.level_benefits.get(class_level)
        hp_gain = (
            benefit.hp_gain
            if benefit is not None and benefit.hp_gain is not None
            else max(1, (definition.hit_die // 2) + 1 + entity.stats.modifier("constitution"))
        )
        entity.resources.max_hp += hp_gain
        entity.resources.hp += hp_gain
        progress.classes[class_id] = class_level
        added_features: tuple[str, ...] = ()
        ability_points = 0
        if benefit is not None:
            added_features = tuple(feature for feature in benefit.feature_ids if feature not in progress.feature_ids)
            progress.feature_ids.update(added_features)
            ability_points = benefit.ability_points
            progress.unspent_ability_points += ability_points
        if self.advancement_track.mode is AdvancementMode.MILESTONE:
            entity.component("advancement")["milestone_ready"] = False
        self.set_progress(entity, progress)
        resources = self._synchronize_class_resources(entity)
        if benefit is not None:
            for resource_id, bonus in benefit.resource_max_bonus.items():
                resource = resources.get(resource_id)
                if resource is None:
                    continue
                resource.maximum += max(0, bonus)
                resource.current += max(0, bonus)
            self.set_resources(entity, resources)
        return LevelUpOutcome(
            class_id=class_id,
            previous_class_level=previous_class_level,
            class_level=class_level,
            total_level=progress.total_level,
            hp_gain=hp_gain,
            max_hp=entity.resources.max_hp,
            feature_ids_added=added_features,
            ability_points_added=ability_points,
            resources=resources,
        )

    def mark_milestone_ready(self, entity: Entity, ready: bool = True) -> None:
        entity.component("advancement")["milestone_ready"] = bool(ready)

    def rest(self, entity: Entity, profile_id: str) -> RestOutcome:
        try:
            profile = self.rest_profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"unknown rest profile: {profile_id}") from exc

        hp_target = min(entity.resources.max_hp, entity.resources.hp + math.ceil(entity.resources.max_hp * profile.hp_fraction))
        hp_restored = hp_target - entity.resources.hp
        entity.resources.hp = hp_target
        energy_target = min(
            entity.resources.max_energy,
            entity.resources.energy + math.ceil(entity.resources.max_energy * profile.energy_fraction),
        )
        energy_restored = energy_target - entity.resources.energy
        entity.resources.energy = energy_target
        if profile.temp_hp_cleared:
            entity.resources.temp_hp = 0

        resources = self.resources(entity)
        resource_restored: dict[str, int] = {}
        for resource_id, resource in resources.items():
            fraction = profile.resource_fraction_override
            if fraction is None:
                fraction = resource.short_rest_fraction if profile.kind is RestKind.SHORT else resource.long_rest_fraction
            restored = resource.restore_fraction(fraction)
            if restored:
                resource_restored[resource_id] = restored
        self.set_resources(entity, resources)
        return RestOutcome(
            profile_id=profile.id,
            hp_restored=hp_restored,
            energy_restored=energy_restored,
            resources_restored=resource_restored,
            duration_seconds=profile.duration_seconds,
        )

    def equip(self, entity: Entity, item_id: str) -> EquipmentOutcome:
        try:
            definition = self.equipment[item_id]
        except KeyError as exc:
            raise KeyError(f"unknown equipment definition: {item_id}") from exc
        inventory = entity.component("inventory").get("items", {})
        if int(inventory.get(item_id, 0)) < 1:
            raise ValueError("equipment item is not present in inventory")
        state = self.equipment_state(entity)
        displaced = sorted({state.slots[slot] for slot in definition.slots if slot in state.slots and state.slots[slot] != item_id})
        for displaced_id in displaced:
            self._remove_equipment_item(state, displaced_id)
        if definition.requires_attunement and item_id not in state.attuned:
            if len(state.attuned) >= state.max_attuned:
                raise ValueError("no attunement slot is available")
            state.attuned.add(item_id)
        for slot in definition.slots:
            state.slots[slot] = item_id
        self.set_equipment_state(entity, state)
        return EquipmentOutcome(
            item_id=item_id,
            equipped=True,
            slots=definition.slots,
            displaced_item_ids=tuple(displaced),
            modifiers=self.effective_equipment_modifiers(entity),
        )

    def unequip(self, entity: Entity, item_id: str) -> EquipmentOutcome:
        state = self.equipment_state(entity)
        slots = tuple(sorted(slot for slot, equipped_id in state.slots.items() if equipped_id == item_id))
        if not slots:
            raise ValueError("item is not equipped")
        self._remove_equipment_item(state, item_id)
        self.set_equipment_state(entity, state)
        return EquipmentOutcome(
            item_id=item_id,
            equipped=False,
            slots=slots,
            modifiers=self.effective_equipment_modifiers(entity),
        )

    def effective_equipment_modifiers(self, entity: Entity) -> dict[str, float]:
        state = self.equipment_state(entity)
        equipped_ids = sorted(set(state.slots.values()))
        totals: dict[str, float] = {}
        for item_id in equipped_ids:
            definition = self.equipment.get(item_id)
            if definition is None:
                continue
            for key, value in definition.modifiers.items():
                totals[key] = totals.get(key, 0.0) + float(value)
        return totals

    def spend_resource(self, entity: Entity, resource_id: str, amount: int = 1) -> TrackedResource:
        resources = self.resources(entity)
        try:
            resource = resources[resource_id]
        except KeyError as exc:
            raise KeyError(f"unknown character resource: {resource_id}") from exc
        resource.spend(amount)
        self.set_resources(entity, resources)
        return resource

    def restore_resource(self, entity: Entity, resource_id: str, amount: int) -> TrackedResource:
        if amount < 0:
            raise ValueError("resource restoration cannot be negative")
        resources = self.resources(entity)
        try:
            resource = resources[resource_id]
        except KeyError as exc:
            raise KeyError(f"unknown character resource: {resource_id}") from exc
        resource.current = min(resource.maximum, resource.current + amount)
        self.set_resources(entity, resources)
        return resource

    def _synchronize_class_resources(self, entity: Entity) -> dict[str, TrackedResource]:
        progress = self.progress(entity)
        resources = self.resources(entity)
        for class_id, class_level in progress.classes.items():
            definition = self.require_class(class_id)
            for resource_id, resource_definition in definition.resources.items():
                maximum = resource_definition.maximum_for_level(class_level)
                existing = resources.get(resource_id)
                if existing is None:
                    resources[resource_id] = TrackedResource(
                        id=resource_id,
                        current=maximum,
                        maximum=maximum,
                        short_rest_fraction=resource_definition.short_rest_fraction,
                        long_rest_fraction=resource_definition.long_rest_fraction,
                    )
                else:
                    increase = max(0, maximum - existing.maximum)
                    existing.maximum = max(existing.maximum, maximum)
                    existing.current = min(existing.maximum, existing.current + increase)
                    existing.short_rest_fraction = resource_definition.short_rest_fraction
                    existing.long_rest_fraction = resource_definition.long_rest_fraction
        self.set_resources(entity, resources)
        return resources

    @staticmethod
    def _remove_equipment_item(state: EquipmentState, item_id: str) -> None:
        for slot in [slot for slot, equipped_id in state.slots.items() if equipped_id == item_id]:
            state.slots.pop(slot, None)
        state.attuned.discard(item_id)


def default_rest_profiles() -> dict[str, RestProfile]:
    return {
        "short_rest": RestProfile(
            id="short_rest",
            kind=RestKind.SHORT,
            duration_seconds=3600.0,
            hp_fraction=0.0,
            energy_fraction=0.5,
        ),
        "long_rest": RestProfile(
            id="long_rest",
            kind=RestKind.LONG,
            duration_seconds=8 * 3600.0,
            hp_fraction=1.0,
            energy_fraction=1.0,
        ),
    }


def default_character_lifecycle() -> CharacterLifecycle:
    adventurer = CharacterClassDefinition(
        id="adventurer",
        name="Adventurer",
        hit_die=8,
        primary_abilities=("strength", "dexterity"),
        resources={
            "resolve": ClassResourceDefinition(
                id="resolve",
                name="Resolve",
                base_max=2,
                per_level=0.5,
                short_rest_fraction=0.5,
                long_rest_fraction=1.0,
            )
        },
        level_benefits={
            4: LevelBenefit(level=4, ability_points=2),
            8: LevelBenefit(level=8, ability_points=2),
            12: LevelBenefit(level=12, ability_points=2),
            16: LevelBenefit(level=16, ability_points=2),
            19: LevelBenefit(level=19, ability_points=2),
        },
    )
    return CharacterLifecycle(classes={adventurer.id: adventurer})
