# src/dnd_rpg_engine/multiplayer/sessions.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from dnd_rpg_engine.core.commands import GameCommand
from dnd_rpg_engine.multiplayer.protocol import ClientIdentity, ClientRole

if TYPE_CHECKING:
    from dnd_rpg_engine.core.engine import GameEngine


@dataclass(slots=True)
class Party:
    id: str
    name: str
    actor_ids: set[str] = field(default_factory=set)
    member_user_ids: set[str] = field(default_factory=set)


@dataclass(slots=True)
class ConnectionState:
    client_id: str
    user_id: str
    connected: bool = True
    last_seen_sequence: int = 0
    connected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    disconnected_at: str | None = None


class CampaignSession:
    """Serializes authoritative commands per campaign while allowing concurrent clients."""

    def __init__(self, campaign_id: str, engine: GameEngine, owner_id: str) -> None:
        self.campaign_id = campaign_id
        self.engine = engine
        self.owner_id = owner_id
        self.clients: dict[str, ClientIdentity] = {}
        self.parties: dict[str, Party] = {}
        self.connections: dict[str, ConnectionState] = {}
        self.lobby_open: bool = True
        self._command_lock = asyncio.Lock()

    def join(self, identity: ClientIdentity) -> None:
        # The session layer is an authorization boundary, not an identity provider.
        # It never trusts a caller-provided OWNER role or arbitrary actor IDs.
        if identity.user_id == self.owner_id:
            identity.role = ClientRole.OWNER
            identity.actor_ids.clear()
        else:
            if identity.role is ClientRole.OWNER:
                identity.role = ClientRole.PLAYER
            owned_actor_ids = {
                entity.id
                for entity in self.engine.state.entities.values()
                if entity.owner_id == identity.user_id
            }
            identity.actor_ids.intersection_update(owned_actor_ids)
            if identity.role is ClientRole.PLAYER and not identity.actor_ids:
                identity.actor_ids = owned_actor_ids
        self.clients[identity.client_id] = identity
        self.connections[identity.client_id] = ConnectionState(client_id=identity.client_id, user_id=identity.user_id)

    def require_client(self, client_id: str) -> ClientIdentity:
        try:
            return self.clients[client_id]
        except KeyError as exc:
            raise PermissionError("unknown campaign client") from exc

    def require_owner(self, client_id: str) -> ClientIdentity:
        identity = self.require_client(client_id)
        if identity.role is not ClientRole.OWNER:
            raise PermissionError("campaign owner permission required")
        return identity

    def leave(self, client_id: str) -> None:
        connection = self.connections.get(client_id)
        if connection is not None:
            connection.connected = False
            connection.disconnected_at = datetime.now(timezone.utc).isoformat()

    def reconnect(self, client_id: str, user_id: str) -> ClientIdentity:
        identity = self.require_client(client_id)
        if identity.user_id != user_id:
            raise PermissionError("reconnect user does not match client identity")
        connection = self.connections.setdefault(client_id, ConnectionState(client_id=client_id, user_id=user_id))
        connection.connected = True
        connection.disconnected_at = None
        return identity

    async def replay(self, client_id: str, *, after_sequence: int | None = None, limit: int = 500):
        identity = self.require_client(client_id)
        connection = self.connections.setdefault(client_id, ConnectionState(client_id=client_id, user_id=identity.user_id))
        cursor = connection.last_seen_sequence if after_sequence is None else after_sequence
        if self.engine.store is None:
            events = [event for event in self.engine._recent_events if event.sequence > cursor][:limit]
        else:
            events = await self.engine.store.list_events(self.campaign_id, after_sequence=cursor, limit=limit)
        if events:
            connection.last_seen_sequence = events[-1].sequence
        return events

    def lobby_snapshot(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "open": self.lobby_open,
            "clients": [identity.model_dump(mode="json") for identity in self.clients.values()],
            "connections": {key: vars(value) if hasattr(value, "__dict__") else {
                "client_id": value.client_id, "user_id": value.user_id, "connected": value.connected,
                "last_seen_sequence": value.last_seen_sequence, "connected_at": value.connected_at,
                "disconnected_at": value.disconnected_at,
            } for key, value in self.connections.items()},
            "parties": {party_id: {"id": party.id, "name": party.name, "actor_ids": sorted(party.actor_ids), "member_user_ids": sorted(party.member_user_ids)} for party_id, party in self.parties.items()},
        }

    def can_control(self, client_id: str, actor_id: str) -> bool:
        identity = self.clients.get(client_id)
        if identity is None or identity.role is ClientRole.SPECTATOR:
            return False
        return identity.role is ClientRole.OWNER or actor_id in identity.actor_ids

    async def dispatch(self, client_id: str, command: GameCommand):
        if not self.can_control(client_id, command.actor_id):
            raise PermissionError("client does not control this actor")
        async with self._command_lock:
            return await self.engine.dispatch(command)

    def create_party(self, party_id: str, name: str) -> Party:
        if party_id in self.parties:
            raise ValueError("party already exists")
        party = Party(id=party_id, name=name)
        self.parties[party_id] = party
        return party

    def add_to_party(self, party_id: str, *, user_id: str | None = None, actor_id: str | None = None) -> None:
        party = self.parties[party_id]
        if user_id:
            party.member_user_ids.add(user_id)
        if actor_id:
            party.actor_ids.add(actor_id)


class SessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, CampaignSession] = {}
        self._lock = asyncio.Lock()

    async def host(self, campaign_id: str, engine: GameEngine, owner_id: str) -> CampaignSession:
        async with self._lock:
            if campaign_id in self.sessions:
                raise ValueError("campaign is already hosted")
            session = CampaignSession(campaign_id, engine, owner_id)
            self.sessions[campaign_id] = session
            return session

    def require(self, campaign_id: str) -> CampaignSession:
        try:
            return self.sessions[campaign_id]
        except KeyError as exc:
            raise KeyError(f"campaign is not hosted: {campaign_id}") from exc

    async def unhost(self, campaign_id: str) -> None:
        async with self._lock:
            self.sessions.pop(campaign_id, None)
