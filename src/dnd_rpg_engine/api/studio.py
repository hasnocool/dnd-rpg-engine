from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.adventure.maps import AreaEdge, AreaNode
from dnd_rpg_engine.creator.content import ContentPack, ModManifest
from dnd_rpg_engine.creator.studio import CreatorStudio, StudioProject, StudioSection
from dnd_rpg_engine.security.models import Permission, ResourceRef, ScopeType

router = APIRouter(prefix="/api/v1/studio", tags=["creator-studio"])


class CreateProjectRequest(BaseModel):
    name: str
    manifest: ModManifest
    organization_id: str | None = None
    workspace_id: str | None = None


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


def _principal(request: Request):
    return getattr(request.state, "principal", None)


async def _project_resource(
    request: Request,
    project: StudioProject,
    permission: Permission,
) -> ResourceRef | None:
    principal = _principal(request)
    if principal is None:
        if getattr(request.app.state, "auth_required", False):
            raise HTTPException(status_code=401, detail="authenticated session required")
        return None
    service = request.app.state.identity
    key = service.resource_key(ScopeType.PROJECT, project.id)
    resource = service.resources.get(key)
    if resource is None:
        if project.owner_user_id is None:
            raise HTTPException(
                status_code=409,
                detail="legacy Studio project has no tenant owner; migrate ownership before authenticated editing",
            )
        resource = ResourceRef(
            type="project",
            id=project.id,
            project_id=project.id,
            owner_user_id=project.owner_user_id,
            organization_id=project.organization_id,
            workspace_id=project.workspace_id,
        )
        if project.owner_user_id == principal.user_id:
            try:
                resource = await service.register_resource(principal, resource)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
    if resource is None:
        raise HTTPException(status_code=403, detail="Studio project is not registered to this tenant")
    try:
        service.authorize(principal, permission, resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return resource


async def _load_authorized(request: Request, project_id: str, permission: Permission) -> StudioProject:
    try:
        project = await _studio(request).get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await _project_resource(request, project, permission)
    return project


@router.post("/projects")
async def create_project(request: Request, payload: CreateProjectRequest) -> dict[str, Any]:
    principal = _principal(request)
    if principal is None and getattr(request.app.state, "auth_required", False):
        raise HTTPException(status_code=401, detail="authenticated session required")
    service = getattr(request.app.state, "identity", None)
    organization_id = payload.organization_id
    workspace_id = payload.workspace_id
    if principal is not None and workspace_id:
        workspace = service.workspaces.get(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="workspace not found")
        if organization_id and organization_id != workspace.organization_id:
            raise HTTPException(status_code=422, detail="workspace does not belong to organization")
        organization_id = workspace.organization_id
        parent = service.resource_for_scope(ScopeType.WORKSPACE, workspace_id)
        try:
            service.authorize(principal, Permission.STUDIO_WRITE, parent)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    elif principal is not None and organization_id:
        if organization_id not in service.organizations:
            raise HTTPException(status_code=404, detail="organization not found")
        parent = service.resource_for_scope(ScopeType.ORGANIZATION, organization_id)
        try:
            service.authorize(principal, Permission.STUDIO_WRITE, parent)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    project = await _studio(request).create_project(
        name=payload.name,
        manifest=payload.manifest,
        owner_user_id=principal.user_id if principal is not None else None,
        organization_id=organization_id,
        workspace_id=workspace_id,
    )
    if principal is not None:
        try:
            await service.register_resource(
                principal,
                ResourceRef(
                    type="project",
                    id=project.id,
                    project_id=project.id,
                    owner_user_id=principal.user_id,
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                ),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        await service.audit(principal, "studio.project.create", "project", project.id)
    return project.model_dump(mode="json")


@router.get("/projects")
async def list_projects(request: Request) -> list[dict[str, Any]]:
    raw = await request.app.state.rpg.store.list_json(CreatorStudio.project_namespace)
    projects = [StudioProject.model_validate(value) for value in raw.values()]
    principal = _principal(request)
    if principal is None:
        if getattr(request.app.state, "auth_required", False):
            raise HTTPException(status_code=401, detail="authenticated session required")
        return [value.model_dump(mode="json") for value in sorted(projects, key=lambda item: (item.name, item.id))]
    service = request.app.state.identity
    visible: list[StudioProject] = []
    for project in projects:
        resource = service.resources.get(service.resource_key(ScopeType.PROJECT, project.id))
        if resource and service.can(principal, Permission.STUDIO_READ, resource):
            visible.append(project)
    return [value.model_dump(mode="json") for value in sorted(visible, key=lambda item: (item.name, item.id))]


@router.get("/projects/{project_id}")
async def get_project(request: Request, project_id: str) -> dict[str, Any]:
    project = await _load_authorized(request, project_id, Permission.STUDIO_READ)
    return project.model_dump(mode="json")


@router.put("/projects/{project_id}/pack")
async def replace_pack(request: Request, project_id: str, pack: ContentPack) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_WRITE)
    project = await _studio(request).replace_pack(project_id, pack)
    return project.model_dump(mode="json")


@router.put("/projects/{project_id}/manifest")
async def update_manifest(request: Request, project_id: str, manifest: ModManifest) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_WRITE)
    project = await _studio(request).update_manifest(project_id, manifest)
    return project.model_dump(mode="json")


@router.put("/projects/{project_id}/{section}/{object_id}")
async def upsert_object(
    request: Request,
    project_id: str,
    section: StudioSection,
    object_id: str,
    payload: UpsertObjectRequest,
) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_WRITE)
    try:
        project = await _studio(request).upsert(project_id, section, object_id, payload.payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.delete("/projects/{project_id}/{section}/{object_id}")
async def delete_object(request: Request, project_id: str, section: StudioSection, object_id: str) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_WRITE)
    try:
        project = await _studio(request).delete(project_id, section, object_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.post("/projects/{project_id}/maps/{map_id}/nodes")
async def add_map_node(request: Request, project_id: str, map_id: str, node: AreaNode) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_WRITE)
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
    await _load_authorized(request, project_id, Permission.STUDIO_WRITE)
    try:
        project = await _studio(request).move_map_node(project_id, map_id, node_id, x=payload.x, y=payload.y, z=payload.z)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.post("/projects/{project_id}/maps/{map_id}/edges")
async def connect_map_nodes(request: Request, project_id: str, map_id: str, edge: AreaEdge) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_WRITE)
    try:
        project = await _studio(request).connect_map_nodes(project_id, map_id, edge)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.post("/projects/{project_id}/validate")
async def validate_project(request: Request, project_id: str) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_READ)
    result = await _studio(request).validate(project_id)
    return result.model_dump(mode="json")


@router.post("/projects/{project_id}/restore")
async def restore_revision(request: Request, project_id: str, payload: RestoreRevisionRequest) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_WRITE)
    try:
        project = await _studio(request).restore_revision(project_id, payload.revision)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump(mode="json")


@router.get("/projects/{project_id}/export")
async def export_project(request: Request, project_id: str) -> dict[str, Any]:
    await _load_authorized(request, project_id, Permission.STUDIO_READ)
    try:
        pack = await _studio(request).export_pack(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return pack.model_dump(mode="json")


@router.post("/projects/{project_id}/publish")
async def publish_project(request: Request, project_id: str) -> dict[str, Any]:
    project = await _load_authorized(request, project_id, Permission.STUDIO_PUBLISH)
    try:
        pack = await _studio(request).export_pack(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state = request.app.state.rpg
    item = state.marketplace.publish(pack)
    await state.store.put_json("marketplace.pack", item.id, pack.model_dump(mode="json"))
    await state.store.put_json("marketplace.item", item.id, item.model_dump(mode="json"))
    principal = _principal(request)
    if principal is not None:
        await request.app.state.identity.audit(
            principal,
            "studio.project.publish",
            "project",
            project.id,
            metadata={"marketplace_item_id": item.id},
        )
    return item.model_dump(mode="json")
