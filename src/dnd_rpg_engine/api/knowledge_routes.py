from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect

from dnd_rpg_engine.core.commands import parse_command
from dnd_rpg_engine.core.world_engine import WorldPlatformEngine
from dnd_rpg_engine.multiplayer.protocol import ClientRole


def install_knowledge_scoped_routes(app: FastAPI) -> None:
    """Replace omniscient legacy read streams for the world-platform profile."""

    protected_paths = {
        "/api/v1/campaigns/{campaign_id}",
        "/api/v1/campaigns/{campaign_id}/events",
        "/api/v1/campaigns/{campaign_id}/ws",
    }
    retained = []
    for route in app.router.routes:
        path = getattr(route, "path", None)
        if path not in protected_paths:
            retained.append(route)
            continue
        methods = getattr(route, "methods", None)
        if path == "/api/v1/campaigns/{campaign_id}" and methods and "GET" not in methods:
            retained.append(route)
        elif path == "/api/v1/campaigns/{campaign_id}/events" and methods and "GET" not in methods:
            retained.append(route)
        # The WebSocket route has no HTTP methods and is replaced wholesale.
    app.router.routes[:] = retained

    async def engine_for(campaign_id: str) -> WorldPlatformEngine:
        engine = await app.state.rpg.get_engine(campaign_id)
        if not isinstance(engine, WorldPlatformEngine):
            raise HTTPException(status_code=409, detail="knowledge-scoped routes require WorldPlatformEngine")
        return engine

    def identity_for(campaign_id: str, client_id: str | None):
        return app.state.rpg.require_client(campaign_id, client_id)

    def visible_ids(engine: WorldPlatformEngine, identity: Any) -> set[str]:
        ids = set(identity.actor_ids)
        for actor_id in identity.actor_ids:
            actor = engine.state.entities.get(actor_id)
            if actor is not None:
                ids.update(engine.knowledge.knowledge_for(actor).known_entity_ids)
        return ids

    def scoped_payload(engine: WorldPlatformEngine, identity: Any) -> dict[str, Any]:
        if identity.role is ClientRole.OWNER:
            return {"knowledge_scoped": False, **engine.state_payload()}
        actor_views = []
        entities: dict[str, Any] = {}
        facts: dict[str, Any] = {}
        for actor_id in sorted(identity.actor_ids):
            actor = engine.state.entities.get(actor_id)
            if actor is None:
                continue
            view = engine.knowledge_view(actor_id)
            actor_views.append(actor_id)
            entities.update(view.entities)
            facts.update({key: fact.model_dump(mode="json") for key, fact in view.facts.items()})
        return {
            "knowledge_scoped": True,
            "campaign_id": engine.state.id,
            "name": engine.state.name,
            "simulation_time": engine.state.simulation_time,
            "active_map_id": engine.state.active_map_id,
            "actor_ids": actor_views,
            "entities": {key: entities[key] for key in sorted(entities)},
            "facts": {key: facts[key] for key in sorted(facts)},
        }

    def event_visible(engine: WorldPlatformEngine, identity: Any, event: Any) -> bool:
        if identity.role is ClientRole.OWNER:
            return True
        allowed = visible_ids(engine, identity)
        if event.actor_id in allowed or event.target_id in allowed:
            return True
        payload = event.payload if isinstance(event.payload, dict) else {}
        return bool(payload.get("public") is True)

    @app.get("/api/v1/campaigns/{campaign_id}", tags=["knowledge-authority"])
    async def get_campaign_scoped(
        campaign_id: str,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await engine_for(campaign_id)
        identity = identity_for(campaign_id, client_id)
        return scoped_payload(engine, identity)

    @app.get("/api/v1/campaigns/{campaign_id}/events", tags=["knowledge-authority"])
    async def events_scoped(
        campaign_id: str,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=250, ge=1, le=5000),
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> list[dict[str, Any]]:
        engine = await engine_for(campaign_id)
        identity = identity_for(campaign_id, client_id)
        rows = await app.state.rpg.store.list_events(campaign_id, after_sequence=after, limit=limit)
        return [event.model_dump(mode="json") for event in rows if event_visible(engine, identity, event)]

    @app.websocket("/api/v1/campaigns/{campaign_id}/ws")
    async def websocket_campaign_scoped(websocket: WebSocket, campaign_id: str) -> None:
        await websocket.accept()
        client_id = websocket.query_params.get("client_id")
        try:
            engine = await engine_for(campaign_id)
            identity = identity_for(campaign_id, client_id)
        except HTTPException as exc:
            await websocket.send_json({"kind": "error", "detail": str(exc.detail)})
            await websocket.close(code=4401 if exc.status_code == 401 else 4404)
            return

        await websocket.send_json({"kind": "state", "state": scoped_payload(engine, identity)})
        stream = await engine.events.subscribe()

        async def sender() -> None:
            while True:
                event = await stream.get()
                if event_visible(engine, identity, event):
                    await websocket.send_json({"kind": "event", "event": event.model_dump(mode="json")})
                else:
                    # Hidden events can still change what an owned actor knows
                    # later, so expose only a fresh redacted state marker.
                    await websocket.send_json(
                        {
                            "kind": "knowledge_checkpoint",
                            "simulation_time": engine.state.simulation_time,
                        }
                    )

        sender_task = asyncio.create_task(sender(), name=f"rpg-knowledge-ws:{campaign_id}:{client_id}")
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("kind") == "command":
                    try:
                        parsed = parse_command(data["command"])
                        result = await app.state.rpg.sessions.require(campaign_id).dispatch(client_id, parsed)
                        if data.get("narrate"):
                            result.narration = await engine.gm.narrate(engine.state, result.events)
                        await websocket.send_json(
                            {
                                "kind": "ack",
                                "request_id": data.get("request_id"),
                                "version": result.version,
                                "narration": result.narration,
                            }
                        )
                    except Exception as exc:
                        await websocket.send_json(
                            {"kind": "error", "request_id": data.get("request_id"), "detail": str(exc)}
                        )
                elif data.get("kind") == "state":
                    await websocket.send_json({"kind": "state", "state": scoped_payload(engine, identity)})
        except WebSocketDisconnect:
            pass
        finally:
            sender_task.cancel()
            with suppress(asyncio.CancelledError):
                await sender_task
            await engine.events.unsubscribe(stream)
