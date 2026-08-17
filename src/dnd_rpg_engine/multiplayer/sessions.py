from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

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


class CampaignSession:
    """Serializes authoritative commands per campaign while allowing concurrent clients.

    ``manage_resolver`` and ``control_resolver`` are optional authenticated
    policy hooks. They let production identity/RBAC grant GM/admin authority
    without forging the transport-level OWNER role. When unset, legacy behavior
    is unchanged.
    """

    def __init__(self, campaign_id: str, engine: GameEngine, owner_id: str) -> None:
        self.campaign_id = campaign_id
        self.engine = engine
        self.owner_id = owner_id
        self.clients: dict[str, ClientIdentity] = {}
        self.parties: dict[str, Party] = {}
        self.manage_resolver: Callable[[ClientIdentity], bool] | None = None
        self.control_resolver: Callable[[ClientIdentity, str], bool] | None = None
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

    def require_client(self, client_id: str) -> ClientIdentity:
        try:
            return self.clients[client_id]
        except KeyError as exc:
            raise PermissionError("unknown campaign client") from exc

    def require_owner(self, client_id: str) -> ClientIdentity:
        identity = self.require_client(client_id)
        if identity.role is ClientRole.OWNER:
            return identity
        if self.manage_resolver is not None and self.manage_resolver(identity):
            return identity
        raise PermissionError("campaign management permission required")

    def leave(self, client_id: str) -> None:
        self.clients.pop(client_id, None)

    def can_control(self, client_id: str, actor_id: str) -> bool:
        identity = self.clients.get(client_id)
        if identity is None or identity.role is ClientRole.SPECTATOR:
            return False
        if identity.role is ClientRole.OWNER or actor_id in identity.actor_ids:
            return True
        return bool(self.control_resolver and self.control_resolver(identity, actor_id))

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
