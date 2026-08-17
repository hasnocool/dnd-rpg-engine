from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.event_sourcing import canonical_json
from dnd_rpg_engine.core.models import CampaignState, Entity


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HandoffStatus(StrEnum):
    PREPARED = "prepared"
    SOURCE_COMMITTED = "source_committed"
    ACCEPTED = "accepted"
    ABORTED = "aborted"


class ZoneDefinition(BaseModel):
    id: str
    world_id: str = "default"
    name: str = ""
    neighbors: set[str] = Field(default_factory=set)
    worker_group: str = "default"
    max_entities: int | None = Field(default=None, ge=1)
    tags: set[str] = Field(default_factory=set)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorldPartition(BaseModel):
    world_id: str = "default"
    zones: dict[str, ZoneDefinition] = Field(default_factory=dict)
    entity_zones: dict[str, str] = Field(default_factory=dict)

    def register_zone(self, zone: ZoneDefinition) -> None:
        if zone.world_id != self.world_id:
            raise ValueError("zone belongs to a different world")
        self.zones[zone.id] = zone

    def assign(self, entity_id: str, zone_id: str) -> None:
        if zone_id not in self.zones:
            raise KeyError(f"unknown zone: {zone_id}")
        self.entity_zones[entity_id] = zone_id

    def zone_for(self, entity_id: str) -> str | None:
        return self.entity_zones.get(entity_id)

    def validate_transition(self, source_zone: str, target_zone: str) -> None:
        if source_zone == target_zone:
            raise ValueError("handoff target must differ from source zone")
        source = self.zones[source_zone]
        if target_zone not in self.zones:
            raise KeyError(f"unknown target zone: {target_zone}")
        if source.neighbors and target_zone not in source.neighbors:
            raise ValueError(f"zone {target_zone} is not reachable from {source_zone}")


class EntityHandoff(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    campaign_id: str
    world_id: str
    entity_id: str
    source_zone: str
    target_zone: str
    source_sequence: int = Field(default=0, ge=0)
    entity_payload: dict[str, Any]
    entity_hash: str
    transfer_hash: str
    status: HandoffStatus = HandoffStatus.PREPARED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    accepted_sequence: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        campaign_id: str,
        world_id: str,
        entity: Entity,
        source_zone: str,
        target_zone: str,
        source_sequence: int,
        metadata: dict[str, Any] | None = None,
    ) -> "EntityHandoff":
        payload = entity.model_dump(mode="json")
        entity_hash = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        body = {
            "campaign_id": campaign_id,
            "world_id": world_id,
            "entity_id": entity.id,
            "source_zone": source_zone,
            "target_zone": target_zone,
            "source_sequence": source_sequence,
            "entity_hash": entity_hash,
        }
        transfer_hash = hashlib.sha256(canonical_json(body).encode()).hexdigest()
        return cls(
            campaign_id=campaign_id,
            world_id=world_id,
            entity_id=entity.id,
            source_zone=source_zone,
            target_zone=target_zone,
            source_sequence=source_sequence,
            entity_payload=payload,
            entity_hash=entity_hash,
            transfer_hash=transfer_hash,
            metadata=metadata or {},
        )

    def verify(self) -> bool:
        entity_hash = hashlib.sha256(canonical_json(self.entity_payload).encode()).hexdigest()
        body = {
            "campaign_id": self.campaign_id,
            "world_id": self.world_id,
            "entity_id": self.entity_id,
            "source_zone": self.source_zone,
            "target_zone": self.target_zone,
            "source_sequence": self.source_sequence,
            "entity_hash": self.entity_hash,
        }
        transfer_hash = hashlib.sha256(canonical_json(body).encode()).hexdigest()
        return entity_hash == self.entity_hash and transfer_hash == self.transfer_hash


class ZoneRouter:
    """Stable rendezvous placement for zones across worker IDs."""

    @staticmethod
    def score(zone_id: str, worker_id: str) -> int:
        digest = hashlib.sha256(f"{zone_id}\0{worker_id}".encode()).digest()
        return int.from_bytes(digest, "big")

    def choose(self, zone_id: str, worker_ids: list[str]) -> str:
        if not worker_ids:
            raise ValueError("no workers available")
        return max(sorted(set(worker_ids)), key=lambda worker_id: self.score(zone_id, worker_id))

    def placement(self, zone_ids: list[str], worker_ids: list[str]) -> dict[str, str]:
        return {zone_id: self.choose(zone_id, worker_ids) for zone_id in sorted(set(zone_ids))}


class HandoffCoordinator:
    """Two-phase entity handoff coordinator with deterministic verification.

    The source remains authoritative until ``commit_source`` succeeds. The
    destination accepts only a transfer whose payload hash and transfer hash
    verify, making handoff replay/idempotency explicit instead of relying on
    best-effort network messages.
    """

    def __init__(self, partition: WorldPartition, *, store: Any | None = None) -> None:
        self.partition = partition
        self.store = store
        self.handoffs: dict[str, EntityHandoff] = {}

    async def _persist(self, handoff: EntityHandoff) -> None:
        if self.store is not None:
            await self.store.put_json("distributed.handoff", handoff.id, handoff.model_dump(mode="json"))

    async def prepare(
        self,
        state: CampaignState,
        entity_id: str,
        target_zone: str,
        *,
        source_sequence: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> EntityHandoff:
        entity = state.require_entity(entity_id)
        source_zone = self.partition.zone_for(entity_id) or entity.position.area_id
        self.partition.validate_transition(source_zone, target_zone)
        target = self.partition.zones[target_zone]
        if target.max_entities is not None:
            occupancy = sum(1 for zone_id in self.partition.entity_zones.values() if zone_id == target_zone)
            if occupancy >= target.max_entities:
                raise ValueError("target zone is at capacity")
        handoff = EntityHandoff.build(
            campaign_id=state.id,
            world_id=self.partition.world_id,
            entity=entity,
            source_zone=source_zone,
            target_zone=target_zone,
            source_sequence=source_sequence,
            metadata=metadata,
        )
        self.handoffs[handoff.id] = handoff
        await self._persist(handoff)
        return handoff

    async def commit_source(self, state: CampaignState, handoff_id: str) -> EntityHandoff:
        handoff = self.handoffs[handoff_id]
        if handoff.status is HandoffStatus.SOURCE_COMMITTED:
            return handoff
        if handoff.status is not HandoffStatus.PREPARED:
            raise ValueError(f"handoff cannot commit from {handoff.status.value}")
        entity = state.require_entity(handoff.entity_id)
        current_hash = hashlib.sha256(canonical_json(entity.model_dump(mode="json")).encode()).hexdigest()
        if current_hash != handoff.entity_hash:
            raise ValueError("entity changed after handoff preparation")
        state.entities.pop(entity.id)
        self.partition.entity_zones.pop(entity.id, None)
        handoff.status = HandoffStatus.SOURCE_COMMITTED
        handoff.updated_at = utcnow()
        await self._persist(handoff)
        return handoff

    async def accept_target(
        self,
        state: CampaignState,
        handoff: EntityHandoff,
        *,
        accepted_sequence: int | None = None,
    ) -> Entity:
        if not handoff.verify():
            raise ValueError("handoff verification failed")
        existing = state.entities.get(handoff.entity_id)
        if handoff.status is HandoffStatus.ACCEPTED:
            if existing is None:
                raise ValueError("accepted handoff is missing destination entity")
            return existing
        if handoff.status is not HandoffStatus.SOURCE_COMMITTED:
            raise ValueError("source must commit before destination acceptance")
        if existing is not None:
            existing_hash = hashlib.sha256(canonical_json(existing.model_dump(mode="json")).encode()).hexdigest()
            if existing_hash != handoff.entity_hash:
                raise ValueError("destination already contains a conflicting entity")
            entity = existing
        else:
            entity = Entity.model_validate(copy.deepcopy(handoff.entity_payload))
            state.add_entity(entity)
        entity.position.area_id = handoff.target_zone
        entity.component("distributed")["zone_id"] = handoff.target_zone
        entity.component("distributed")["last_handoff_id"] = handoff.id
        self.partition.assign(entity.id, handoff.target_zone)
        handoff.status = HandoffStatus.ACCEPTED
        handoff.accepted_sequence = accepted_sequence
        handoff.updated_at = utcnow()
        self.handoffs[handoff.id] = handoff
        await self._persist(handoff)
        return entity

    async def abort(self, handoff_id: str, *, reason: str = "") -> EntityHandoff:
        handoff = self.handoffs[handoff_id]
        if handoff.status is HandoffStatus.ACCEPTED:
            raise ValueError("accepted handoff cannot be aborted")
        handoff.status = HandoffStatus.ABORTED
        handoff.updated_at = utcnow()
        if reason:
            handoff.metadata["abort_reason"] = reason
        await self._persist(handoff)
        return handoff


class DistributedWorldRuntime:
    def __init__(self, partition: WorldPartition, *, store: Any | None = None) -> None:
        self.partition = partition
        self.router = ZoneRouter()
        self.handoffs = HandoffCoordinator(partition, store=store)

    def place_zones(self, workers: list[dict[str, Any]]) -> dict[str, str]:
        eligible = [str(worker["worker_id"]) for worker in workers if int(worker.get("capacity", 0)) > 0]
        return self.router.placement(list(self.partition.zones), eligible)

    def register_entity(self, entity: Entity, zone_id: str | None = None) -> None:
        target = zone_id or entity.component("distributed").get("zone_id") or entity.position.area_id
        self.partition.assign(entity.id, str(target))
