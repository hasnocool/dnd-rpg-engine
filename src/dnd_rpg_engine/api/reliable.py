from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from dnd_rpg_engine.api.security_helpers import campaign_resource, identity_service, require_principal
from dnd_rpg_engine.multiplayer.reliable import (
    RateLimitError,
    ReliableCommandEnvelope,
    SequenceGapError,
    Subscription,
)
from dnd_rpg_engine.security.models import Permission
from dnd_rpg_engine.security.tokens import TokenError

router = APIRouter(prefix="/api/v1/reliable", tags=["reliable-multiplayer"])


class PresenceRequest(BaseModel):
    client_id: str
    status: str = Field(default="online", max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubscriptionRequest(BaseModel):
    client_id: str
    event_types: set[str] = Field(default_factory=set)
    actor_ids: set[str] = Field(default_factory=set)


def _require_bound_client(request: Request, campaign_id: str, client_id: str):
    principal = require_principal(request)
    try:
        client = request.app.state.rpg.sessions.require(campaign_id).require_client(client_id)
    except (KeyError, PermissionError) as exc:
        raise HTTPException(status_code=401, detail="unknown campaign client") from exc
    if client.user_id != principal.user_id or (client.session_id and client.session_id != principal.session_id):
        raise HTTPException(status_code=403, detail="campaign client is bound to a different authenticated session")
    return principal, client


@router.post("/campaigns/{campaign_id}/commands")
async def reliable_command(
    request: Request,
    campaign_id: str,
    envelope: ReliableCommandEnvelope,
) -> dict[str, Any]:
    _require_bound_client(request, campaign_id, envelope.client_id)
    session = request.app.state.rpg.sessions.require(campaign_id)
    try:
        ack = await request.app.state.reliable.dispatch(session, envelope)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (SequenceGapError, ValueError, KeyError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ack.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/presence")
async def heartbeat_presence(
    request: Request,
    campaign_id: str,
    payload: PresenceRequest,
) -> dict[str, Any]:
    _require_bound_client(request, campaign_id, payload.client_id)
    session = request.app.state.rpg.sessions.require(campaign_id)
    record = request.app.state.reliable.heartbeat(
        session,
        payload.client_id,
        status=payload.status,
        metadata=payload.metadata,
    )
    return record.model_dump(mode="json")


@router.get("/campaigns/{campaign_id}/presence")
async def list_presence(request: Request, campaign_id: str) -> list[dict[str, Any]]:
    principal = require_principal(request)
    resource = await campaign_resource(request, campaign_id)
    try:
        identity_service(request).authorize(principal, Permission.CAMPAIGN_READ, resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [value.model_dump(mode="json") for value in request.app.state.reliable.list_presence(campaign_id)]


@router.post("/campaigns/{campaign_id}/subscriptions")
async def subscribe_events(
    request: Request,
    campaign_id: str,
    payload: SubscriptionRequest,
) -> dict[str, Any]:
    _require_bound_client(request, campaign_id, payload.client_id)
    subscription = Subscription(
        client_id=payload.client_id,
        event_types=payload.event_types,
        actor_ids=payload.actor_ids,
    )
    request.app.state.reliable.subscribe(campaign_id, subscription)
    return subscription.model_dump(mode="json")


@router.websocket("/campaigns/{campaign_id}/ws")
async def reliable_websocket(websocket: WebSocket, campaign_id: str) -> None:
    app = websocket.app
    token = websocket.query_params.get("access_token")
    if not token:
        authorization = websocket.headers.get("authorization", "")
        scheme, _, candidate = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = candidate.strip()
    try:
        if not token:
            raise TokenError("authenticated session required")
        principal = app.state.identity.authenticate(token)
        session = app.state.rpg.sessions.require(campaign_id)
        client_id = websocket.query_params.get("client_id")
        if not client_id:
            raise TokenError("client_id is required")
        client = session.require_client(client_id)
        if client.user_id != principal.user_id or (client.session_id and client.session_id != principal.session_id):
            raise TokenError("campaign client belongs to a different authenticated session")
        resource = app.state.identity.resource_for_scope(__import__("dnd_rpg_engine.security.models", fromlist=["ScopeType"]).ScopeType.CAMPAIGN, campaign_id)
        app.state.identity.authorize(principal, Permission.CAMPAIGN_READ, resource)
        engine = await app.state.rpg.get_engine(campaign_id)
    except (TokenError, PermissionError, KeyError) as exc:
        await websocket.close(code=4401, reason=str(exc))
        return

    await websocket.accept()
    app.state.reliable.heartbeat(session, client_id)
    stream = await engine.events.subscribe()
    outgoing: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)

    async def send_loop() -> None:
        while True:
            await websocket.send_json(await outgoing.get())

    async def event_loop() -> None:
        while True:
            event = await stream.get()
            payload = event.model_dump(mode="json")
            reliability = app.state.reliable.state_for(campaign_id, client_id)
            if reliability.subscription and not reliability.subscription.accepts(payload):
                continue
            await outgoing.put({"kind": "event", "event": payload})

    async def receive_loop() -> None:
        while True:
            data = await websocket.receive_json()
            kind = data.get("kind")
            if kind == "command":
                try:
                    envelope = ReliableCommandEnvelope(
                        request_id=data.get("request_id") or data.get("id"),
                        client_id=client_id,
                        client_sequence=int(data["client_sequence"]),
                        command=dict(data["command"]),
                        narrate=bool(data.get("narrate", False)),
                    )
                    ack = await app.state.reliable.dispatch(session, envelope)
                    await outgoing.put({"kind": "ack", **ack.model_dump(mode="json")})
                except RateLimitError as exc:
                    await outgoing.put({"kind": "error", "status": 429, "detail": str(exc)})
                except (SequenceGapError, PermissionError, ValueError, KeyError, RuntimeError) as exc:
                    await outgoing.put({"kind": "error", "status": 409, "detail": str(exc)})
            elif kind == "heartbeat":
                record = app.state.reliable.heartbeat(session, client_id, status=str(data.get("status", "online")))
                await outgoing.put({"kind": "presence", "presence": record.model_dump(mode="json")})
            elif kind == "subscribe":
                subscription = Subscription(
                    client_id=client_id,
                    event_types=set(data.get("event_types", [])),
                    actor_ids=set(data.get("actor_ids", [])),
                )
                app.state.reliable.subscribe(campaign_id, subscription)
                await outgoing.put({"kind": "subscribed", "subscription": subscription.model_dump(mode="json")})
            elif kind == "state":
                await outgoing.put({"kind": "state", "state": engine.state_payload()})

    tasks = [asyncio.create_task(send_loop()), asyncio.create_task(event_loop()), asyncio.create_task(receive_loop())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            with suppress(WebSocketDisconnect, asyncio.CancelledError):
                task.result()
    finally:
        for task in tasks:
            task.cancel()
        await engine.events.unsubscribe(stream)
        app.state.reliable.leave(campaign_id, client_id)
