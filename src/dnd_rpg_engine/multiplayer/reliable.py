from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.commands import parse_command
from dnd_rpg_engine.multiplayer.protocol import ServerEnvelope
from dnd_rpg_engine.multiplayer.sessions import CampaignSession


class SequenceGapError(ValueError):
    pass


class RateLimitError(ValueError):
    pass


class ReliableCommandEnvelope(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    client_id: str
    client_sequence: int = Field(ge=1)
    command: dict[str, Any]
    narrate: bool = False

    def fingerprint(self) -> str:
        payload = json.dumps(self.command, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class ReliableAck(BaseModel):
    request_id: str
    client_id: str
    client_sequence: int
    server_sequence: int
    engine_version: int
    simulation_time: float
    accepted: bool = True
    duplicate: bool = False
    command_fingerprint: str
    event_sequences: list[int] = Field(default_factory=list)
    narration: str | None = None


class PresenceRecord(BaseModel):
    client_id: str
    user_id: str
    display_name: str
    campaign_id: str
    last_seen: float
    connected: bool = True
    status: str = "online"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Subscription(BaseModel):
    client_id: str
    event_types: set[str] = Field(default_factory=set)
    actor_ids: set[str] = Field(default_factory=set)

    def accepts(self, event: dict[str, Any]) -> bool:
        event_type = str(event.get("type", ""))
        if self.event_types and event_type not in self.event_types:
            return False
        if self.actor_ids:
            actor_id = event.get("actor_id")
            target_id = event.get("target_id")
            if actor_id not in self.actor_ids and target_id not in self.actor_ids:
                return False
        return True


class TokenBucket:
    def __init__(
        self,
        *,
        capacity: float = 20.0,
        refill_per_second: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.capacity = max(1.0, capacity)
        self.refill_per_second = max(0.001, refill_per_second)
        self.clock = clock
        self.tokens = self.capacity
        self.updated_at = self.clock()

    def allow(self, cost: float = 1.0) -> bool:
        now = self.clock()
        elapsed = max(0.0, now - self.updated_at)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now
        if cost > self.tokens:
            return False
        self.tokens -= cost
        return True


class BackpressureBuffer:
    """Bounded server envelope queue with state-update coalescing."""

    def __init__(self, max_items: int = 256) -> None:
        self.max_items = max(1, max_items)
        self.items: deque[tuple[ServerEnvelope, bool]] = deque()
        self.sequence = 0
        self.dropped = 0

    def push(self, kind: str, payload: dict[str, Any], *, critical: bool = False) -> ServerEnvelope:
        self.sequence += 1
        envelope = ServerEnvelope(sequence=self.sequence, kind=kind, payload=payload)
        if kind == "state":
            self.items = deque((item, flag) for item, flag in self.items if item.kind != "state")
        while len(self.items) >= self.max_items:
            index = next((i for i, (_, flag) in enumerate(self.items) if not flag), None)
            if index is None:
                self.items.popleft()
            else:
                self.items.rotate(-index)
                self.items.popleft()
                self.items.rotate(index)
            self.dropped += 1
        self.items.append((envelope, critical))
        return envelope

    def pop(self) -> ServerEnvelope | None:
        if not self.items:
            return None
        return self.items.popleft()[0]

    def drain(self, limit: int = 100) -> list[ServerEnvelope]:
        output: list[ServerEnvelope] = []
        while self.items and len(output) < limit:
            output.append(self.items.popleft()[0])
        return output


@dataclass(slots=True)
class ClientReliabilityState:
    next_client_sequence: int = 1
    receipts: dict[int, ReliableAck] = field(default_factory=dict)
    fingerprints: dict[int, str] = field(default_factory=dict)
    buffer: BackpressureBuffer = field(default_factory=BackpressureBuffer)
    subscription: Subscription | None = None
    limiter: TokenBucket = field(default_factory=TokenBucket)


class ReliableCampaignGateway:
    """Reliable sequence/ack/idempotency boundary around CampaignSession."""

    def __init__(self) -> None:
        self.clients: dict[tuple[str, str], ClientReliabilityState] = {}
        self.server_sequences: dict[str, int] = {}
        self.presence: dict[tuple[str, str], PresenceRecord] = {}

    def state_for(self, campaign_id: str, client_id: str) -> ClientReliabilityState:
        return self.clients.setdefault((campaign_id, client_id), ClientReliabilityState())

    async def dispatch(
        self,
        session: CampaignSession,
        envelope: ReliableCommandEnvelope,
    ) -> ReliableAck:
        state = self.state_for(session.campaign_id, envelope.client_id)
        fingerprint = envelope.fingerprint()
        existing = state.receipts.get(envelope.client_sequence)
        if existing is not None:
            if state.fingerprints[envelope.client_sequence] != fingerprint:
                raise SequenceGapError("client sequence was reused for a different command")
            return existing.model_copy(update={"duplicate": True})
        if envelope.client_sequence != state.next_client_sequence:
            raise SequenceGapError(
                f"expected client sequence {state.next_client_sequence}, got {envelope.client_sequence}"
            )
        if not state.limiter.allow():
            raise RateLimitError("command rate limit exceeded")
        parsed = parse_command(envelope.command)
        result = await session.dispatch(envelope.client_id, parsed)
        if envelope.narrate:
            result.narration = await session.engine.gm.narrate(session.engine.state, result.events)
        server_sequence = self.server_sequences.get(session.campaign_id, 0) + 1
        self.server_sequences[session.campaign_id] = server_sequence
        ack = ReliableAck(
            request_id=envelope.request_id,
            client_id=envelope.client_id,
            client_sequence=envelope.client_sequence,
            server_sequence=server_sequence,
            engine_version=result.version,
            simulation_time=result.simulation_time,
            command_fingerprint=fingerprint,
            event_sequences=[event.sequence for event in result.events],
            narration=result.narration,
        )
        state.receipts[envelope.client_sequence] = ack
        state.fingerprints[envelope.client_sequence] = fingerprint
        state.next_client_sequence += 1
        # Keep a bounded retry ledger.
        for sequence in sorted(state.receipts)[:-256]:
            state.receipts.pop(sequence, None)
            state.fingerprints.pop(sequence, None)
        return ack

    def heartbeat(
        self,
        session: CampaignSession,
        client_id: str,
        *,
        now: float | None = None,
        status: str = "online",
        metadata: dict[str, Any] | None = None,
    ) -> PresenceRecord:
        identity = session.require_client(client_id)
        record = PresenceRecord(
            client_id=client_id,
            user_id=identity.user_id,
            display_name=identity.display_name,
            campaign_id=session.campaign_id,
            last_seen=time.monotonic() if now is None else now,
            connected=True,
            status=status,
            metadata=metadata or {},
        )
        self.presence[(session.campaign_id, client_id)] = record
        return record

    def leave(self, campaign_id: str, client_id: str, *, now: float | None = None) -> None:
        record = self.presence.get((campaign_id, client_id))
        if record is not None:
            record.connected = False
            record.last_seen = time.monotonic() if now is None else now

    def list_presence(self, campaign_id: str, *, now: float | None = None, stale_after: float = 30.0) -> list[PresenceRecord]:
        current = time.monotonic() if now is None else now
        values: list[PresenceRecord] = []
        for (stored_campaign, _), record in self.presence.items():
            if stored_campaign != campaign_id:
                continue
            value = record.model_copy(deep=True)
            if current - value.last_seen > stale_after:
                value.connected = False
                value.status = "stale"
            values.append(value)
        return sorted(values, key=lambda value: (not value.connected, value.display_name, value.client_id))

    def subscribe(self, campaign_id: str, subscription: Subscription) -> None:
        self.state_for(campaign_id, subscription.client_id).subscription = subscription

    def fanout_event(self, campaign_id: str, event: dict[str, Any]) -> None:
        for (stored_campaign, _), state in self.clients.items():
            if stored_campaign != campaign_id:
                continue
            if state.subscription is not None and not state.subscription.accepts(event):
                continue
            state.buffer.push("event", event, critical=True)
