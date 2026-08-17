# src/dnd_rpg_engine/api/app.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dnd_rpg_engine.api.schemas import (
    AwardXPRequest, BudgetedEncounterRequest, CommandRequest, ConfigurePartyRequest,
    CreateCampaignRequest, CreateEntityRequest, EncounterRequest, InstantiatePackRequest,
    JoinRequest, LevelUpRequest, ReactionWindowRequest, TickRequest, TravelRequest, UpdateTimingRequest,
    CharacterBuildRequest, CreatePartyRequest, ImportCampaignRequest, PlayableCampaignRequest, ReconnectRequest,
)
from dnd_rpg_engine.core.commands import parse_command
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.core.persistence import SQLiteStore
from dnd_rpg_engine.campaign.package import CampaignPackage
from dnd_rpg_engine.characters.package import CharacterPackage
from dnd_rpg_engine.creator.studio import CreatorProject, CreatorStudio
from dnd_rpg_engine.rulesets.srd_5_2_1 import SRD_5_2_1_RULESET, build_srd_5_2_1_pack
from dnd_rpg_engine.creator.content import ContentPack, ContentValidator
from dnd_rpg_engine.creator.loader import install_content_pack
from dnd_rpg_engine.creator.marketplace import MarketplaceRegistry
from dnd_rpg_engine.multiplayer.protocol import ClientIdentity, ClientRole
from dnd_rpg_engine.multiplayer.sessions import SessionManager
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog_store import SRDCatalogStore
from dnd_rpg_engine.rulesets.srd_5_2_1.runtime import SRDRuntimeCatalog
from dnd_rpg_engine.rulesets.srd_5_2_1.toolbox import encounter_budget


class ApplicationState:
    def __init__(self, database_path: str, srd_catalog_path: str | None = None) -> None:
        self.store = SQLiteStore(database_path)
        self.srd_runtime = SRDRuntimeCatalog(srd_catalog_path) if srd_catalog_path else None
        self.srd_catalog = self.srd_runtime.store if self.srd_runtime is not None else None
        self.engines: dict[str, GameEngine] = {}
        self.sessions = SessionManager()
        self.marketplace = MarketplaceRegistry()
        self.validator = ContentValidator()
        self.creator_studio = CreatorStudio()
        self.realtime_tasks: dict[str, tuple[asyncio.Event, asyncio.Task[None]]] = {}
        self.websocket_clients: dict[str, set[WebSocket]] = {}
        self.broadcast_tasks: dict[str, asyncio.Task[None]] = {}

    async def get_engine(self, campaign_id: str) -> GameEngine:
        engine = self.engines.get(campaign_id)
        if engine is not None:
            return engine
        try:
            engine = await GameEngine.load(campaign_id, store=self.store)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc
        self.engines[campaign_id] = engine
        engine.characters.bind_catalog(self.srd_runtime)
        engine.campaign_runner.bind_catalog(self.srd_runtime)
        if campaign_id not in self.sessions.sessions:
            await self.sessions.host(campaign_id, engine, owner_id=str(engine.state.metadata.get("owner_id", "local")))
        await self.ensure_realtime(campaign_id, engine)
        await self.ensure_broadcast(campaign_id, engine)
        return engine

    def require_client(self, campaign_id: str, client_id: str | None):
        if not client_id:
            raise HTTPException(status_code=401, detail="campaign client id required")
        try:
            return self.sessions.require(campaign_id).require_client(client_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=401, detail="unknown campaign client") from exc

    def require_owner(self, campaign_id: str, client_id: str | None):
        if not client_id:
            raise HTTPException(status_code=401, detail="campaign client id required")
        try:
            return self.sessions.require(campaign_id).require_owner(client_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="campaign session not found") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    async def ensure_realtime(self, campaign_id: str, engine: GameEngine) -> None:
        if campaign_id in self.realtime_tasks or not engine.config.realtime_enabled:
            return
        stop = asyncio.Event()
        task = asyncio.create_task(engine.run_realtime(stop), name=f"rpg-clock:{campaign_id}")
        self.realtime_tasks[campaign_id] = (stop, task)

    async def ensure_broadcast(self, campaign_id: str, engine: GameEngine) -> None:
        if campaign_id in self.broadcast_tasks:
            return
        stream = await engine.events.subscribe()

        async def pump() -> None:
            try:
                while True:
                    event = await stream.get()
                    payload = {"kind": "event", "event": event.model_dump(mode="json")}
                    stale: list[WebSocket] = []
                    for ws in tuple(self.websocket_clients.get(campaign_id, ())):
                        try:
                            await ws.send_json(payload)
                        except Exception:
                            stale.append(ws)
                    for ws in stale:
                        self.websocket_clients.get(campaign_id, set()).discard(ws)
            except asyncio.CancelledError:
                raise
            finally:
                await engine.events.unsubscribe(stream)

        self.broadcast_tasks[campaign_id] = asyncio.create_task(pump(), name=f"rpg-broadcast:{campaign_id}")

    async def shutdown(self) -> None:
        for stop, _ in self.realtime_tasks.values():
            stop.set()
        for _, task in self.realtime_tasks.values():
            task.cancel()
        for task in self.broadcast_tasks.values():
            task.cancel()
        for _, task in self.realtime_tasks.values():
            with suppress(asyncio.CancelledError):
                await task
        for task in self.broadcast_tasks.values():
            with suppress(asyncio.CancelledError):
                await task


def create_app(database_path: str = "rpg_engine.sqlite3", srd_catalog_path: str | None = None) -> FastAPI:
    state = ApplicationState(database_path, srd_catalog_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await state.store.initialize()
        if state.srd_runtime is not None:
            await state.srd_runtime.initialize()
        stored_packs = await state.store.list_json("marketplace.pack")
        for item_id, raw_pack in stored_packs.items():
            try:
                state.marketplace.publish(ContentPack.model_validate(raw_pack))
            except Exception:
                continue
        app.state.rpg = state
        yield
        await state.shutdown()

    app = FastAPI(
        title="RPG Engine API",
        version="2.0.0",
        description="Authoritative deterministic RPG simulation API with configurable turn/time-driven scheduling.",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "2.0.0"}

    @app.get("/api/v1/srd/catalog")
    async def srd_catalog_info() -> dict[str, Any]:
        if state.srd_catalog is None:
            raise HTTPException(status_code=404, detail="offline SRD catalog is not configured")
        manifest = await state.srd_catalog.manifest()
        return {
            "manifest": None if manifest is None else manifest.model_dump(mode="json"),
            "sections": await state.srd_catalog.sections(),
        }

    @app.get("/api/v1/srd/catalog/{section}")
    async def srd_catalog_search(
        section: str,
        q: str = Query(default="", max_length=100),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[dict[str, Any]]:
        if state.srd_catalog is None:
            raise HTTPException(status_code=404, detail="offline SRD catalog is not configured")
        sections = await state.srd_catalog.sections()
        if section not in sections:
            raise HTTPException(status_code=404, detail="catalog section not found")
        return await state.srd_catalog.search(section, q, limit=limit)

    @app.get("/api/v1/srd/encounter-budget")
    async def srd_encounter_budget(
        levels: str = Query(min_length=1, max_length=120),
        difficulty: str = Query(default="moderate", pattern="^(low|moderate|high)$"),
    ) -> dict[str, Any]:
        try:
            parsed = [int(part.strip()) for part in levels.split(",") if part.strip()]
            budget = encounter_budget(parsed, difficulty)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"levels": parsed, "difficulty": difficulty, "xp_budget": budget}

    @app.post("/api/v1/campaigns")
    async def create_campaign(request: CreateCampaignRequest) -> dict[str, Any]:
        engine = await GameEngine.create(request.name, config=request.config(), store=state.store, seed=request.seed)
        engine.state.metadata["owner_id"] = request.owner_id
        engine.characters.bind_catalog(state.srd_runtime)
        engine.campaign_runner.bind_catalog(state.srd_runtime)
        await engine.save()
        await state.store.put_json("hosted_campaign", engine.state.id, {"owner_id": request.owner_id, "public": False})
        state.engines[engine.state.id] = engine
        session = await state.sessions.host(engine.state.id, engine, request.owner_id)
        owner = ClientIdentity(user_id=request.owner_id, display_name=request.owner_id, role=ClientRole.OWNER)
        session.join(owner)
        await state.ensure_realtime(engine.state.id, engine)
        await state.ensure_broadcast(engine.state.id, engine)
        return {"campaign_id": engine.state.id, "owner_client_id": owner.client_id, **engine.state_payload()}

    @app.get("/api/v1/campaigns")
    async def list_campaigns(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict[str, Any]]:
        return await state.store.list_campaigns(limit)

    @app.get("/api/v1/campaigns/{campaign_id}")
    async def get_campaign(campaign_id: str) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        return engine.state_payload()

    @app.patch("/api/v1/campaigns/{campaign_id}/timing")
    async def update_timing(
        campaign_id: str,
        request: UpdateTimingRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        kwargs: dict[str, Any] = {}
        if "time_mode" in request.model_fields_set:
            kwargs["time_mode"] = request.time_mode
        if "player_decision_timeout_seconds" in request.model_fields_set:
            kwargs["player_decision_timeout_seconds"] = request.player_decision_timeout_seconds
        if "pause_when_player_ready" in request.model_fields_set:
            kwargs["pause_when_player_ready"] = request.pause_when_player_ready
        if "time_scale" in request.model_fields_set:
            kwargs["time_scale"] = request.time_scale
        config = await engine.update_timing(**kwargs)
        await state.ensure_realtime(campaign_id, engine)
        return config.model_dump(mode="json")

    @app.post("/api/v1/campaigns/{campaign_id}/encounters")
    async def start_encounter(
        campaign_id: str,
        request: EncounterRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, object]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            return await engine.start_encounter(request.participant_ids)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete("/api/v1/campaigns/{campaign_id}/encounters/{encounter_id}")
    async def end_encounter(
        campaign_id: str,
        encounter_id: str,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, str]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            await engine.end_encounter(encounter_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="encounter not found") from exc
        return {"status": "ended"}

    @app.post("/api/v1/campaigns/{campaign_id}/characters")
    async def create_character(
        campaign_id: str,
        request: CharacterBuildRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            entity = await engine.characters.build(request, entity_id=str(uuid4()))
            event = await engine.add_entity(entity)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"entity": entity.model_dump(mode="json"), "character": engine.characters.state(entity).model_dump(mode="json"), "event": event.model_dump(mode="json")}

    @app.get("/api/v1/campaigns/{campaign_id}/characters/{actor_id}")
    async def character_sheet(campaign_id: str, actor_id: str) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        try:
            entity = engine.state.require_entity(actor_id)
            character = engine.characters.state(entity)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"entity": entity.model_dump(mode="json"), "character": character.model_dump(mode="json"), "legal_actions": engine.characters.available_actions(entity)}

    @app.get("/api/v1/campaigns/{campaign_id}/characters/{actor_id}/actions")
    async def legal_actions(campaign_id: str, actor_id: str) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        try:
            return engine.characters.available_actions(engine.state.require_entity(actor_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="character not found") from exc

    @app.get("/api/v1/campaigns/{campaign_id}/characters/{actor_id}/export")
    async def export_character(campaign_id: str, actor_id: str) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        try:
            entity = engine.state.require_entity(actor_id)
            package = CharacterPackage.from_entity(entity, engine.characters.state(entity))
            return package.model_dump(mode="json")
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/{campaign_id}/characters/import")
    async def import_character(
        campaign_id: str, payload: dict[str, Any],
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            package = CharacterPackage.model_validate(payload)
            package.verify()
            entity = package.entity.model_copy(deep=True)
            entity.id = str(uuid4())
            engine.characters.save(entity, package.character)
            event = await engine.add_entity(entity)
            return {"entity": entity.model_dump(mode="json"), "character": package.character.model_dump(mode="json"), "event": event.model_dump(mode="json")}
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/{campaign_id}/characters/{actor_id}/level-up")
    async def level_up_character(
        campaign_id: str, actor_id: str, request: LevelUpRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            entity = engine.state.require_entity(actor_id)
            result = await engine.characters.level_up(entity, target_level=request.target_level, reason=request.reason)
            await engine._emit("character.level_gained", actor_id=actor_id, payload={"level": result.level, "reason": request.reason})
            await engine.save()
            return result.model_dump(mode="json")
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/{campaign_id}/characters/{actor_id}/xp")
    async def award_character_xp(
        campaign_id: str, actor_id: str, request: AwardXPRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            entity = engine.state.require_entity(actor_id)
            levels = await engine.characters.award_xp(entity, request.amount)
            await engine._emit("character.xp_awarded", actor_id=actor_id, payload={"xp": request.amount, "levels_gained": levels})
            await engine.save()
            return {"character": engine.characters.state(entity).model_dump(mode="json"), "levels_gained": levels}
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/{campaign_id}/party")
    async def configure_campaign_party(
        campaign_id: str, request: ConfigurePartyRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            result = engine.campaign_runner.configure_party(request.actor_ids, map_id=request.map_id, node_id=request.node_id)
            await engine.save()
            return result.model_dump(mode="json")
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/{campaign_id}/travel")
    async def campaign_travel(
        campaign_id: str, request: TravelRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_client(campaign_id, client_id)
        try:
            result = await engine.campaign_runner.travel(request.actor_id, request.map_id, request.destination_node_id, request.pace)
            await engine.save()
            return result.model_dump(mode="json")
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/{campaign_id}/encounters/budgeted")
    async def budgeted_encounter(
        campaign_id: str, request: BudgetedEncounterRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            result = await engine.campaign_runner.start_budgeted_encounter(request.party_levels, difficulty=request.difficulty, query=request.query)
            return result.model_dump(mode="json")
        except (KeyError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/{campaign_id}/encounters/finish")
    async def finish_budgeted_encounter(
        campaign_id: str, client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        try:
            result = await engine.campaign_runner.finish_encounter()
            return result.model_dump(mode="json")
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/campaigns/{campaign_id}/director")
    async def director_suggestion(campaign_id: str) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        suggestion = await engine.director.suggest()
        return {"kind": suggestion.kind, "reason": suggestion.reason, "payload": suggestion.payload}

    @app.post("/api/v1/campaigns/{campaign_id}/reaction-windows")
    async def create_reaction_window(
        campaign_id: str, request: ReactionWindowRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, str]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        window_id = await engine.open_reaction_window(
            trigger_event_id=request.trigger_event_id, eligible_actor_ids=request.eligible_actor_ids,
            allowed_reactions=request.allowed_reactions, timeout_seconds=request.timeout_seconds,
        )
        return {"window_id": window_id}

    @app.get("/api/v1/campaigns/{campaign_id}/export")
    async def export_campaign(campaign_id: str) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        package = CampaignPackage(
            campaign=engine.state.model_copy(deep=True),
            engine_config=engine.config.model_dump(mode="json"),
            installed_content_packs=dict(engine.state.metadata.get("installed_content_packs", {})),
            metadata={"format": "dnd-rpg-engine-campaign", "version": 2},
        )
        package.sha256 = package.content_hash()
        return package.model_dump(mode="json")

    @app.post("/api/v1/campaigns/{campaign_id}/entities")
    async def create_entity(
        campaign_id: str,
        request: CreateEntityRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        entity = Entity(
            id=request.id or str(uuid4()),
            name=request.name,
            kind=request.kind,
            controller=request.controller,
            owner_id=request.owner_id,
            stats=request.stats,
            resources=request.resources,
            position=request.position,
            tags=request.tags,
            components=request.components,
        )
        event = await engine.add_entity(entity, ready_delay=request.ready_delay)
        return {"entity": entity.model_dump(mode="json"), "event": event.model_dump(mode="json")}

    @app.post("/api/v1/campaigns/{campaign_id}/commands")
    async def command(
        campaign_id: str,
        request: CommandRequest,
        header_client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        client_id = request.client_id or header_client_id
        state.require_client(campaign_id, client_id)
        try:
            parsed = parse_command(request.command)
            result = await state.sessions.require(campaign_id).dispatch(client_id, parsed)
            if request.narrate:
                result.narration = await engine.gm.narrate(engine.state, result.events)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (ValueError, KeyError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "version": result.version,
            "simulation_time": result.simulation_time,
            "events": [event.model_dump(mode="json") for event in result.events],
            "narration": result.narration,
        }

    @app.post("/api/v1/campaigns/{campaign_id}/tick")
    async def tick(
        campaign_id: str,
        request: TickRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        result = await engine.tick(request.seconds, narrate=request.narrate)
        return {
            "version": result.version,
            "simulation_time": result.simulation_time,
            "events": [event.model_dump(mode="json") for event in result.events],
            "narration": result.narration,
        }

    @app.get("/api/v1/campaigns/{campaign_id}/events")
    async def events(campaign_id: str, after: int = Query(default=0, ge=0), limit: int = Query(default=250, ge=1, le=5000)):
        await state.get_engine(campaign_id)
        rows = await state.store.list_events(campaign_id, after_sequence=after, limit=limit)
        return [event.model_dump(mode="json") for event in rows]

    @app.post("/api/v1/campaigns/{campaign_id}/join")
    async def join(campaign_id: str, request: JoinRequest) -> dict[str, Any]:
        engine = await state.get_engine(campaign_id)
        if campaign_id not in state.sessions.sessions:
            await state.sessions.host(campaign_id, engine, owner_id="local")
        try:
            role = ClientRole(request.role)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid role") from exc
        identity = ClientIdentity(
            user_id=request.user_id,
            display_name=request.display_name,
            role=role,
            actor_ids=request.actor_ids,
        )
        state.sessions.require(campaign_id).join(identity)
        return identity.model_dump(mode="json")

    @app.get("/api/v1/campaigns/{campaign_id}/lobby")
    async def lobby(campaign_id: str) -> dict[str, object]:
        await state.get_engine(campaign_id)
        return state.sessions.require(campaign_id).lobby_snapshot()

    @app.post("/api/v1/campaigns/{campaign_id}/reconnect")
    async def reconnect(campaign_id: str, request: ReconnectRequest) -> dict[str, Any]:
        await state.get_engine(campaign_id)
        try:
            identity = state.sessions.require(campaign_id).reconnect(request.client_id, request.user_id)
            return identity.model_dump(mode="json")
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.get("/api/v1/campaigns/{campaign_id}/replay")
    async def replay(
        campaign_id: str, client_id: str = Query(min_length=1),
        after: int | None = Query(default=None, ge=0), limit: int = Query(default=500, ge=1, le=5000),
    ) -> list[dict[str, Any]]:
        await state.get_engine(campaign_id)
        try:
            events = await state.sessions.require(campaign_id).replay(client_id, after_sequence=after, limit=limit)
            return [event.model_dump(mode="json") for event in events]
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/{campaign_id}/parties")
    async def create_party(
        campaign_id: str, request: CreatePartyRequest,
        client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
    ) -> dict[str, Any]:
        await state.get_engine(campaign_id)
        state.require_owner(campaign_id, client_id)
        session = state.sessions.require(campaign_id)
        try:
            party = session.create_party(request.party_id, request.name)
            for actor_id in request.actor_ids:
                session.add_to_party(party.id, actor_id=actor_id)
            for user_id in request.member_user_ids:
                session.add_to_party(party.id, user_id=user_id)
            return {"id": party.id, "name": party.name, "actor_ids": sorted(party.actor_ids), "member_user_ids": sorted(party.member_user_ids)}
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/campaigns/import")
    async def import_campaign(request: ImportCampaignRequest) -> dict[str, Any]:
        try:
            package = CampaignPackage.model_validate(request.package)
            expected = package.sha256
            package.sha256 = None
            actual = package.content_hash()
            package.sha256 = expected
            if expected and expected != actual:
                raise ValueError("campaign package checksum mismatch")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        imported_state = package.campaign.model_copy(deep=True)
        if request.regenerate_id:
            imported_state.id = str(uuid4())
        imported_state.metadata["owner_id"] = request.owner_id
        engine = GameEngine(imported_state, store=state.store)
        engine.characters.bind_catalog(state.srd_runtime)
        engine.campaign_runner.bind_catalog(state.srd_runtime)
        installed = package.installed_content_packs
        if installed:
            for raw in installed.values():
                install_content_pack(engine, ContentPack.model_validate(raw))
        await engine.save()
        state.engines[engine.state.id] = engine
        session = await state.sessions.host(engine.state.id, engine, request.owner_id)
        owner = ClientIdentity(user_id=request.owner_id, display_name=request.owner_id, role=ClientRole.OWNER)
        session.join(owner)
        await state.ensure_realtime(engine.state.id, engine)
        await state.ensure_broadcast(engine.state.id, engine)
        return {"campaign_id": engine.state.id, "owner_client_id": owner.client_id, **engine.state_payload()}

    @app.post("/api/v1/creator/studio/inspect")
    async def inspect_creator_project(pack: ContentPack) -> dict[str, object]:
        return state.creator_studio.inspect(pack)

    @app.post("/api/v1/creator/studio/apply")
    async def apply_creator_project(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            pack = ContentPack.model_validate(payload["pack"])
            project = CreatorProject.model_validate(payload["project"])
            updated = project.apply_to_pack(pack)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        errors = state.validator.validate(updated)
        return {"pack": updated.model_dump(mode="json"), "valid": not errors, "errors": errors, "content_hash": updated.content_hash()}

    @app.post("/api/v2/playable-campaigns")
    async def create_playable_campaign(request: PlayableCampaignRequest) -> dict[str, Any]:
        config = request.character.model_dump()  # force request validation before side effects
        del config
        engine = await GameEngine.create(
            request.campaign_name,
            config=CreateCampaignRequest(name=request.campaign_name, owner_id=request.owner_id, seed=request.seed, time_mode=request.time_mode).config(),
            store=state.store, seed=request.seed,
        )
        engine.state.metadata["owner_id"] = request.owner_id
        engine.characters.bind_catalog(state.srd_runtime)
        engine.campaign_runner.bind_catalog(state.srd_runtime)
        install_content_pack(engine, build_srd_5_2_1_pack())
        engine.activate_rules(SRD_5_2_1_RULESET)
        if state.srd_runtime is not None:
            await state.srd_runtime.install_simple_spells(engine)
        character_request = request.character.model_copy(update={"owner_id": request.owner_id})
        character = await engine.characters.build(character_request, entity_id=str(uuid4()))
        await engine.add_entity(character)
        engine.campaign_runner.configure_party({character.id})
        await engine.save()
        state.engines[engine.state.id] = engine
        session = await state.sessions.host(engine.state.id, engine, request.owner_id)
        owner = ClientIdentity(user_id=request.owner_id, display_name=request.owner_id, role=ClientRole.OWNER)
        session.join(owner)
        await state.ensure_realtime(engine.state.id, engine)
        await state.ensure_broadcast(engine.state.id, engine)
        return {
            "campaign_id": engine.state.id, "owner_client_id": owner.client_id,
            "character_id": character.id, "character": engine.characters.state(character).model_dump(mode="json"),
            "legal_actions": engine.characters.available_actions(character),
            **engine.state_payload(),
        }

    @app.post("/api/v1/creator/validate")
    async def validate_pack(pack: ContentPack) -> dict[str, Any]:
        errors = state.validator.validate(pack)
        return {"valid": not errors, "errors": errors, "content_hash": pack.content_hash()}

    @app.post("/api/v1/creator/instantiate")
    async def instantiate_pack(request: InstantiatePackRequest) -> dict[str, Any]:
        pack = ContentPack.model_validate(request.pack)
        errors = state.validator.validate(pack)
        if errors:
            raise HTTPException(status_code=422, detail=errors)
        template = pack.campaigns.get(request.campaign_template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="campaign template not found")
        engine = await GameEngine.create(template.name, config=template.config, store=state.store, seed=template.config.seed)
        engine.state.metadata["owner_id"] = request.owner_id
        engine.characters.bind_catalog(state.srd_runtime)
        engine.campaign_runner.bind_catalog(state.srd_runtime)
        engine.state.flags.update(template.flags)
        engine.state.active_map_id = template.start_map_id
        install_content_pack(engine, pack)
        if template.active_rule_id:
            engine.activate_rules(pack.rules[template.active_rule_id].to_ruleset())
        for entity in template.entities:
            await engine.add_entity(entity.model_copy(deep=True))
        await engine.save()
        state.engines[engine.state.id] = engine
        await state.sessions.host(engine.state.id, engine, request.owner_id)
        await state.store.put_json("hosted_campaign", engine.state.id, {"owner_id": request.owner_id, "public": False, "source_pack": pack.manifest.id})
        await state.ensure_realtime(engine.state.id, engine)
        await state.ensure_broadcast(engine.state.id, engine)
        return {"campaign_id": engine.state.id, **engine.state_payload()}

    @app.post("/api/v1/marketplace/publish")
    async def publish_pack(pack: ContentPack) -> dict[str, Any]:
        errors = state.validator.validate(pack)
        if errors:
            raise HTTPException(status_code=422, detail=errors)
        item = state.marketplace.publish(pack)
        await state.store.put_json("marketplace.pack", item.id, pack.model_dump(mode="json"))
        await state.store.put_json("marketplace.item", item.id, item.model_dump(mode="json"))
        return item.model_dump(mode="json")

    @app.get("/api/v1/marketplace")
    async def search_marketplace(q: str = "", tags: str = "") -> list[dict[str, Any]]:
        wanted = {tag.strip() for tag in tags.split(",") if tag.strip()}
        return [item.model_dump(mode="json") for item in state.marketplace.search(q, tags=wanted or None)]

    @app.post("/api/v1/marketplace/{item_id}/install")
    async def install_marketplace(item_id: str) -> dict[str, Any]:
        try:
            pack = state.marketplace.install(item_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="marketplace item not found") from exc
        return {"manifest": pack.manifest.model_dump(mode="json"), "content_hash": pack.content_hash()}

    @app.websocket("/api/v1/campaigns/{campaign_id}/ws")
    async def websocket_campaign(websocket: WebSocket, campaign_id: str) -> None:
        await websocket.accept()
        try:
            engine = await state.get_engine(campaign_id)
        except HTTPException:
            await websocket.send_json({"kind": "error", "detail": "campaign not found"})
            await websocket.close(code=4404)
            return
        await state.ensure_broadcast(campaign_id, engine)
        client_id = websocket.query_params.get("client_id")
        state.websocket_clients.setdefault(campaign_id, set()).add(websocket)
        await websocket.send_json({"kind": "state", "state": engine.state_payload()})
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("kind") == "command":
                    try:
                        if not client_id:
                            raise PermissionError("campaign client id required for commands")
                        state.require_client(campaign_id, client_id)
                        parsed = parse_command(data["command"])
                        result = await state.sessions.require(campaign_id).dispatch(client_id, parsed)
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
                        await websocket.send_json({"kind": "error", "request_id": data.get("request_id"), "detail": str(exc)})
                elif data.get("kind") == "state":
                    await websocket.send_json({"kind": "state", "state": engine.state_payload()})
        except WebSocketDisconnect:
            pass
        finally:
            state.websocket_clients.get(campaign_id, set()).discard(websocket)

    static_dir = Path(__file__).resolve().parent.parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/creator")
    async def creator() -> FileResponse:
        return FileResponse(static_dir / "creator.html")

    @app.get("/play")
    async def player() -> FileResponse:
        return FileResponse(static_dir / "player.html")

    return app


app = create_app()
