# src/dnd_rpg_engine/hosting/reconnect.py
from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any, Protocol

from pydantic import BaseModel, Field

from dnd_rpg_engine.multiplayer.protocol import ClientIdentity
from dnd_rpg_engine.multiplayer.sessions import CampaignSession


class JsonStore(Protocol):
    async def put_json(self, namespace: str, key: str, value: Any) -> None: ...
    async def get_json(self, namespace: str, key: str) -> Any | None: ...


class ResumeTicket(BaseModel):
    token: str
    campaign_id: str
    client: ClientIdentity
    last_event_sequence: int = Field(default=0, ge=0)
    expires_at: float


class ResumeResult(BaseModel):
    client: ClientIdentity
    replay_after_sequence: int
    resumed: bool = True


class ReconnectManager:
    """Issues opaque reconnect tickets while storing only token hashes."""

    namespace = "resume_ticket"

    def __init__(self, store: JsonStore, *, default_ttl_seconds: float = 3600.0) -> None:
        if default_ttl_seconds <= 0:
            raise ValueError("resume ticket TTL must be positive")
        self.store = store
        self.default_ttl_seconds = default_ttl_seconds

    async def issue(
        self,
        campaign_id: str,
        client: ClientIdentity,
        *,
        last_event_sequence: int = 0,
        ttl_seconds: float | None = None,
    ) -> ResumeTicket:
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ValueError("resume ticket TTL must be positive")
        raw_token = secrets.token_urlsafe(32)
        expires_at = time.time() + ttl
        ticket = ResumeTicket(
            token=raw_token,
            campaign_id=campaign_id,
            client=client.model_copy(deep=True),
            last_event_sequence=last_event_sequence,
            expires_at=expires_at,
        )
        await self.store.put_json(
            self.namespace,
            self._token_key(raw_token),
            {
                "campaign_id": campaign_id,
                "client": client.model_dump(mode="json"),
                "last_event_sequence": last_event_sequence,
                "expires_at": expires_at,
                "revoked": False,
            },
        )
        return ticket

    async def resume(
        self,
        token: str,
        session: CampaignSession,
        *,
        observed_event_sequence: int | None = None,
        rotate: bool = True,
    ) -> tuple[ResumeResult, ResumeTicket | None]:
        key = self._token_key(token)
        raw = await self.store.get_json(self.namespace, key)
        if not isinstance(raw, dict) or raw.get("revoked"):
            raise PermissionError("resume ticket is invalid")
        if float(raw.get("expires_at", 0)) <= time.time():
            raise PermissionError("resume ticket has expired")
        if str(raw.get("campaign_id")) != session.campaign_id:
            raise PermissionError("resume ticket belongs to a different campaign")

        client = ClientIdentity.model_validate(raw["client"])
        session.join(client)
        replay_after = int(raw.get("last_event_sequence", 0))
        if observed_event_sequence is not None:
            replay_after = max(replay_after, observed_event_sequence)
        result = ResumeResult(client=client, replay_after_sequence=replay_after)
        rotated: ResumeTicket | None = None
        if rotate:
            await self.revoke(token)
            rotated = await self.issue(
                session.campaign_id,
                client,
                last_event_sequence=replay_after,
            )
        return result, rotated

    async def checkpoint(self, token: str, last_event_sequence: int) -> None:
        if last_event_sequence < 0:
            raise ValueError("event sequence cannot be negative")
        key = self._token_key(token)
        raw = await self.store.get_json(self.namespace, key)
        if not isinstance(raw, dict) or raw.get("revoked"):
            raise PermissionError("resume ticket is invalid")
        raw["last_event_sequence"] = max(int(raw.get("last_event_sequence", 0)), last_event_sequence)
        await self.store.put_json(self.namespace, key, raw)

    async def revoke(self, token: str) -> None:
        key = self._token_key(token)
        raw = await self.store.get_json(self.namespace, key)
        if isinstance(raw, dict):
            raw["revoked"] = True
            raw["revoked_at"] = time.time()
            await self.store.put_json(self.namespace, key, raw)

    @staticmethod
    def _token_key(token: str) -> str:
        if not token:
            raise PermissionError("resume ticket is invalid")
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
