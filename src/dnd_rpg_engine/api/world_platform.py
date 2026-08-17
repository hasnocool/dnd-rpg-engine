from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.campaign.orchestrator import SceneDefinition, SceneStatus
from dnd_rpg_engine.core.world_engine import WorldPlatformEngine
from dnd_rpg_engine.multiplayer.protocol import ClientRole
from dnd_rpg_engine.rules.compiler import RuleProvenance

router = APIRouter(prefix="/api/v1/campaigns", tags=["world-platform"])


class CompileRuleRequest(BaseModel):
    rule_id: str
    name: str
    graph: dict[str, Any] = Field(default_factory=dict)
    provenance: RuleProvenance | None = None


class SceneTransitionRequest(BaseModel):
    status: SceneStatus
    reason: str = "api"
    exclusive: bool = False


def _client(request: Request, campaign_id: str, client_id: str | None):
    return request.app.state.rpg.require_client(campaign_id, client_id)


def _owner(request: Request, campaign_id: str, client_id: str | None):
    return request.app.state.rpg.require_owner(campaign_id, client_id)


async def _engine(request: Request, campaign_id: str) -> WorldPlatformEngine:
    engine = await request.app.state.rpg.get_engine(campaign_id)
    if not isinstance(engine, WorldPlatformEngine):
        raise HTTPException(status_code=409, detail="world-platform API requires WorldPlatformEngine")
    return engine


@router.post("/{campaign_id}/rules/compile")
async def compile_rule(
    request: Request,
    campaign_id: str,
    payload: CompileRuleRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    try:
        graph = engine.compile_rule_graph(payload.rule_id, payload.name, payload.graph, provenance=payload.provenance)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return graph.model_dump(mode="json")


@router.post("/{campaign_id}/scenes")
async def register_scene(
    request: Request,
    campaign_id: str,
    scene: SceneDefinition,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    engine.register_scene(scene)
    await engine.save()
    return engine.orchestrator.state_for(scene.id).model_dump(mode="json")


@router.patch("/{campaign_id}/scenes/{scene_id}")
async def transition_scene(
    request: Request,
    campaign_id: str,
    scene_id: str,
    payload: SceneTransitionRequest,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    try:
        if payload.status is SceneStatus.ACTIVE:
            transition = engine.orchestrator.activate(scene_id, reason=payload.reason, exclusive=payload.exclusive)
        else:
            transition = engine.orchestrator.transition(scene_id, payload.status, reason=payload.reason)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await engine.save()
    return transition.model_dump(mode="json")


@router.get("/{campaign_id}/director/proposals")
async def director_proposals(
    request: Request,
    campaign_id: str,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> list[dict[str, Any]]:
    _owner(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    return [value.model_dump(mode="json") for value in engine.director_proposals()]


@router.get("/{campaign_id}/runtime")
async def runtime_snapshot(
    request: Request,
    campaign_id: str,
    actor_id: str | None = None,
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    identity = _client(request, campaign_id, client_id)
    engine = await _engine(request, campaign_id)
    if actor_id is None:
        if identity.role is not ClientRole.OWNER:
            raise HTTPException(status_code=403, detail="only campaign owners may request an omniscient runtime snapshot")
        return engine.runtime_snapshot().model_dump(mode="json")
    if identity.role is not ClientRole.OWNER and actor_id not in identity.actor_ids:
        raise HTTPException(status_code=403, detail="client does not own requested actor knowledge")
    try:
        return engine.runtime_snapshot(actor_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
