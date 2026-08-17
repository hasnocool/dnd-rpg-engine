from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.api.security_helpers import campaign_resource, identity_service, require_principal
from dnd_rpg_engine.distributed import (
    DistributedWorldRuntime,
    EntityHandoff,
    WorldPartition,
    ZoneDefinition,
    ZoneLeaseManager,
)
from dnd_rpg_engine.security.models import Permission

router = APIRouter(prefix="/api/v1/distributed", tags=["distributed-world"])


class CreateWorldRequest(BaseModel):
    world_id: str = "default"
    zones: list[ZoneDefinition] = Field(default_factory=list)


class AddZoneRequest(BaseModel):
    zone: ZoneDefinition


class PlacementRequest(BaseModel):
    worker_ids: list[str] = Field(default_factory=list)


class ClaimPlacementRequest(BaseModel):
    worker_id: str
    worker_ids: list[str] = Field(default_factory=list)
    ttl_seconds: float = Field(default=15.0, gt=0, le=300)


class LeaseRequest(BaseModel):
    worker_id: str
    ttl_seconds: float = Field(default=15.0, gt=0, le=300)


class PrepareHandoffRequest(BaseModel):
    entity_id: str
    target_zone: str
    source_sequence: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _campaign_authorize(
    request: Request,
    campaign_id: str,
    permission: Permission = Permission.DISTRIBUTED_MANAGE,
):
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


async def _lease_manager(request: Request) -> ZoneLeaseManager:
    manager = getattr(request.app.state, "zone_leases", None)
    if manager is None:
        manager = ZoneLeaseManager(request.app.state.rpg.store)
        await manager.initialize()
        request.app.state.zone_leases = manager
    return manager


async def _persist(request: Request, campaign_id: str, runtime: DistributedWorldRuntime) -> None:
    await request.app.state.rpg.store.put_json(
        "distributed.partition", campaign_id, runtime.partition.model_dump(mode="json")
    )


async def _workers(request: Request, requested: list[str]) -> list[dict[str, Any]]:
    if requested:
        return [{"worker_id": value, "capacity": 1} for value in sorted(set(requested))]
    if hasattr(request.app.state.rpg.store, "list_active_workers"):
        return await request.app.state.rpg.store.list_active_workers()
    raise HTTPException(status_code=409, detail="worker IDs are required for the SQLite backend")


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
    workers = await _workers(request, payload.worker_ids)
    return {"placement": runtime.place_zones(workers), "workers": workers}


@router.post("/campaigns/{campaign_id}/placement/claim")
async def claim_zone_placement(request: Request, campaign_id: str, payload: ClaimPlacementRequest) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    runtime = await _runtime(request, campaign_id)
    assert runtime is not None
    workers = await _workers(request, payload.worker_ids)
    if payload.worker_id not in {str(value["worker_id"]) for value in workers}:
        raise HTTPException(status_code=422, detail="worker_id is not in the placement worker set")
    placement = runtime.place_zones(workers)
    leases = await (await _lease_manager(request)).claim_placement(
        campaign_id,
        placement,
        payload.worker_id,
        ttl_seconds=payload.ttl_seconds,
    )
    return {
        "placement": placement,
        "claimed": [value.model_dump(mode="json") for value in leases],
    }


@router.get("/campaigns/{campaign_id}/leases")
async def list_zone_leases(request: Request, campaign_id: str) -> list[dict[str, Any]]:
    await _campaign_authorize(request, campaign_id, Permission.CAMPAIGN_READ)
    return [value.model_dump(mode="json") for value in await (await _lease_manager(request)).list(campaign_id)]


@router.post("/campaigns/{campaign_id}/leases/{zone_id}")
async def acquire_zone_lease(
    request: Request,
    campaign_id: str,
    zone_id: str,
    payload: LeaseRequest,
) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    runtime = await _runtime(request, campaign_id)
    assert runtime is not None
    if zone_id not in runtime.partition.zones:
        raise HTTPException(status_code=404, detail="zone not found")
    lease = await (await _lease_manager(request)).acquire(
        campaign_id, zone_id, payload.worker_id, ttl_seconds=payload.ttl_seconds
    )
    if lease is None:
        raise HTTPException(status_code=409, detail="zone is leased by another worker")
    return lease.model_dump(mode="json")


@router.patch("/campaigns/{campaign_id}/leases/{zone_id}")
async def renew_zone_lease(
    request: Request,
    campaign_id: str,
    zone_id: str,
    payload: LeaseRequest,
) -> dict[str, Any]:
    await _campaign_authorize(request, campaign_id)
    lease = await (await _lease_manager(request)).renew(
        campaign_id, zone_id, payload.worker_id, ttl_seconds=payload.ttl_seconds
    )
    if lease is None:
        raise HTTPException(status_code=409, detail="worker does not hold an active zone lease")
    return lease.model_dump(mode="json")


@router.delete("/campaigns/{campaign_id}/leases/{zone_id}", status_code=204)
async def release_zone_lease(
    request: Request,
    campaign_id: str,
    zone_id: str,
    worker_id: str = Query(...),
) -> None:
    await _campaign_authorize(request, campaign_id)
    released = await (await _lease_manager(request)).release(campaign_id, zone_id, worker_id)
    if not released:
        raise HTTPException(status_code=404, detail="matching zone lease not found")


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


async def _load_handoff(
    request: Request,
    campaign_id: str,
    handoff_id: str,
    runtime: DistributedWorldRuntime,
) -> EntityHandoff:
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
