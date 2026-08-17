# src/dnd_rpg_engine/api/lifecycle.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.characters.lifecycle import CharacterBuildRequest
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.commands import CustomCommand

router = APIRouter(prefix="/api/v1/campaigns", tags=["character-lifecycle"])


class XPRequest(BaseModel):
    amount: int = Field(ge=0)


class LevelUpRequest(BaseModel):
    class_id: str


class RestRequest(BaseModel):
    profile_id: str = "long_rest"


class EquipmentRequest(BaseModel):
    item_id: str


class ResourceRequest(BaseModel):
    resource_id: str
    amount: int = Field(default=1, ge=0)


def _require_owner(request: Request, campaign_id: str, client_id: str | None) -> None:
    request.app.state.rpg.require_owner(campaign_id, client_id)


async def _advanced_engine(request: Request, campaign_id: str) -> AdvancedGameEngine:
    engine = await request.app.state.rpg.get_engine(campaign_id)
    if not isinstance(engine, AdvancedGameEngine):
        raise HTTPException(
            status_code=409,
            detail="character lifecycle API requires AdvancedGameEngine; start the server with advanced mode enabled",
        )
    return engine


async def _dispatch(
    request: Request,
    campaign_id: str,
    actor_id: str,
    name: str,
    payload: dict[str, Any],
    client_id: str | None,
) -> dict[str, Any]:
    engine = await _advanced_engine(request, campaign_id)
    if not client_id:
        raise HTTPException(status_code=401, detail="campaign client id required")
    request.app.state.rpg.require_client(campaign_id, client_id)
    command = CustomCommand(actor_id=actor_id, name=name, payload=payload)
    try:
        result = await request.app.state.rpg.sessions.require(campaign_id).dispatch(client_id, command)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, KeyError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "version": result.version,
        "simulation_time": result.simulation_time,
        "events": [event.model_dump(mode="json") for event in result.events],
        "character": engine.state.require_entity(actor_id).model_dump(mode="json"),
    }


@router.post("/{campaign_id}/characters")
async def create_character(
    request: Request,
    campaign_id: str,
    build: CharacterBuildRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    engine = await _advanced_engine(request, campaign_id)
    _require_owner(request, campaign_id, client_id)
    try:
        entity = await engine.create_character(build)
        await engine.save()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"character": entity.model_dump(mode="json")}


@router.get("/{campaign_id}/characters/{actor_id}")
async def get_character(request: Request, campaign_id: str, actor_id: str) -> dict[str, Any]:
    engine = await _advanced_engine(request, campaign_id)
    try:
        entity = engine.state.require_entity(actor_id)
        progress = engine.character_lifecycle.progress(entity)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "entity": entity.model_dump(mode="json"),
        "progress": progress.model_dump(mode="json"),
        "resources": {
            key: value.model_dump(mode="json")
            for key, value in engine.character_lifecycle.resources(entity).items()
        },
        "equipment": engine.character_lifecycle.equipment_state(entity).model_dump(mode="json"),
        "equipment_modifiers": engine.character_lifecycle.effective_equipment_modifiers(entity),
        "level_ready": engine.character_lifecycle.eligible_for_level(entity),
    }


@router.post("/{campaign_id}/characters/{actor_id}/xp")
async def award_xp(
    request: Request,
    campaign_id: str,
    actor_id: str,
    payload: XPRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _require_owner(request, campaign_id, client_id)
    return await _dispatch(request, campaign_id, actor_id, "character.award_xp", payload.model_dump(), client_id)


@router.post("/{campaign_id}/characters/{actor_id}/level-up")
async def level_up(
    request: Request,
    campaign_id: str,
    actor_id: str,
    payload: LevelUpRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _require_owner(request, campaign_id, client_id)
    return await _dispatch(request, campaign_id, actor_id, "character.level_up", payload.model_dump(), client_id)


@router.post("/{campaign_id}/characters/{actor_id}/rest")
async def rest(
    request: Request,
    campaign_id: str,
    actor_id: str,
    payload: RestRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    return await _dispatch(request, campaign_id, actor_id, "character.rest", payload.model_dump(), client_id)


@router.post("/{campaign_id}/characters/{actor_id}/equip")
async def equip(
    request: Request,
    campaign_id: str,
    actor_id: str,
    payload: EquipmentRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    return await _dispatch(request, campaign_id, actor_id, "character.equip", payload.model_dump(), client_id)


@router.post("/{campaign_id}/characters/{actor_id}/unequip")
async def unequip(
    request: Request,
    campaign_id: str,
    actor_id: str,
    payload: EquipmentRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    return await _dispatch(request, campaign_id, actor_id, "character.unequip", payload.model_dump(), client_id)


@router.post("/{campaign_id}/characters/{actor_id}/resources/spend")
async def spend_resource(
    request: Request,
    campaign_id: str,
    actor_id: str,
    payload: ResourceRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    return await _dispatch(request, campaign_id, actor_id, "character.spend_resource", payload.model_dump(), client_id)


@router.post("/{campaign_id}/characters/{actor_id}/resources/restore")
async def restore_resource(
    request: Request,
    campaign_id: str,
    actor_id: str,
    payload: ResourceRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _require_owner(request, campaign_id, client_id)
    return await _dispatch(request, campaign_id, actor_id, "character.restore_resource", payload.model_dump(), client_id)
