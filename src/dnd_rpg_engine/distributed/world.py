from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.models import Entity


class ShardStatus(StrEnum):
    STARTING = "starting"
    READY = "ready"
    DRAINING = "draining"
    OFFLINE = "offline"


class WorldShard(BaseModel):
    id: str
    status: ShardStatus = ShardStatus.READY
    capacity: int = Field(default=1000, ge=1)
    load: int = Field(default=0, ge=0)
    regions: set[str] = Field(default_factory=set)
    heartbeat_at: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.status is ShardStatus.READY and self.load < self.capacity


class CrossShardMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_shard: str
    target_shard: str
    topic: str
    payload: dict[str, Any] = Field(default_factory=dict)
    lamport: int = Field(default=0, ge=0)
    idempotency_key: str | None = None


class TransferStatus(StrEnum):
    PREPARED = "prepared"
    ACCEPTED = "accepted"
    COMMITTED = "committed"
    ABORTED = "aborted"


class EntityTransfer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    entity_id: str
    source_shard: str
    target_shard: str
    target_region: str
    entity_payload: dict[str, Any]
    state_hash: str
    status: TransferStatus = TransferStatus.PREPARED
    prepared_at: float = 0.0
    committed_at: float | None = None
    abort_reason: str | None = None


class ShardDirectory:
    """Deterministic region routing with stable rendezvous hashing."""

    def __init__(self) -> None:
        self.shards: dict[str, WorldShard] = {}

    def register(self, shard: WorldShard) -> None:
        self.shards[shard.id] = shard

    def heartbeat(self, shard_id: str, *, now: float, load: int | None = None, status: ShardStatus | None = None) -> WorldShard:
        shard = self.shards[shard_id]
        shard.heartbeat_at = now
        if load is not None:
            shard.load = max(0, load)
        if status is not None:
            shard.status = status
        return shard

    def expire(self, *, now: float, timeout: float) -> list[str]:
        expired: list[str] = []
        for shard in self.shards.values():
            if shard.status is ShardStatus.OFFLINE:
                continue
            if now - shard.heartbeat_at > timeout:
                shard.status = ShardStatus.OFFLINE
                expired.append(shard.id)
        return sorted(expired)

    def route(self, region: str) -> WorldShard:
        explicit = [shard for shard in self.shards.values() if region in shard.regions and shard.available]
        candidates = explicit or [shard for shard in self.shards.values() if shard.available]
        if not candidates:
            raise RuntimeError("no ready shard has capacity")
        return max(candidates, key=lambda shard: (self._score(region, shard.id), -shard.load, shard.id))

    def rebalance_plan(self, regions: list[str], current: dict[str, str]) -> dict[str, str]:
        plan: dict[str, str] = {}
        for region in sorted(set(regions)):
            target = self.route(region).id
            if current.get(region) != target:
                plan[region] = target
        return plan

    @staticmethod
    def _score(key: str, shard_id: str) -> int:
        digest = hashlib.sha256(f"{key}\0{shard_id}".encode()).digest()
        return int.from_bytes(digest[:8], "big")


class TransferCoordinator:
    """Two-phase cross-shard entity transfer coordinator.

    Transfers are prepared from a canonical entity payload, accepted only when
    the destination confirms the same state hash, and then committed exactly
    once. This avoids disappearing/duplicated entities during shard handoff.
    """

    def __init__(self) -> None:
        self.transfers: dict[str, EntityTransfer] = {}
        self.committed_entities: dict[str, str] = {}
        self.seen_messages: set[str] = set()
        self.lamport = 0

    def prepare(
        self,
        entity: Entity,
        *,
        source_shard: str,
        target_shard: str,
        target_region: str,
        now: float,
    ) -> EntityTransfer:
        payload = entity.model_dump(mode="json")
        state_hash = self._hash_payload(payload)
        transfer = EntityTransfer(
            entity_id=entity.id,
            source_shard=source_shard,
            target_shard=target_shard,
            target_region=target_region,
            entity_payload=payload,
            state_hash=state_hash,
            prepared_at=now,
        )
        self.transfers[transfer.id] = transfer
        return transfer

    def accept(self, transfer_id: str, *, destination_hash: str) -> EntityTransfer:
        transfer = self.transfers[transfer_id]
        if transfer.status is TransferStatus.ABORTED:
            raise ValueError("cannot accept an aborted transfer")
        if destination_hash != transfer.state_hash:
            raise ValueError("destination entity hash does not match prepared transfer")
        transfer.status = TransferStatus.ACCEPTED
        return transfer

    def commit(self, transfer_id: str, *, now: float) -> EntityTransfer:
        transfer = self.transfers[transfer_id]
        if transfer.status is TransferStatus.COMMITTED:
            return transfer
        if transfer.status is not TransferStatus.ACCEPTED:
            raise ValueError("transfer must be accepted before commit")
        previous = self.committed_entities.get(transfer.entity_id)
        if previous is not None and previous != transfer.id:
            raise ValueError("entity already committed through another transfer")
        transfer.status = TransferStatus.COMMITTED
        transfer.committed_at = now
        self.committed_entities[transfer.entity_id] = transfer.id
        return transfer

    def abort(self, transfer_id: str, *, reason: str) -> EntityTransfer:
        transfer = self.transfers[transfer_id]
        if transfer.status is TransferStatus.COMMITTED:
            raise ValueError("cannot abort a committed transfer")
        transfer.status = TransferStatus.ABORTED
        transfer.abort_reason = reason
        return transfer

    def restore_entity(self, transfer_id: str) -> Entity:
        transfer = self.transfers[transfer_id]
        if transfer.status not in {TransferStatus.ACCEPTED, TransferStatus.COMMITTED}:
            raise ValueError("transfer is not accepted")
        if self._hash_payload(transfer.entity_payload) != transfer.state_hash:
            raise ValueError("transfer payload hash verification failed")
        return Entity.model_validate(transfer.entity_payload)

    def message(
        self,
        *,
        source_shard: str,
        target_shard: str,
        topic: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> CrossShardMessage:
        self.lamport += 1
        return CrossShardMessage(
            source_shard=source_shard,
            target_shard=target_shard,
            topic=topic,
            payload=dict(payload or {}),
            lamport=self.lamport,
            idempotency_key=idempotency_key,
        )

    def receive(self, message: CrossShardMessage) -> bool:
        self.lamport = max(self.lamport, message.lamport) + 1
        key = message.idempotency_key or message.id
        if key in self.seen_messages:
            return False
        self.seen_messages.add(key)
        return True

    @staticmethod
    def _hash_payload(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()
