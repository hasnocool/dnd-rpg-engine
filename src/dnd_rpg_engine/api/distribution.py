from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine import __version__
from dnd_rpg_engine.creator.studio import CreatorStudio
from dnd_rpg_engine.distribution.packages import PackageRelease
from dnd_rpg_engine.distribution.service import ContentDistributionService

router = APIRouter(prefix="/api/v1/distribution", tags=["content-distribution"])


class ResolvePackagesRequest(BaseModel):
    requirements: dict[str, str] = Field(default_factory=dict)
    engine_version: str = __version__
    lock_id: str | None = None


def _service(request: Request) -> ContentDistributionService:
    return ContentDistributionService(request.app.state.rpg.store)


@router.get("/releases")
async def list_releases(request: Request, package_id: str | None = None) -> list[dict[str, Any]]:
    rows = await _service(request).releases(package_id)
    return [row.model_dump(mode="json") for row in rows]


@router.post("/releases")
async def publish_release(request: Request, release: PackageRelease) -> dict[str, Any]:
    try:
        saved = await _service(request).publish_release(release)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return saved.model_dump(mode="json")


@router.post("/resolve")
async def resolve_packages(request: Request, payload: ResolvePackagesRequest) -> dict[str, Any]:
    try:
        resolution = await _service(request).resolve(
            payload.requirements,
            engine_version=payload.engine_version,
            lock_id=payload.lock_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return resolution.model_dump(mode="json")


@router.get("/locks")
async def list_locks(request: Request) -> dict[str, Any]:
    return await _service(request).locks()


@router.post("/studio/{project_id}/publish")
async def publish_studio_project(request: Request, project_id: str) -> dict[str, Any]:
    state = request.app.state.rpg
    studio = CreatorStudio(state.store, validator=state.validator)
    try:
        pack = await studio.export_pack(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    release = await _service(request).publish_pack(pack)
    item = state.marketplace.publish(pack)
    await state.store.put_json("marketplace.pack", item.id, pack.model_dump(mode="json"))
    await state.store.put_json("marketplace.item", item.id, item.model_dump(mode="json"))
    return {
        "marketplace": item.model_dump(mode="json"),
        "release": release.model_dump(mode="json"),
    }
