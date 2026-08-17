from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.models import CampaignState


class SceneKind(StrEnum):
    EXPLORATION = "exploration"
    ENCOUNTER = "encounter"
    DIALOGUE = "dialogue"
    TRAVEL = "travel"
    DOWNTIME = "downtime"
    SETTLEMENT = "settlement"
    DUNGEON = "dungeon"
    CUSTOM = "custom"


class SceneStatus(StrEnum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class SceneDefinition(BaseModel):
    id: str
    name: str
    kind: SceneKind = SceneKind.CUSTOM
    map_id: str | None = None
    entity_ids: set[str] = Field(default_factory=set)
    preload_scene_ids: set[str] = Field(default_factory=set)
    next_scene_ids: list[str] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneRuntime(BaseModel):
    scene_id: str
    status: SceneStatus = SceneStatus.UNLOADED
    entered_at: float | None = None
    suspended_at: float | None = None
    resolved_at: float | None = None
    visit_count: int = 0
    flags: dict[str, Any] = Field(default_factory=dict)


class SceneTransition(BaseModel):
    scene_id: str
    previous_status: SceneStatus
    status: SceneStatus
    simulation_time: float
    reason: str = ""
    active_scene_ids: list[str] = Field(default_factory=list)


_ALLOWED: dict[SceneStatus, set[SceneStatus]] = {
    SceneStatus.UNLOADED: {SceneStatus.LOADING, SceneStatus.ARCHIVED},
    SceneStatus.LOADING: {SceneStatus.ACTIVE, SceneStatus.UNLOADED, SceneStatus.ARCHIVED},
    SceneStatus.ACTIVE: {SceneStatus.SUSPENDED, SceneStatus.RESOLVED, SceneStatus.ARCHIVED},
    SceneStatus.SUSPENDED: {SceneStatus.ACTIVE, SceneStatus.RESOLVED, SceneStatus.ARCHIVED},
    SceneStatus.RESOLVED: {SceneStatus.ARCHIVED, SceneStatus.ACTIVE},
    SceneStatus.ARCHIVED: set(),
}


class CampaignOrchestrator:
    """Authoritative scene lifecycle and world-streaming coordinator.

    Runtime state is mirrored into ``CampaignState.metadata`` so snapshots,
    event sourcing, reconnects, and production workers naturally retain the
    campaign orchestration state.
    """

    metadata_key = "campaign_orchestrator"

    def __init__(self, state: CampaignState) -> None:
        self.state = state
        self.definitions: dict[str, SceneDefinition] = {}
        self.runtime: dict[str, SceneRuntime] = {}
        self._restore_runtime()

    def register(self, definition: SceneDefinition) -> None:
        self.definitions[definition.id] = definition
        self.runtime.setdefault(definition.id, SceneRuntime(scene_id=definition.id))
        self._persist_runtime()

    def register_many(self, definitions: list[SceneDefinition]) -> None:
        for definition in definitions:
            self.register(definition)

    def require(self, scene_id: str) -> SceneDefinition:
        try:
            return self.definitions[scene_id]
        except KeyError as exc:
            raise KeyError(f"unknown scene: {scene_id}") from exc

    def state_for(self, scene_id: str) -> SceneRuntime:
        if scene_id not in self.runtime:
            self.runtime[scene_id] = SceneRuntime(scene_id=scene_id)
        return self.runtime[scene_id]

    def active_scene_ids(self) -> list[str]:
        return sorted(scene_id for scene_id, runtime in self.runtime.items() if runtime.status is SceneStatus.ACTIVE)

    def active_definitions(self) -> list[SceneDefinition]:
        return [self.definitions[scene_id] for scene_id in self.active_scene_ids() if scene_id in self.definitions]

    def load(self, scene_id: str, *, reason: str = "load") -> SceneTransition:
        return self.transition(scene_id, SceneStatus.LOADING, reason=reason)

    def activate(self, scene_id: str, *, reason: str = "activate", exclusive: bool = False) -> SceneTransition:
        runtime = self.state_for(scene_id)
        if runtime.status is SceneStatus.UNLOADED:
            self.transition(scene_id, SceneStatus.LOADING, reason="implicit load")
        if exclusive:
            for active_id in self.active_scene_ids():
                if active_id != scene_id:
                    self.transition(active_id, SceneStatus.SUSPENDED, reason=f"exclusive scene:{scene_id}")
        transition = self.transition(scene_id, SceneStatus.ACTIVE, reason=reason)
        definition = self.definitions.get(scene_id)
        if definition and definition.map_id:
            self.state.active_map_id = definition.map_id
        return transition

    def suspend(self, scene_id: str, *, reason: str = "suspend") -> SceneTransition:
        return self.transition(scene_id, SceneStatus.SUSPENDED, reason=reason)

    def resolve(self, scene_id: str, *, reason: str = "resolved") -> SceneTransition:
        return self.transition(scene_id, SceneStatus.RESOLVED, reason=reason)

    def archive(self, scene_id: str, *, reason: str = "archived") -> SceneTransition:
        return self.transition(scene_id, SceneStatus.ARCHIVED, reason=reason)

    def transition(self, scene_id: str, status: SceneStatus, *, reason: str = "") -> SceneTransition:
        runtime = self.state_for(scene_id)
        previous = runtime.status
        if status is previous:
            return self._transition_record(scene_id, previous, status, reason)
        if status not in _ALLOWED[previous]:
            raise ValueError(f"invalid scene transition: {previous.value} -> {status.value}")
        now = self.state.simulation_time
        runtime.status = status
        if status is SceneStatus.ACTIVE:
            runtime.entered_at = now
            runtime.suspended_at = None
            runtime.visit_count += 1
        elif status is SceneStatus.SUSPENDED:
            runtime.suspended_at = now
        elif status is SceneStatus.RESOLVED:
            runtime.resolved_at = now
        self._persist_runtime()
        return self._transition_record(scene_id, previous, status, reason)

    def next_candidates(self, scene_id: str) -> list[SceneDefinition]:
        definition = self.require(scene_id)
        return [self.definitions[value] for value in definition.next_scene_ids if value in self.definitions]

    def streaming_entity_ids(self, *, include_preload: bool = True) -> set[str]:
        scene_ids = set(self.active_scene_ids())
        if include_preload:
            for scene_id in list(scene_ids):
                definition = self.definitions.get(scene_id)
                if definition:
                    scene_ids.update(definition.preload_scene_ids)
        entity_ids: set[str] = set()
        for scene_id in scene_ids:
            definition = self.definitions.get(scene_id)
            if definition:
                entity_ids.update(definition.entity_ids)
        return entity_ids

    def streamed_state_payload(self) -> dict[str, Any]:
        entity_ids = self.streaming_entity_ids()
        return {
            "campaign_id": self.state.id,
            "simulation_time": self.state.simulation_time,
            "active_scene_ids": self.active_scene_ids(),
            "active_map_id": self.state.active_map_id,
            "entities": {
                entity_id: self.state.entities[entity_id].model_dump(mode="json")
                for entity_id in sorted(entity_ids)
                if entity_id in self.state.entities
            },
        }

    def _transition_record(
        self,
        scene_id: str,
        previous: SceneStatus,
        status: SceneStatus,
        reason: str,
    ) -> SceneTransition:
        return SceneTransition(
            scene_id=scene_id,
            previous_status=previous,
            status=status,
            simulation_time=self.state.simulation_time,
            reason=reason,
            active_scene_ids=self.active_scene_ids(),
        )

    def _restore_runtime(self) -> None:
        raw = self.state.metadata.get(self.metadata_key, {})
        rows = raw.get("scenes", {}) if isinstance(raw, dict) else {}
        if isinstance(rows, dict):
            for scene_id, value in rows.items():
                try:
                    self.runtime[str(scene_id)] = SceneRuntime.model_validate(value)
                except Exception:
                    continue

    def _persist_runtime(self) -> None:
        self.state.metadata[self.metadata_key] = {
            "scenes": {
                scene_id: runtime.model_dump(mode="json")
                for scene_id, runtime in sorted(self.runtime.items())
            },
            "active_scene_ids": self.active_scene_ids(),
        }
