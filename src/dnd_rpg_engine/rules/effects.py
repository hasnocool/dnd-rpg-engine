# src/dnd_rpg_engine/rules/effects.py
from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EffectTrigger(StrEnum):
    BEFORE_ACTION = "before_action"
    AFTER_ACTION = "after_action"
    BEFORE_ROLL = "before_roll"
    AFTER_ROLL = "after_roll"
    BEFORE_DAMAGE = "before_damage"
    AFTER_DAMAGE = "after_damage"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    MOVE_START = "move_start"
    MOVE_END = "move_end"
    ZERO_HP = "zero_hp"


class ModifierKind(StrEnum):
    FLAT = "flat"
    MULTIPLIER = "multiplier"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


class Modifier(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str | None = None
    target: str
    kind: ModifierKind = ModifierKind.FLAT
    value: float = 0.0
    priority: int = 100
    tags: set[str] = Field(default_factory=set)


class EffectOperation(BaseModel):
    operation: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EffectDefinition(BaseModel):
    id: str
    name: str
    triggers: set[EffectTrigger] = Field(default_factory=set)
    modifiers: list[Modifier] = Field(default_factory=list)
    operations: list[EffectOperation] = Field(default_factory=list)
    duration_seconds: float | None = Field(default=None, gt=0)
    stack_key: str | None = None
    max_stacks: int = Field(default=1, ge=1, le=100)
    tags: set[str] = Field(default_factory=set)


class EffectInstance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    effect_id: str
    source_id: str | None = None
    target_id: str
    created_at: float = 0.0
    expires_at: float | None = None
    stacks: int = Field(default=1, ge=1, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EffectPipeline:
    """Deterministic effect registry and trigger pipeline.

    The pipeline stores definitions separately from active instances. Consumers
    ask for modifiers/operations at a named trigger; the authoritative runtime
    decides how those results affect rules resolution.
    """

    def __init__(self) -> None:
        self.definitions: dict[str, EffectDefinition] = {}
        self.instances: dict[str, EffectInstance] = {}
        self.by_target: dict[str, list[str]] = {}

    def register(self, definition: EffectDefinition) -> None:
        self.definitions[definition.id] = definition

    def apply(
        self,
        effect_id: str,
        target_id: str,
        *,
        source_id: str | None = None,
        now: float = 0.0,
        stacks: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> EffectInstance:
        definition = self.definitions[effect_id]
        stack_key = definition.stack_key or effect_id
        for instance_id in self.by_target.get(target_id, []):
            current = self.instances[instance_id]
            current_definition = self.definitions[current.effect_id]
            current_key = current_definition.stack_key or current.effect_id
            if current_key != stack_key:
                continue
            current.stacks = min(definition.max_stacks, current.stacks + max(1, stacks))
            if definition.duration_seconds is not None:
                current.expires_at = now + definition.duration_seconds
            current.metadata.update(metadata or {})
            return current

        instance = EffectInstance(
            effect_id=effect_id,
            source_id=source_id,
            target_id=target_id,
            created_at=now,
            expires_at=(now + definition.duration_seconds) if definition.duration_seconds is not None else None,
            stacks=min(definition.max_stacks, max(1, stacks)),
            metadata=dict(metadata or {}),
        )
        self.instances[instance.id] = instance
        self.by_target.setdefault(target_id, []).append(instance.id)
        return instance

    def remove(self, instance_id: str) -> bool:
        instance = self.instances.pop(instance_id, None)
        if instance is None:
            return False
        target_instances = self.by_target.get(instance.target_id, [])
        self.by_target[instance.target_id] = [value for value in target_instances if value != instance_id]
        if not self.by_target[instance.target_id]:
            self.by_target.pop(instance.target_id, None)
        return True

    def expire(self, now: float) -> list[EffectInstance]:
        expired = [
            instance
            for instance in self.instances.values()
            if instance.expires_at is not None and instance.expires_at <= now
        ]
        for instance in expired:
            self.remove(instance.id)
        return sorted(expired, key=lambda value: (value.expires_at or 0.0, value.id))

    def active_for(self, target_id: str, *, now: float | None = None) -> list[EffectInstance]:
        if now is not None:
            self.expire(now)
        active = [self.instances[value] for value in self.by_target.get(target_id, []) if value in self.instances]
        return sorted(active, key=lambda value: (value.created_at, value.id))

    def modifiers_for(
        self,
        target_id: str,
        trigger: EffectTrigger,
        *,
        target: str | None = None,
        tags: set[str] | None = None,
        now: float | None = None,
    ) -> list[Modifier]:
        wanted_tags = tags or set()
        results: list[Modifier] = []
        for instance in self.active_for(target_id, now=now):
            definition = self.definitions[instance.effect_id]
            if trigger not in definition.triggers:
                continue
            if wanted_tags and definition.tags and not (wanted_tags & definition.tags):
                continue
            for modifier in definition.modifiers:
                if target is not None and modifier.target != target:
                    continue
                for _ in range(instance.stacks):
                    results.append(modifier.model_copy(deep=True))
        return sorted(results, key=lambda value: (value.priority, value.id))

    def operations_for(
        self,
        target_id: str,
        trigger: EffectTrigger,
        *,
        now: float | None = None,
    ) -> list[EffectOperation]:
        results: list[EffectOperation] = []
        for instance in self.active_for(target_id, now=now):
            definition = self.definitions[instance.effect_id]
            if trigger not in definition.triggers:
                continue
            for _ in range(instance.stacks):
                results.extend(operation.model_copy(deep=True) for operation in definition.operations)
        return results
