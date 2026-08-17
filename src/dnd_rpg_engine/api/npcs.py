# src/dnd_rpg_engine/api/npcs.py
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from dnd_rpg_engine.adventure.npcs import NPCProfile
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.models import EntityKind

router = APIRouter(prefix="/api/v1/campaigns", tags=["npcs"])


async def _engine(request: Request, campaign_id: str) -> AdvancedGameEngine:
    engine = await request.app.state.rpg.get_engine(campaign_id)
    if not isinstance(engine, AdvancedGameEngine):
        raise HTTPException(status_code=409, detail="NPC management requires AdvancedGameEngine")
    return engine


async def _owner_engine(request: Request, campaign_id: str, client_id: str | None) -> AdvancedGameEngine:
    engine = await _engine(request, campaign_id)
    request.app.state.rpg.require_owner(campaign_id, client_id)
    return engine


def _profile_payload(engine: AdvancedGameEngine, actor_id: str) -> dict:
    profile = engine.npcs.get(actor_id)
    entity = engine.state.entities.get(actor_id)
    if profile is None and entity is None:
        raise KeyError(actor_id)
    return {
        "profile": None if profile is None else profile.model_dump(mode="json"),
        "entity": None if entity is None else entity.model_dump(mode="json"),
    }


def _apply_profile_to_entity(engine: AdvancedGameEngine, profile: NPCProfile) -> None:
    entity = engine.state.require_entity(profile.entity_id)
    entity.name = profile.name or profile.entity_id
    entity.controller = profile.controller
    entity.stats = profile.stats.model_copy(deep=True)
    entity.resources = profile.resources.model_copy(deep=True)
    entity.position = profile.position.model_copy(deep=True)
    entity.tags = {"npc", *profile.tags}
    entity.components["npc"] = {
        "role": profile.role,
        "dialogue_id": profile.dialogue_id,
        "shop_id": profile.shop_id,
        "personality_id": profile.personality_id,
        "schedule_id": profile.schedule_id,
    }
    entity.components["ai"] = {"profile": profile.ai_profile}
    if profile.appearance:
        entity.components["appearance"] = dict(profile.appearance)
    else:
        entity.components.pop("appearance", None)
    if profile.faction_id:
        entity.components["faction"] = {"id": profile.faction_id}
    else:
        entity.components.pop("faction", None)


def _sync_schedule(engine: AdvancedGameEngine, profile: NPCProfile) -> None:
    engine.world.schedules.assignments.pop(profile.entity_id, None)
    if profile.schedule_id:
        if profile.schedule_id not in engine.world.schedules.schedules:
            raise ValueError(f"unknown NPC schedule: {profile.schedule_id}")
        engine.world.schedules.assign(profile.entity_id, profile.schedule_id)


@router.get("/{campaign_id}/npcs")
async def list_npcs(request: Request, campaign_id: str, client_id: str | None = Header(default=None, alias="X-RPG-Client-ID")) -> list[dict]:
    engine = await _owner_engine(request, campaign_id, client_id)
    actor_ids = {entity.id for entity in engine.state.entities.values() if entity.kind is EntityKind.NPC} | {profile.entity_id for profile in engine.npcs.all()}
    return [_profile_payload(engine, actor_id) for actor_id in sorted(actor_ids)]


@router.post("/{campaign_id}/npcs")
async def create_npc(request: Request, campaign_id: str, profile: NPCProfile, client_id: str | None = Header(default=None, alias="X-RPG-Client-ID")) -> dict:
    engine = await _owner_engine(request, campaign_id, client_id)
    if profile.entity_id in engine.state.entities:
        raise HTTPException(status_code=409, detail="NPC entity already exists")
    try:
        _sync_schedule(engine, profile)
        entity = profile.to_entity()
        await engine.add_entity(entity)
        engine.npcs.register(profile.model_copy(deep=True))
        await engine._emit("npc.created", actor_id=profile.entity_id, payload={"role": profile.role})
        await engine.save()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _profile_payload(engine, profile.entity_id)


@router.get("/{campaign_id}/npcs/{actor_id}")
async def get_npc(request: Request, campaign_id: str, actor_id: str, client_id: str | None = Header(default=None, alias="X-RPG-Client-ID")) -> dict:
    engine = await _owner_engine(request, campaign_id, client_id)
    try:
        return _profile_payload(engine, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="NPC not found") from exc


@router.patch("/{campaign_id}/npcs/{actor_id}")
async def update_npc(request: Request, campaign_id: str, actor_id: str, profile: NPCProfile, client_id: str | None = Header(default=None, alias="X-RPG-Client-ID")) -> dict:
    engine = await _owner_engine(request, campaign_id, client_id)
    if profile.entity_id != actor_id:
        raise HTTPException(status_code=422, detail="NPC entity_id cannot be changed")
    entity = engine.state.entities.get(actor_id)
    if entity is None or entity.kind is not EntityKind.NPC:
        raise HTTPException(status_code=404, detail="NPC not found")
    try:
        _sync_schedule(engine, profile)
        engine.npcs.register(profile.model_copy(deep=True))
        _apply_profile_to_entity(engine, profile)
        await engine._emit("npc.updated", actor_id=actor_id, payload={"role": profile.role})
        await engine.save()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _profile_payload(engine, actor_id)


@router.delete("/{campaign_id}/npcs/{actor_id}")
async def delete_npc(request: Request, campaign_id: str, actor_id: str, client_id: str | None = Header(default=None, alias="X-RPG-Client-ID")) -> dict[str, bool]:
    engine = await _owner_engine(request, campaign_id, client_id)
    entity = engine.state.entities.get(actor_id)
    if entity is None or entity.kind is not EntityKind.NPC:
        raise HTTPException(status_code=404, detail="NPC not found")
    engine.npcs.remove(actor_id)
    engine.world.schedules.assignments.pop(actor_id, None)
    engine.state.entities.pop(actor_id, None)
    await engine._emit("npc.removed", actor_id=actor_id, payload={})
    await engine.save()
    return {"deleted": True}
