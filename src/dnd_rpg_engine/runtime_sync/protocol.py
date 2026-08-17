from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.models import CampaignState
from dnd_rpg_engine.knowledge.authority import KnowledgeView


class VisualBinding(BaseModel):
    entity_id: str
    scene: str | None = None
    sprite: str | None = None
    model: str | None = None
    animation_set: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeSnapshot(BaseModel):
    sequence: int = Field(ge=0)
    campaign_id: str
    simulation_time: float
    active_map_id: str | None = None
    entities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    facts: dict[str, Any] = Field(default_factory=dict)
    bindings: dict[str, VisualBinding] = Field(default_factory=dict)
    snapshot_hash: str = ""

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["snapshot_hash"] = ""
        return payload

    def compute_hash(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


class DeltaOperation(BaseModel):
    operation: str
    path: str
    value: Any = None


class RuntimeDelta(BaseModel):
    sequence: int = Field(ge=0)
    base_hash: str
    target_hash: str
    simulation_time: float
    operations: list[DeltaOperation] = Field(default_factory=list)


class ClientSyncCursor(BaseModel):
    client_id: str
    sequence: int = 0
    snapshot_hash: str = ""


class RuntimeSynchronizer:
    """Build deterministic client frames for browser/Godot/remote runtimes.

    The synchronizer consumes either full campaign truth or an already-redacted
    KnowledgeView. That makes visual clients incapable of learning more than the
    authority layer explicitly exposes.
    """

    def __init__(self) -> None:
        self.sequence = 0
        self.bindings: dict[str, VisualBinding] = {}

    def register_binding(self, binding: VisualBinding) -> None:
        self.bindings[binding.entity_id] = binding

    def snapshot_from_state(self, state: CampaignState) -> RuntimeSnapshot:
        self.sequence += 1
        snapshot = RuntimeSnapshot(
            sequence=self.sequence,
            campaign_id=state.id,
            simulation_time=state.simulation_time,
            active_map_id=state.active_map_id,
            entities={
                entity_id: entity.model_dump(mode="json")
                for entity_id, entity in sorted(state.entities.items())
            },
            bindings={
                entity_id: binding
                for entity_id, binding in sorted(self.bindings.items())
                if entity_id in state.entities
            },
        )
        return snapshot.model_copy(update={"snapshot_hash": snapshot.compute_hash()})

    def snapshot_from_knowledge(self, view: KnowledgeView) -> RuntimeSnapshot:
        self.sequence += 1
        snapshot = RuntimeSnapshot(
            sequence=self.sequence,
            campaign_id=view.campaign_id,
            simulation_time=view.simulation_time,
            active_map_id=view.active_map_id,
            entities={key: value for key, value in sorted(view.entities.items())},
            facts={key: value.model_dump(mode="json") for key, value in sorted(view.facts.items())},
            bindings={
                entity_id: binding
                for entity_id, binding in sorted(self.bindings.items())
                if entity_id in view.entities
            },
        )
        return snapshot.model_copy(update={"snapshot_hash": snapshot.compute_hash()})

    def diff(self, previous: RuntimeSnapshot, current: RuntimeSnapshot) -> RuntimeDelta:
        if previous.campaign_id != current.campaign_id:
            raise ValueError("cannot diff runtime snapshots from different campaigns")
        operations: list[DeltaOperation] = []
        self._diff_mapping("/entities", previous.entities, current.entities, operations)
        self._diff_mapping("/facts", previous.facts, current.facts, operations)
        self._diff_mapping(
            "/bindings",
            {key: value.model_dump(mode="json") for key, value in previous.bindings.items()},
            {key: value.model_dump(mode="json") for key, value in current.bindings.items()},
            operations,
        )
        if previous.active_map_id != current.active_map_id:
            operations.append(DeltaOperation(operation="replace", path="/active_map_id", value=current.active_map_id))
        return RuntimeDelta(
            sequence=current.sequence,
            base_hash=previous.snapshot_hash,
            target_hash=current.snapshot_hash,
            simulation_time=current.simulation_time,
            operations=operations,
        )

    def apply(self, previous: RuntimeSnapshot, delta: RuntimeDelta) -> RuntimeSnapshot:
        if previous.snapshot_hash != delta.base_hash:
            raise ValueError("runtime delta base hash mismatch")
        payload = previous.model_dump(mode="json")
        payload["sequence"] = delta.sequence
        payload["simulation_time"] = delta.simulation_time
        for operation in delta.operations:
            self._apply_operation(payload, operation)
        payload["snapshot_hash"] = ""
        snapshot = RuntimeSnapshot.model_validate(payload)
        snapshot = snapshot.model_copy(update={"snapshot_hash": snapshot.compute_hash()})
        if snapshot.snapshot_hash != delta.target_hash:
            raise ValueError("runtime delta target hash mismatch")
        return snapshot

    @staticmethod
    def _diff_mapping(
        prefix: str,
        before: dict[str, Any],
        after: dict[str, Any],
        operations: list[DeltaOperation],
    ) -> None:
        for key in sorted(set(before) - set(after)):
            operations.append(DeltaOperation(operation="remove", path=f"{prefix}/{key}"))
        for key in sorted(set(after) - set(before)):
            operations.append(DeltaOperation(operation="add", path=f"{prefix}/{key}", value=after[key]))
        for key in sorted(set(before) & set(after)):
            if before[key] != after[key]:
                operations.append(DeltaOperation(operation="replace", path=f"{prefix}/{key}", value=after[key]))

    @staticmethod
    def _apply_operation(payload: dict[str, Any], operation: DeltaOperation) -> None:
        parts = [value for value in operation.path.split("/") if value]
        if not parts:
            raise ValueError("runtime delta path cannot be empty")
        cursor: dict[str, Any] = payload
        for part in parts[:-1]:
            raw = cursor.setdefault(part, {})
            if not isinstance(raw, dict):
                raise ValueError(f"runtime delta path is not an object: {operation.path}")
            cursor = raw
        key = parts[-1]
        if operation.operation in {"add", "replace"}:
            cursor[key] = operation.value
        elif operation.operation == "remove":
            cursor.pop(key, None)
        else:
            raise ValueError(f"unsupported runtime delta operation: {operation.operation}")
