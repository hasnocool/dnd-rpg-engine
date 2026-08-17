# src/dnd_rpg_engine/api/studio.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.adventure.maps import AreaEdge, AreaNode
from dnd_rpg_engine.creator.content import ContentPack, ModManifest
from dnd_rpg_engine.creator.studio import CreatorStudio, StudioSection

router = APIRouter(prefix="/api/v1/studio", tags=["creator-studio"])


class CreateProjectRequest(BaseModel):
    name: str
    manifest: ModManifest


class UpsertObjectRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class MoveNodeRequest(BaseModel):
    x: float
    y: float
    z: float | None = None


class RestoreRevisionRequest(BaseModel):
    revision: int = Field(ge=0)


def _studio(request: Request) -> CreatorStudio:
    state = request.app.state.rpg
    return CreatorStudio(state.store, validator=state.validator)


@router.post("/projects")
async def create_project(request: Request, payload: CreateProjectRequest) -> dict[str, Any]:
    project = await _studio(request).create_project(name=payload.name, manifest=payload.manifest)
    return project.model_dump(mode="json")


@router.get("/projects/{project_id}")
async def get_project(request: Request, project_id: str) -> dict[str, Any]:
    try:
        project = await _studio(request).get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.put("/projects/{project_id}/pack")
async def replace_pack(request: Request, project_id: str, pack: ContentPack) -> dict[str, Any]:
    try:
        project = await _studio(request).replace_pack(project_id, pack)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.put("/projects/{project_id}/manifest")
async def update_manifest(request: Request, project_id: str, manifest: ModManifest) -> dict[str, Any]:
    try:
        project = await _studio(request).update_manifest(project_id, manifest)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.put("/projects/{project_id}/{section}/{object_id}")
async def upsert_object(
    request: Request,
    project_id: str,
    section: StudioSection,
    object_id: str,
    payload: UpsertObjectRequest,
) -> dict[str, Any]:
    try:
        project = await _studio(request).upsert(project_id, section, object_id, payload.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.delete("/projects/{project_id}/{section}/{object_id}")
async def delete_object(
    request: Request,
    project_id: str,
    section: StudioSection,
    object_id: str,
) -> dict[str, Any]:
    try:
        project = await _studio(request).delete(project_id, section, object_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.post("/projects/{project_id}/maps/{map_id}/nodes")
async def add_map_node(
    request: Request,
    project_id: str,
    map_id: str,
    node: AreaNode,
) -> dict[str, Any]:
    try:
        project = await _studio(request).add_map_node(project_id, map_id, node)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.patch("/projects/{project_id}/maps/{map_id}/nodes/{node_id}")
async def move_map_node(
    request: Request,
    project_id: str,
    map_id: str,
    node_id: str,
    payload: MoveNodeRequest,
) -> dict[str, Any]:
    try:
        project = await _studio(request).move_map_node(
            project_id,
            map_id,
            node_id,
            x=payload.x,
            y=payload.y,
            z=payload.z,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.post("/projects/{project_id}/maps/{map_id}/edges")
async def connect_map_nodes(
    request: Request,
    project_id: str,
    map_id: str,
    edge: AreaEdge,
) -> dict[str, Any]:
    try:
        project = await _studio(request).connect_map_nodes(project_id, map_id, edge)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.post("/projects/{project_id}/validate")
async def validate_project(request: Request, project_id: str) -> dict[str, Any]:
    try:
        result = await _studio(request).validate(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.post("/projects/{project_id}/restore")
async def restore_revision(
    request: Request,
    project_id: str,
    payload: RestoreRevisionRequest,
) -> dict[str, Any]:
    try:
        project = await _studio(request).restore_revision(project_id, payload.revision)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.get("/projects/{project_id}/export")
async def export_project(request: Request, project_id: str) -> dict[str, Any]:
    try:
        pack = await _studio(request).export_pack(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return pack.model_dump(mode="json")


@router.post("/projects/{project_id}/publish")
async def publish_project(request: Request, project_id: str) -> dict[str, Any]:
    try:
        pack = await _studio(request).export_pack(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state = request.app.state.rpg
    item = state.marketplace.publish(pack)
    await state.store.put_json("marketplace.pack", item.id, pack.model_dump(mode="json"))
    await state.store.put_json("marketplace.item", item.id, item.model_dump(mode="json"))
    return item.model_dump(mode="json")
