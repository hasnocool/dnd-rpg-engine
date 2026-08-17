from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine import __version__
from dnd_rpg_engine.api.security_helpers import identity_service, require_principal
from dnd_rpg_engine.creator.content import ContentPack
from dnd_rpg_engine.creator.packages import (
    DependencyResolver,
    PackageLock,
    PackagePlanner,
    PackageRelease,
    ResolutionError,
)
from dnd_rpg_engine.security.models import Permission, ResourceRef

router = APIRouter(prefix="/api/v1/packages", tags=["content-packages"])


class PublishReleaseRequest(BaseModel):
    pack: ContentPack
    organization_id: str | None = None
    workspace_id: str | None = None
    migrations_from: set[str] = Field(default_factory=set)
    ruleset_constraints: dict[str, str] = Field(default_factory=dict)


class ResolveRequest(BaseModel):
    requirements: dict[str, str]
    engine_version: str = __version__


class UpgradeRequest(BaseModel):
    current: PackageLock
    target: PackageLock


@router.post("/releases")
async def publish_release(request: Request, payload: PublishReleaseRequest) -> dict[str, Any]:
    principal = require_principal(request)
    service = identity_service(request)
    resource = ResourceRef(
        type="project",
        id=f"package:{payload.pack.manifest.id}",
        project_id=f"package:{payload.pack.manifest.id}",
        owner_user_id=principal.user_id,
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
    )
    try:
        stored_resource = await service.register_resource(principal, resource)
        service.authorize(principal, Permission.STUDIO_PUBLISH, stored_resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    release = PackageRelease.from_pack(payload.pack).model_copy(
        update={
            "migrations_from": payload.migrations_from,
            "ruleset_constraints": payload.ruleset_constraints,
            "metadata": {
                "owner_user_id": principal.user_id,
                "organization_id": payload.organization_id,
                "workspace_id": payload.workspace_id,
            },
        }
    )
    request.app.state.package_repository.add(release)
    await request.app.state.rpg.store.put_json(
        "package.release", f"{release.package_id}@{release.version}", release.model_dump(mode="json")
    )
    await request.app.state.rpg.store.put_json(
        "package.pack", f"{release.package_id}@{release.version}", payload.pack.model_dump(mode="json")
    )
    await service.audit(principal, "package.publish", "package", release.package_id, metadata={"version": release.version})
    return release.model_dump(mode="json")


@router.get("/releases")
async def list_releases(request: Request) -> list[dict[str, Any]]:
    require_principal(request)
    return [
        release.model_dump(mode="json")
        for package_id in sorted(request.app.state.package_repository.releases)
        for release in request.app.state.package_repository.releases[package_id]
    ]


@router.post("/resolve")
async def resolve_packages(request: Request, payload: ResolveRequest) -> dict[str, Any]:
    require_principal(request)
    try:
        lock = DependencyResolver(request.app.state.package_repository).resolve(
            payload.requirements,
            engine_version=payload.engine_version,
        )
    except ResolutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return lock.model_dump(mode="json")


@router.post("/upgrade-plan")
async def plan_upgrade(request: Request, payload: UpgradeRequest) -> dict[str, Any]:
    require_principal(request)
    plan = PackagePlanner(request.app.state.package_repository).plan(payload.current, payload.target)
    return plan.model_dump(mode="json")
