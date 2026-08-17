# src/dnd_rpg_engine/ai/intelligence.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Protocol

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.commands import GameCommand, parse_command
from dnd_rpg_engine.core.models import CampaignState, Entity, EntityKind
from dnd_rpg_engine.tactical.actions import ActionDefinition


class MemoryRecord(BaseModel):
    id: str
    simulation_time: float = Field(ge=0)
    text: str
    importance: float = Field(default=0.5, ge=0, le=1)
    tags: set[str] = Field(default_factory=set)
    subject_id: str | None = None
    expires_at: float | None = None


class PersistentActorMemory:
    """Deterministic memory stored directly on an entity component.

    Because records live in ``entity.components``, normal campaign persistence,
    replay snapshots, and multiplayer state transfer retain actor memories.
    """

    def __init__(self, entity: Entity, *, limit: int = 256) -> None:
        self.entity = entity
        self.limit = max(1, limit)

    def _raw(self) -> list[dict[str, Any]]:
        component = self.entity.component("agent_memory")
        raw = component.setdefault("entries", [])
        if not isinstance(raw, list):
            raw = []
            component["entries"] = raw
        return raw

    def add(
        self,
        *,
        simulation_time: float,
        text: str,
        importance: float = 0.5,
        tags: set[str] | None = None,
        subject_id: str | None = None,
        expires_at: float | None = None,
    ) -> MemoryRecord:
        raw = self._raw()
        sequence = int(self.entity.component("agent_memory").get("sequence", 0)) + 1
        self.entity.component("agent_memory")["sequence"] = sequence
        record = MemoryRecord(
            id=f"{self.entity.id}:memory:{sequence}",
            simulation_time=max(0.0, simulation_time),
            text=text,
            importance=importance,
            tags=set(tags or set()),
            subject_id=subject_id,
            expires_at=expires_at,
        )
        raw.append(record.model_dump(mode="json"))
        if len(raw) > self.limit:
            ranked = sorted(
                (MemoryRecord.model_validate(value) for value in raw),
                key=lambda value: (value.importance, value.simulation_time, value.id),
                reverse=True,
            )[: self.limit]
            ranked.sort(key=lambda value: (value.simulation_time, value.id))
            raw[:] = [value.model_dump(mode="json") for value in ranked]
        return record

    def recall(
        self,
        *,
        now: float,
        tags: set[str] | None = None,
        subject_id: str | None = None,
        limit: int = 12,
    ) -> list[MemoryRecord]:
        wanted_tags = tags or set()
        records = [MemoryRecord.model_validate(value) for value in self._raw()]
        records = [value for value in records if value.expires_at is None or value.expires_at > now]
        if wanted_tags:
            records = [value for value in records if value.tags & wanted_tags]
        if subject_id is not None:
            records = [value for value in records if value.subject_id == subject_id]
        records.sort(key=lambda value: (value.importance, value.simulation_time, value.id), reverse=True)
        return records[: max(0, limit)]


class Observation(BaseModel):
    entity_id: str
    distance: float = Field(ge=0)
    visible: bool = True
    alive: bool = True
    hostile: bool = False
    hp_fraction: float = Field(default=1.0, ge=0, le=1)
    tags: set[str] = Field(default_factory=set)


class PerceptionSnapshot(BaseModel):
    actor_id: str
    simulation_time: float
    observations: list[Observation] = Field(default_factory=list)
    nearby_allies: int = 0
    nearby_hostiles: int = 0
    scheduled_location: str | None = None
    scheduled_activity: str | None = None
    memories: list[MemoryRecord] = Field(default_factory=list)


class PerceptionSystem:
    def observe(
        self,
        actor: Entity,
        state: CampaignState,
        *,
        max_distance: float = 30.0,
        line_of_sight: Callable[[Entity, Entity], bool] | None = None,
        scheduled_location: str | None = None,
        scheduled_activity: str | None = None,
    ) -> PerceptionSnapshot:
        explicit_target = str(actor.component("ai").get("target_id", ""))
        hostile_to = {str(value) for value in actor.component("ai").get("hostile_to", [])}
        actor_faction = actor.component("faction").get("id")
        observations: list[Observation] = []
        allies = 0
        hostiles = 0
        for entity in state.entities.values():
            if entity.id == actor.id or not entity.alive:
                continue
            distance = actor.position.distance_to(entity.position)
            if distance > max_distance:
                continue
            visible = line_of_sight(actor, entity) if line_of_sight is not None else True
            if not visible:
                continue
            other_faction = entity.component("faction").get("id")
            hostile = (
                entity.id == explicit_target
                or entity.id in hostile_to
                or (actor.kind is not EntityKind.PLAYER and entity.kind is EntityKind.PLAYER and bool(actor.component("ai").get("hostile", True)))
            )
            same_faction = actor_faction is not None and actor_faction == other_faction
            if hostile:
                hostiles += 1
            elif same_faction:
                allies += 1
            hp_fraction = entity.resources.hp / max(1, entity.resources.max_hp)
            observations.append(
                Observation(
                    entity_id=entity.id,
                    distance=distance,
                    visible=visible,
                    alive=entity.alive,
                    hostile=hostile,
                    hp_fraction=max(0.0, min(1.0, hp_fraction)),
                    tags=set(entity.tags),
                )
            )
        observations.sort(key=lambda value: (value.distance, value.entity_id))
        memories = PersistentActorMemory(actor).recall(now=state.simulation_time, limit=8)
        return PerceptionSnapshot(
            actor_id=actor.id,
            simulation_time=state.simulation_time,
            observations=observations,
            nearby_allies=allies,
            nearby_hostiles=hostiles,
            scheduled_location=scheduled_location,
            scheduled_activity=scheduled_activity,
            memories=memories,
        )


class GoalKind(StrEnum):
    SURVIVE = "survive"
    DEFEAT = "defeat"
    PROTECT = "protect"
    REACH = "reach"
    PATROL = "patrol"
    SOCIAL = "social"


class Goal(BaseModel):
    id: str
    kind: GoalKind
    weight: float = Field(default=1.0, ge=0, le=10)
    target_id: str | None = None
    tags: set[str] = Field(default_factory=set)


class ActionCandidate(BaseModel):
    id: str
    command: dict[str, Any]
    utility: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)
    factors: dict[str, float] = Field(default_factory=dict)


class UtilityScorer:
    def score(
        self,
        candidate: ActionCandidate,
        *,
        goals: list[Goal],
        personality: dict[str, float] | None = None,
    ) -> ActionCandidate:
        personality = personality or {}
        score = candidate.utility
        reasons = list(candidate.reasons)
        for key, value in sorted(candidate.factors.items()):
            score += value
            reasons.append(f"factor:{key}={value:.3f}")
        for goal in goals:
            overlap = candidate.tags & goal.tags
            direct_target = goal.target_id is not None and candidate.command.get("target_id") == goal.target_id
            if overlap or direct_target:
                bonus = goal.weight * (0.12 + 0.04 * len(overlap))
                score += bonus
                reasons.append(f"goal:{goal.id}=+{bonus:.3f}")
        for tag in sorted(candidate.tags):
            bias = float(personality.get(tag, 0.0))
            if bias:
                score += bias
                reasons.append(f"personality:{tag}={bias:+.3f}")
        return candidate.model_copy(update={"utility": score, "reasons": reasons})


class TacticalPlanner:
    def __init__(self, scorer: UtilityScorer | None = None) -> None:
        self.scorer = scorer or UtilityScorer()

    @staticmethod
    def _target(perception: PerceptionSnapshot) -> Observation | None:
        hostile = [value for value in perception.observations if value.hostile and value.alive]
        return min(hostile, key=lambda value: (value.distance, value.hp_fraction, value.entity_id), default=None)

    def candidates(
        self,
        actor: Entity,
        state: CampaignState,
        perception: PerceptionSnapshot,
        *,
        action: ActionDefinition,
        goals: list[Goal] | None = None,
        personality: dict[str, float] | None = None,
    ) -> list[ActionCandidate]:
        goals = list(goals or [])
        target_observation = self._target(perception)
        hp_fraction = actor.resources.hp / max(1, actor.resources.max_hp)
        candidates: list[ActionCandidate] = []
        if target_observation is not None:
            target = state.entities[target_observation.entity_id]
            distance = target_observation.distance
            if distance <= action.range + 1e-9:
                candidates.append(
                    ActionCandidate(
                        id="attack",
                        command={"type": "attack", "actor_id": actor.id, "target_id": target.id, "action_id": action.id},
                        utility=0.55,
                        tags={"attack", "aggressive", "defeat"},
                        factors={
                            "target_wounded": (1.0 - target_observation.hp_fraction) * 0.22,
                            "close_range": max(0.0, 1.0 - distance / max(action.range, 0.1)) * 0.12,
                        },
                    )
                )
            else:
                speed = float(actor.component("movement").get("units_per_second", 1.5))
                travel = min(distance, max(0.1, speed * 2.0))
                ratio = travel / max(distance, 1e-9)
                destination = {
                    "x": actor.position.x + (target.position.x - actor.position.x) * ratio,
                    "y": actor.position.y + (target.position.y - actor.position.y) * ratio,
                    "z": actor.position.z + (target.position.z - actor.position.z) * ratio,
                }
                candidates.append(
                    ActionCandidate(
                        id="advance",
                        command={"type": "move", "actor_id": actor.id, **destination},
                        utility=0.40,
                        tags={"move", "approach", "defeat"},
                        factors={"target_proximity": max(0.0, 1.0 - distance / 30.0) * 0.15},
                    )
                )

            if hp_fraction < 0.45:
                dx = actor.position.x - target.position.x
                dy = actor.position.y - target.position.y
                dz = actor.position.z - target.position.z
                magnitude = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
                flee_distance = float(actor.component("movement").get("units_per_second", 1.5)) * 3.0
                candidates.append(
                    ActionCandidate(
                        id="flee",
                        command={
                            "type": "move",
                            "actor_id": actor.id,
                            "x": actor.position.x + dx / magnitude * flee_distance,
                            "y": actor.position.y + dy / magnitude * flee_distance,
                            "z": actor.position.z + dz / magnitude * flee_distance,
                        },
                        utility=0.28,
                        tags={"move", "defensive", "survive", "flee"},
                        factors={
                            "low_hp": (1.0 - hp_fraction) * 0.72,
                            "outnumbered": max(0, perception.nearby_hostiles - perception.nearby_allies) * 0.12,
                        },
                    )
                )

        if perception.scheduled_location and actor.position.area_id != perception.scheduled_location:
            candidates.append(
                ActionCandidate(
                    id="follow_schedule",
                    command={"type": "interact", "actor_id": actor.id, "target_id": perception.scheduled_location, "interaction": "travel_intent"},
                    utility=0.18,
                    tags={"schedule", "routine", "reach"},
                    factors={"schedule_pressure": 0.18},
                    reasons=[f"scheduled:{perception.scheduled_activity or 'activity'}"],
                )
            )

        candidates.append(
            ActionCandidate(
                id="wait",
                command={"type": "wait", "actor_id": actor.id},
                utility=0.05,
                tags={"wait", "defensive"},
            )
        )
        scored = [self.scorer.score(value, goals=goals, personality=personality) for value in candidates]
        return sorted(scored, key=lambda value: (-value.utility, value.id))

    def choose(
        self,
        actor: Entity,
        state: CampaignState,
        perception: PerceptionSnapshot,
        *,
        action: ActionDefinition,
        goals: list[Goal] | None = None,
        personality: dict[str, float] | None = None,
    ) -> ActionCandidate:
        return self.candidates(
            actor,
            state,
            perception,
            action=action,
            goals=goals,
            personality=personality,
        )[0]

    def plan_command(
        self,
        actor: Entity,
        state: CampaignState,
        perception: PerceptionSnapshot,
        *,
        action: ActionDefinition,
        goals: list[Goal] | None = None,
        personality: dict[str, float] | None = None,
    ) -> GameCommand:
        selected = self.choose(
            actor,
            state,
            perception,
            action=action,
            goals=goals,
            personality=personality,
        )
        return parse_command(selected.command)


class BehaviorStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


@dataclass(slots=True)
class BehaviorContext:
    actor: Entity
    state: CampaignState
    perception: PerceptionSnapshot
    blackboard: dict[str, Any] = field(default_factory=dict)


class BehaviorNode(Protocol):
    def tick(self, context: BehaviorContext) -> BehaviorStatus: ...


@dataclass(slots=True)
class ConditionNode:
    predicate: Callable[[BehaviorContext], bool]

    def tick(self, context: BehaviorContext) -> BehaviorStatus:
        return BehaviorStatus.SUCCESS if self.predicate(context) else BehaviorStatus.FAILURE


@dataclass(slots=True)
class ActionNode:
    action: Callable[[BehaviorContext], BehaviorStatus]

    def tick(self, context: BehaviorContext) -> BehaviorStatus:
        return self.action(context)


@dataclass(slots=True)
class SequenceNode:
    children: list[BehaviorNode]

    def tick(self, context: BehaviorContext) -> BehaviorStatus:
        for child in self.children:
            status = child.tick(context)
            if status is not BehaviorStatus.SUCCESS:
                return status
        return BehaviorStatus.SUCCESS


@dataclass(slots=True)
class SelectorNode:
    children: list[BehaviorNode]

    def tick(self, context: BehaviorContext) -> BehaviorStatus:
        for child in self.children:
            status = child.tick(context)
            if status is not BehaviorStatus.FAILURE:
                return status
        return BehaviorStatus.FAILURE


class IntelligentActorController:
    """Perception -> goals/utility -> authoritative GameCommand planner."""

    def __init__(
        self,
        *,
        perception: PerceptionSystem | None = None,
        planner: TacticalPlanner | None = None,
    ) -> None:
        self.perception = perception or PerceptionSystem()
        self.planner = planner or TacticalPlanner()

    def plan(
        self,
        actor: Entity,
        state: CampaignState,
        *,
        action: ActionDefinition,
        goals: list[Goal] | None = None,
        personality: dict[str, float] | None = None,
        line_of_sight: Callable[[Entity, Entity], bool] | None = None,
        scheduled_location: str | None = None,
        scheduled_activity: str | None = None,
    ) -> tuple[GameCommand, PerceptionSnapshot, ActionCandidate]:
        snapshot = self.perception.observe(
            actor,
            state,
            line_of_sight=line_of_sight,
            scheduled_location=scheduled_location,
            scheduled_activity=scheduled_activity,
        )
        candidate = self.planner.choose(
            actor,
            state,
            snapshot,
            action=action,
            goals=goals,
            personality=personality,
        )
        memory = PersistentActorMemory(actor)
        memory.add(
            simulation_time=state.simulation_time,
            text=f"Planned {candidate.id} with utility {candidate.utility:.3f}",
            importance=min(1.0, 0.35 + candidate.utility / 3.0),
            tags={"decision", *candidate.tags},
            subject_id=str(candidate.command.get("target_id")) if candidate.command.get("target_id") else None,
        )
        return parse_command(candidate.command), snapshot, candidate
