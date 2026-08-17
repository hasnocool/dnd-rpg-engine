from __future__ import annotations

from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field


class Transport(Protocol):
    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any: ...

    async def close(self) -> None: ...


class HTTPXTransport:
    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)
        self.access_token: str | None = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        merged = dict(headers or {})
        if self.access_token:
            merged.setdefault("Authorization", f"Bearer {self.access_token}")
        response = await self.client.request(method, path, json=json, headers=merged)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()


class RPGClientConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8000"
    timeout: float = Field(default=30.0, gt=0)


class CampaignHandle(BaseModel):
    campaign_id: str
    client_id: str
    client_sequence: int = 1
    last_event_sequence: int = 0
    state: dict[str, Any] = Field(default_factory=dict)


class RPGClient:
    """Async Python SDK for authenticated/reliable v2.5 platform clients."""

    def __init__(self, config: RPGClientConfig | None = None, *, transport: Transport | None = None) -> None:
        self.config = config or RPGClientConfig()
        self.transport = transport or HTTPXTransport(self.config.base_url, timeout=self.config.timeout)
        self.access_token: str | None = None
        self.user: dict[str, Any] | None = None
        self.campaigns: dict[str, CampaignHandle] = {}

    async def bootstrap(
        self,
        *,
        user_id: str,
        display_name: str,
        bootstrap_key: str,
        ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        payload = await self.transport.request(
            "POST",
            "/api/v1/auth/bootstrap",
            json={"user_id": user_id, "display_name": display_name, "ttl_seconds": ttl_seconds},
            headers={"X-RPG-Bootstrap-Key": bootstrap_key},
        )
        self.access_token = str(payload["access_token"])
        if isinstance(self.transport, HTTPXTransport):
            self.transport.access_token = self.access_token
        self.user = dict(payload["user"])
        return payload

    async def create_campaign(self, name: str, *, seed: int = 1, time_mode: str = "hybrid") -> CampaignHandle:
        payload = await self.transport.request(
            "POST",
            "/api/v1/secure/campaigns",
            json={"name": name, "seed": seed, "time_mode": time_mode},
            headers=self._auth_headers(),
        )
        handle = CampaignHandle(
            campaign_id=str(payload["campaign_id"]),
            client_id=str(payload["owner_client_id"]),
            state=dict(payload.get("state") or payload),
        )
        self.campaigns[handle.campaign_id] = handle
        return handle

    async def join_campaign(self, campaign_id: str) -> CampaignHandle:
        payload = await self.transport.request(
            "POST",
            f"/api/v1/secure/campaigns/{campaign_id}/join",
            json={},
            headers=self._auth_headers(),
        )
        handle = CampaignHandle(campaign_id=campaign_id, client_id=str(payload["client_id"]))
        self.campaigns[campaign_id] = handle
        return handle

    async def command(self, campaign_id: str, command: dict[str, Any], *, narrate: bool = False) -> dict[str, Any]:
        handle = self.campaigns[campaign_id]
        payload = await self.transport.request(
            "POST",
            f"/api/v1/reliable/campaigns/{campaign_id}/commands",
            json={
                "client_id": handle.client_id,
                "client_sequence": handle.client_sequence,
                "command": command,
                "narrate": narrate,
            },
            headers=self._auth_headers(),
        )
        if not payload.get("duplicate", False):
            handle.client_sequence += 1
        return payload

    async def events(self, campaign_id: str, *, limit: int = 250) -> list[dict[str, Any]]:
        handle = self.campaigns[campaign_id]
        payload = await self.transport.request(
            "GET",
            f"/api/v1/campaigns/{campaign_id}/events?after={handle.last_event_sequence}&limit={limit}",
            headers=self._auth_headers(),
        )
        events = list(payload)
        for event in events:
            handle.last_event_sequence = max(handle.last_event_sequence, int(event.get("sequence", 0)))
            self.apply_event(handle, event)
        return events

    def apply_event(self, handle: CampaignHandle, event: dict[str, Any]) -> None:
        handle.state.setdefault("events", []).append(event)
        handle.state["last_event_sequence"] = int(event.get("sequence", handle.last_event_sequence))

    async def close(self) -> None:
        await self.transport.close()

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
