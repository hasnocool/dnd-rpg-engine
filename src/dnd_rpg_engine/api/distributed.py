from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.api.security_helpers import campaign_resource, identity_service, require_principal
from dnd_rpg_engine.distributed import DistributedWorldRuntime, EntityHandoff, WorldPartition, ZoneDefinition
from dnd_rpg_engine.security.models import Permission

router = APIRouter(prefix="/api/v1/distributed", tags=["distributed-world"])


class CreateWorldRequest(BaseModel):
    world_id: str = "default"
    zones: list[ZoneDefinition] = Field(default_factory=list)


class AddZoneRequest(BaseModel):
    zone: ZoneDefinition


class PlacementRequest(BaseModel):
    worker_ids: list[str] = Field(default_factory=list)


class PrepareHandoffRequest(BaseModel):
    entity_id: str
    target_zone: str
    source_sequence: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _authorize(request: Request, campaign_id: str, permission: Permission = Permission.DISTRIBUTED_MANAGE):
    principal = require_principal(request)
    return principal


async def _campaign_authorize(request: Request, campaign_id: str, permission: Permission = Permission.DISTRIBUTED_MANAGE):
    principal = require_principal(request)
    resource = await campaign_resource(request, campaign_id)
    try:
        identity_service(request).authorize(principal, permission, resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return principal


async def _runtime(request: Request, campaign_id: str, *, required: bool = True) -> DistributedWorldRuntime | None:
    runtime = request.app.state.distributed_worlds.get(campaign_id)
    if runtime is not None:
        return runtime
    raw = await request.app.state.rpg.store.get_json("distributed.partition", campaign_id)
    if raw is None:
        if required:
            raise HTTPException(status_code=404, detail="distributed world is not configured")
        return None
    partition = WorldPartition.model_validate(raw)
    runtime = DistributedWorldRuntime(partition, store=request.app.state.rpg.store)
    stored = await request.app.state.rpg.store.list_json("distributed.handoff")
    runtime.handoffs.handoffs = {
        handoff_id: EntityHandoff.model_validate(value)
        for handoff_id, value in stored.items()
        if value.get("campaign_id") == campaign_id
    }
    request.app.state.distributed_worlds[campaign_id] = runtime
    return runtime


async def _persist(request: Request, campaign_id: str, runtime: DistributedWorldRuntime) -> None:
    await request.app.state.rpg.store.put_json(
        "distributed.partition", campaign_id, runtime.partition.model_dump(mode="json")
    )


@router.put("/campaigns/{campaign_id}/world")
async def configure_world(request: Request, campaign_id: str, payload: CreateWorldRequest) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    partition = WorldPartition(world_id=payload.world_id)
    for zone in payload.zones:
        partition.register_zone(zone.model_copy(update={"world_id": payload.world_id}))
    runtime = DistributedWorldRuntime(partition, store=request.app.state.rpg.store)
    for entity in engine.state.entities.values():
        if entity.position.area_id in partition.zones:
            runtime.register_entity(entity, entity.position.area_id)
    request.app.state.distributed_worlds[campaign_id] = runtime
    await _persist(request, campaign_id, runtime)
    return partition.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/zones")
async def add_zone(request: Request, campaign_id: str, payload: AddZoneRequest) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    runtime = await _runtime(request, campaign_id)
    assert runtime is not None
    zone = payload.zone.model_copy(update={"world_id": runtime.partition.world_id})
    runtime.partition.register_zone(zone)
    await _persist(request, campaign_id, runtime)
    return zone.model_dump(mode="json")


@router.get("/campaigns/{campaign_id}/world")
async def get_world(request: Request, campaign_id: str) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id, Permission.CAMPAIGN_READ)
    runtime = await _runtime(request, campaign_id)
    assert runtime is not None
    return runtime.partition.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/placement")
async def zone_placement(request: Request, campaign_id: str, payload: PlacementRequest) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    runtime = await _runtime(request, campaign_id)
    assert runtime is not None
    workers: list[dict[str, Any]]
    if payload.worker_ids:
        workers = [{"worker_id": value, "capacity": 1} for value in payload.worker_ids]
    elif hasattr(request.app.state.rpg.store, "list_active_workers"):
        workers = await request.app.state.rpg.store.list_active_workers()
    else:
        raise HTTPException(status_code=409, detail="worker IDs are required for the SQLite backend")
    return {"placement": runtime.place_zones(workers), "workers": workers}


@router.post("/campaigns/{campaign_id}/handoffs")
async def prepare_handoff(request: Request, campaign_id: str, payload: PrepareHandoffRequest) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    runtime = await _runtime(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    assert runtime is not None
    try:
        handoff = await runtime.handoffs.prepare(
            engine.state,
            payload.entity_id,
            payload.target_zone,
            source_sequence=payload.source_sequence,
            metadata=payload.metadata,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return handoff.model_dump(mode="json")


async def _load_handoff(request: Request, campaign_id: str, handoff_id: str, runtime: DistributedWorldRuntime) -> EntityHandoff:
    handoff = runtime.handoffs.handoffs.get(handoff_id)
    if handoff is None:
        raw = await request.app.state.rpg.store.get_json("distributed.handoff", handoff_id)
        if raw is None or raw.get("campaign_id") != campaign_id:
            raise HTTPException(status_code=404, detail="handoff not found")
        handoff = EntityHandoff.model_validate(raw)
        runtime.handoffs.handoffs[handoff_id] = handoff
    return handoff


@router.post("/campaigns/{campaign_id}/handoffs/{handoff_id}/commit")
async def commit_handoff(request: Request, campaign_id: str, handoff_id: str) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    runtime = await _runtime(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    assert runtime is not None
    await _load_handoff(request, campaign_id, handoff_id, runtime)
    try:
        handoff = await runtime.handoffs.commit_source(engine.state, handoff_id)
        await engine.save()
        await _persist(request, campaign_id, runtime)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return handoff.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/handoffs/{handoff_id}/accept")
async def accept_handoff(request: Request, campaign_id: str, handoff_id: str) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    runtime = await _runtime(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    assert runtime is not None
    handoff = await _load_handoff(request, campaign_id, handoff_id, runtime)
    try:
        entity = await runtime.handoffs.accept_target(engine.state, handoff)
        await engine.save()
        await _persist(request, campaign_id, runtime)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"handoff": handoff.model_dump(mode="json"), "entity": entity.model_dump(mode="json")}
