# src/dnd_rpg_engine/api/workbench.py
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.core.world_engine import WorldPlatformEngine
from dnd_rpg_engine.multiplayer.protocol import ClientRole

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaign-workbench"])


class CreatePartyRequest(BaseModel):
    id: str
    name: str


class PartyMemberRequest(BaseModel):
    user_id: str | None = None
    actor_id: str | None = None


class DirectorDecisionRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


def _client(request: Request, campaign_id: str, client_id: str | None):
    return request.app.state.rpg.require_client(campaign_id, client_id)


def _owner(request: Request, campaign_id: str, client_id: str | None):
    return request.app.state.rpg.require_owner(campaign_id, client_id)


async def _engine(request: Request, campaign_id: str) -> WorldPlatformEngine:
    engine = await request.app.state.rpg.get_engine(campaign_id)
    if not isinstance(engine, WorldPlatformEngine):
        raise HTTPException(status_code=409, detail="campaign workbench requires WorldPlatformEngine")
    return engine


def _entity_payloads_for(engine: WorldPlatformEngine, identity: Any, actor_id: str | None) -> dict[str, dict[str, Any]]:
    if identity.role is ClientRole.OWNER:
        return {
            entity_id: entity.model_dump(mode="json")
            for entity_id, entity in sorted(engine.state.entities.items())
        }
    if actor_id is not None and actor_id not in identity.actor_ids:
        raise HTTPException(status_code=403, detail="client does not own requested actor")
    owned = [actor_id] if actor_id else sorted(identity.actor_ids)
    entities: dict[str, dict[str, Any]] = {}
    for owned_id in owned:
        if not owned_id:
            continue
        try:
            view = engine.knowledge_view(owned_id)
        except KeyError:
            continue
        entities.update(view.entities)
    return {key: entities[key] for key in sorted(entities)}


def _spatial_summary(engine: WorldPlatformEngine, *, include_details: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for space_id, space in sorted(engine.spatial.spaces.items()):
        row: dict[str, Any] = {"id": space_id, "kind": type(space).__name__}
        if include_details:
            for attribute in ("width", "height", "depth", "bounds", "diagonal"):
                value = getattr(space, attribute, None)
                if value is not None:
                    if hasattr(value, "model_dump"):
                        value = value.model_dump(mode="json")
                    row[attribute] = value
        rows.append(row)
    return rows


def _installed_pack_rows(engine: WorldPlatformEngine) -> list[dict[str, Any]]:
    raw = engine.state.metadata.get("installed_content_packs", {})
    if not isinstance(raw, dict):
        return []
    rows: list[dict[str, Any]] = []
    for install_id, pack in sorted(raw.items()):
        if not isinstance(pack, dict):
            continue
        manifest = pack.get("manifest", {}) if isinstance(pack.get("manifest"), dict) else {}
        sections = {
            key: len(value)
            for key, value in pack.items()
            if key != "manifest" and isinstance(value, dict)
        }
        rows.append(
            {
                "install_id": install_id,
                "id": manifest.get("id"),
                "name": manifest.get("name"),
                "version": manifest.get("version"),
                "author": manifest.get("author"),
                "license": manifest.get("license"),
                "dependencies": manifest.get("dependencies", {}),
                "tags": manifest.get("tags", []),
                "sections": sections,
                "pack": pack,
            }
        )
    return rows


@router.get("/{campaign_id}/workbench/session")
async def workbench_session(
    request: Request,
    campaign_id: str,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    session = request.app.state.rpg.sessions.require(campaign_id)
    return {
        "campaign_id": campaign_id,
        "owner_id": session.owner_id,
        "clients": [
            identity.model_dump(mode="json")
            for _, identity in sorted(session.clients.items())
        ],
        "parties": [
            {
                "id": party.id,
                "name": party.name,
                "actor_ids": sorted(party.actor_ids),
                "member_user_ids": sorted(party.member_user_ids),
            }
            for _, party in sorted(session.parties.items())
        ],
        "scenes": {
            scene_id: {
                "definition": engine.orchestrator.definitions[scene_id].model_dump(mode="json")
                if scene_id in engine.orchestrator.definitions
                else None,
                "runtime": runtime.model_dump(mode="json"),
            }
            for scene_id, runtime in sorted(engine.orchestrator.runtime.items())
        },
        "active_scene_ids": engine.orchestrator.active_scene_ids(),
        "simulation_time": engine.state.simulation_time,
        "world_minutes": engine.state.world_minutes,
    }


@router.post("/{campaign_id}/workbench/parties")
async def create_party(
    request: Request,
    campaign_id: str,
    payload: CreatePartyRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    session = request.app.state.rpg.sessions.require(campaign_id)
    try:
        party = session.create_party(payload.id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": party.id,
        "name": party.name,
        "actor_ids": [],
        "member_user_ids": [],
    }


@router.post("/{campaign_id}/workbench/parties/{party_id}/members")
async def add_party_member(
    request: Request,
    campaign_id: str,
    party_id: str,
    payload: PartyMemberRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    session = request.app.state.rpg.sessions.require(campaign_id)
    if party_id not in session.parties:
        raise HTTPException(status_code=404, detail="party not found")
    if not payload.user_id and not payload.actor_id:
        raise HTTPException(status_code=422, detail="user_id or actor_id is required")
    if payload.actor_id:
        engine = await _engine(request, campaign_id)
        if payload.actor_id not in engine.state.entities:
            raise HTTPException(status_code=404, detail="actor not found")
    session.add_to_party(party_id, user_id=payload.user_id, actor_id=payload.actor_id)
    party = session.parties[party_id]
    return {
        "id": party.id,
        "name": party.name,
        "actor_ids": sorted(party.actor_ids),
        "member_user_ids": sorted(party.member_user_ids),
    }


@router.get("/{campaign_id}/workbench/catalog")
async def workbench_catalog(
    request: Request,
    campaign_id: str,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _client(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    return {
        "actions": [value.model_dump(mode="json") for value in engine.actions.all()],
        "spells": [value.model_dump(mode="json") for value in engine.spells.all()],
        "items": [value.model_dump(mode="json") for value in engine.items.all()],
        "conditions": [value.model_dump(mode="json") for value in engine.conditions.all()],
        "rule_graphs": [
            {
                "id": graph.id,
                "name": graph.name,
                "graph_hash": graph.graph_hash,
                "action_time_seconds": graph.action_time_seconds,
                "capabilities": sorted(value.value for value in graph.capabilities),
            }
            for _, graph in sorted(engine.rule_graphs.items())
        ],
    }


@router.get("/{campaign_id}/workbench/tactical")
async def workbench_tactical(
    request: Request,
    campaign_id: str,
    actor_id: str | None = None,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    identity = _client(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    entities = _entity_payloads_for(engine, identity, actor_id)
    selected = entities.get(actor_id) if actor_id else None
    action_economy: dict[str, Any] | None = None
    if actor_id and actor_id in engine.state.entities and (identity.role is ClientRole.OWNER or actor_id in identity.actor_ids):
        actor = engine.state.entities[actor_id]
        economy_method = getattr(engine.combat.runtime, "action_economy", None)
        if callable(economy_method):
            try:
                economy = economy_method(actor)
                action_economy = economy.model_dump(mode="json") if hasattr(economy, "model_dump") else dict(economy)
            except Exception:
                action_economy = None
    return {
        "campaign_id": campaign_id,
        "simulation_time": engine.state.simulation_time,
        "active_map_id": engine.state.active_map_id,
        "knowledge_scoped": identity.role is not ClientRole.OWNER,
        "selected_actor_id": actor_id,
        "selected_actor": selected,
        "entities": entities,
        "spaces": _spatial_summary(engine, include_details=identity.role is ClientRole.OWNER),
        "action_economy": action_economy,
        "active_scene_ids": engine.orchestrator.active_scene_ids(),
    }


@router.get("/{campaign_id}/workbench/analytics")
async def workbench_analytics(
    request: Request,
    campaign_id: str,
    limit: int = 5000,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    rows = await request.app.state.rpg.store.list_events(campaign_id, after_sequence=0, limit=max(1, min(limit, 5000)))
    type_counts: Counter[str] = Counter()
    actor_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    numeric_totals: defaultdict[str, float] = defaultdict(float)
    for event in rows:
        type_counts[event.type] += 1
        if event.actor_id:
            actor_counts[event.actor_id] += 1
        if event.target_id:
            target_counts[event.target_id] += 1
        payload = event.payload if isinstance(event.payload, dict) else {}
        for key in ("damage", "healing", "amount", "delta", "xp"):
            value = payload.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric_totals[key] += float(value)
    entity_health = {
        entity_id: {
            "name": entity.name,
            "hp": entity.resources.hp,
            "max_hp": entity.resources.max_hp,
            "alive": entity.alive,
        }
        for entity_id, entity in sorted(engine.state.entities.items())
    }
    return {
        "campaign_id": campaign_id,
        "event_count": len(rows),
        "simulation_time": engine.state.simulation_time,
        "world_minutes": engine.state.world_minutes,
        "event_types": dict(type_counts.most_common()),
        "actors": dict(actor_counts.most_common()),
        "targets": dict(target_counts.most_common()),
        "numeric_totals": dict(sorted(numeric_totals.items())),
        "entity_health": entity_health,
        "director_pressure": float(engine.state.metadata.get("director_pressure", 0.0)),
        "active_scene_ids": engine.orchestrator.active_scene_ids(),
    }


@router.get("/{campaign_id}/workbench/knowledge")
async def workbench_knowledge(
    request: Request,
    campaign_id: str,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    actors: dict[str, Any] = {}
    for entity_id, entity in sorted(engine.state.entities.items()):
        if entity.controller.value != "human" and entity.kind.value != "player":
            continue
        knowledge = engine.knowledge.knowledge_for(entity)
        actors[entity_id] = knowledge.model_dump(mode="json")
    return {
        "campaign_id": campaign_id,
        "truth_entity_ids": sorted(engine.state.entities),
        "actors": actors,
    }


@router.get("/{campaign_id}/workbench/replay")
async def workbench_replay(
    request: Request,
    campaign_id: str,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    events = await request.app.state.rpg.store.list_events(campaign_id, after_sequence=0, limit=5000)
    stored_entries = await request.app.state.rpg.store.list_json("event_source.entry")
    prefix = f"{campaign_id}:"
    journal_entries = [
        {"storage_key": key, **value}
        for key, value in sorted(stored_entries.items())
        if key.startswith(prefix) and isinstance(value, dict)
    ]
    return {
        "campaign_id": campaign_id,
        "event_source_head": engine.state.metadata.get("event_source_head"),
        "events": [event.model_dump(mode="json") for event in events],
        "journal_entries": journal_entries,
        "branching_available": bool(journal_entries),
        "note": "State rewind/branch controls are available when the campaign is running through EventSourcedEngine; the persisted event timeline is always available.",
    }


@router.get("/{campaign_id}/workbench/content")
async def workbench_content(
    request: Request,
    campaign_id: str,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    packs = _installed_pack_rows(engine)
    automations = []
    for row in packs:
        pack = row.get("pack", {})
        for section in ("dynamic_events", "schedules"):
            values = pack.get(section, {}) if isinstance(pack, dict) else {}
            if isinstance(values, dict):
                for object_id, value in sorted(values.items()):
                    automations.append({"pack": row.get("install_id"), "section": section, "id": object_id, "definition": value})
    return {
        "campaign_id": campaign_id,
        "packs": packs,
        "automations": automations,
        "director_decisions": engine.state.metadata.get("director_decisions", []),
    }


@router.post("/{campaign_id}/workbench/director/{proposal_id}/accept")
async def accept_director_proposal(
    request: Request,
    campaign_id: str,
    proposal_id: str,
    payload: DirectorDecisionRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    try:
        return await engine.accept_director_proposal(proposal_id, note=payload.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{campaign_id}/workbench/director/{proposal_id}/dismiss")
async def dismiss_director_proposal(
    request: Request,
    campaign_id: str,
    proposal_id: str,
    payload: DirectorDecisionRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    try:
        return await engine.dismiss_director_proposal(proposal_id, note=payload.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
