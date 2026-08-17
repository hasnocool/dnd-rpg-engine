from __future__ import annotations

import importlib
import inspect
import os
from contextlib import asynccontextmanager
from typing import Type

from fastapi import FastAPI

from dnd_rpg_engine import __version__
from dnd_rpg_engine.ai.director import CampaignDirector
from dnd_rpg_engine.api.director import router as director_router
from dnd_rpg_engine.api.distributed import router as distributed_router
from dnd_rpg_engine.api.hosting import router as hosting_router
from dnd_rpg_engine.api.lifecycle import router as lifecycle_router
from dnd_rpg_engine.api.packages import router as packages_router
from dnd_rpg_engine.api.reliable import router as reliable_router
from dnd_rpg_engine.api.security import router as security_router
from dnd_rpg_engine.api.simulation import router as simulation_router
from dnd_rpg_engine.api.studio import router as studio_router
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.creator.packages import PackageRelease, PackageRepository
from dnd_rpg_engine.hosting.postgres import create_store
from dnd_rpg_engine.multiplayer.reliable import ReliableCampaignGateway
from dnd_rpg_engine.security.middleware import IdentityMiddleware
from dnd_rpg_engine.security.service import IdentityService
from dnd_rpg_engine.security.tokens import SessionTokenService
from dnd_rpg_engine.simulation import SimulationLab


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


async def _maybe_close(value: object) -> None:
    close = getattr(value, "close", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result


def create_platform_app(
    database_url: str = "rpg_engine.sqlite3",
    *,
    advanced: bool = True,
    auth_required: bool | None = None,
    auth_secret: str | None = None,
    bootstrap_key: str | None = None,
) -> FastAPI:
    """Build the v2.5 platform while preserving the stable ``/api/v1`` namespace.

    Compatibility mode keeps the original local API usable. Production mode is
    enabled with ``auth_required=True`` (or ``RPG_AUTH_REQUIRED=1``), at which
    point caller-asserted legacy join/command/publish routes are disabled and
    authenticated identity/RBAC plus the reliable transport become the
    authority boundary.
    """

    required = _env_bool("RPG_AUTH_REQUIRED", False) if auth_required is None else auth_required
    resolved_secret = auth_secret or os.environ.get("RPG_AUTH_SECRET")
    if required and not resolved_secret:
        raise RuntimeError("authenticated mode requires RPG_AUTH_SECRET (at least 32 bytes)")
    tokens = SessionTokenService(resolved_secret) if resolved_secret else SessionTokenService.ephemeral()
    identity = IdentityService(tokens)
    resolved_bootstrap = bootstrap_key or os.environ.get("RPG_BOOTSTRAP_KEY")
    if resolved_bootstrap is not None and len(resolved_bootstrap.encode("utf-8")) < 16:
        raise RuntimeError("RPG_BOOTSTRAP_KEY must contain at least 16 bytes")

    legacy = importlib.import_module("dnd_rpg_engine.api.app")
    engine_class: Type[GameEngine] = AdvancedGameEngine if advanced else GameEngine
    legacy.SQLiteStore = create_store
    legacy.GameEngine = engine_class
    app = legacy.create_app(database_url)
    app.version = __version__
    app.title = "RPG Engine Platform API"
    app.description = (
        "Authoritative deterministic RPG application platform with identity/RBAC, "
        "distributed worlds, versioned content, simulation lab, reliable multiplayer, "
        "Campaign Director, Creator Studio, and client SDKs."
    )

    app.state.identity = identity
    app.state.auth_required = required
    app.state.bootstrap_key = resolved_bootstrap
    app.state.platform_engine_class = engine_class
    app.state.client_principals = {}
    app.state.reliable = ReliableCampaignGateway()
    app.state.distributed_worlds = {}
    app.state.package_repository = PackageRepository()
    app.state.simulation_lab = SimulationLab()
    app.state.directors: dict[str, CampaignDirector] = {}

    # The compatibility app historically hard-coded its health version. In
    # authenticated mode its old WebSocket is also removed because WebSocket
    # traffic bypasses BaseHTTPMiddleware; clients use the authenticated reliable
    # socket instead.
    filtered_routes = []
    for route in app.router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set()) or set()
        if path == "/health" and "GET" in methods:
            continue
        if required and path == "/api/v1/campaigns/{campaign_id}/ws":
            continue
        filtered_routes.append(route)
    app.router.routes[:] = filtered_routes

    base_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def platform_lifespan(application: FastAPI):
        async with base_lifespan(application):
            await identity.initialize(application.state.rpg.store)
            stored_releases = await application.state.rpg.store.list_json("package.release")
            for raw in stored_releases.values():
                try:
                    application.state.package_repository.add(PackageRelease.model_validate(raw))
                except Exception:
                    continue
            yield
        await _maybe_close(application.state.rpg.store)

    app.router.lifespan_context = platform_lifespan

    @app.get("/health", tags=["platform"])
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": __version__,
            "engine_profile": "advanced" if advanced else "compatibility",
            "database_backend": "postgresql"
            if database_url.startswith(("postgres://", "postgresql://"))
            else "sqlite",
            "authentication_required": required,
            "capabilities": [
                "character_lifecycle",
                "postgresql_hosting",
                "creator_studio",
                "identity_rbac",
                "distributed_worlds",
                "content_lockfiles",
                "simulation_lab",
                "reliable_multiplayer",
                "campaign_director",
                "client_sdks",
            ],
        }

    app.include_router(security_router)
    app.include_router(lifecycle_router)
    app.include_router(hosting_router)
    app.include_router(studio_router)
    app.include_router(reliable_router)
    app.include_router(distributed_router)
    app.include_router(packages_router)
    app.include_router(simulation_router)
    app.include_router(director_router)
    app.add_middleware(IdentityMiddleware, required=required)
    return app
