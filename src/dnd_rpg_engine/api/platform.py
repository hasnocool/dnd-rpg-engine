from __future__ import annotations

import importlib
from typing import Type

from fastapi import FastAPI

from dnd_rpg_engine import __version__
from dnd_rpg_engine.api.distribution import router as distribution_router
from dnd_rpg_engine.api.hosting import router as hosting_router
from dnd_rpg_engine.api.knowledge_routes import install_knowledge_scoped_routes
from dnd_rpg_engine.api.lifecycle import router as lifecycle_router
from dnd_rpg_engine.api.rule_studio import router as rule_studio_router
from dnd_rpg_engine.api.studio import router as studio_router
from dnd_rpg_engine.api.world_platform import router as world_platform_router
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.world_engine import WorldPlatformEngine
from dnd_rpg_engine.hosting.postgres import create_store


def create_platform_app(
    database_url: str = "rpg_engine.sqlite3",
    *,
    advanced: bool = True,
) -> FastAPI:
    """Build the current platform while preserving all existing /api/v1 routes.

    The compatibility app remains available through ``advanced=False``. The
    default advanced profile uses ``WorldPlatformEngine`` so v1.2-v3.0 services
    share the same authoritative campaign state and command/event contracts.
    """

    legacy = importlib.import_module("dnd_rpg_engine.api.app")
    engine_class: Type[GameEngine] = WorldPlatformEngine if advanced else GameEngine
    legacy.SQLiteStore = create_store
    legacy.GameEngine = engine_class
    app = legacy.create_app(database_url)
    app.version = __version__
    app.title = "RPG Engine Platform API"
    app.description = (
        "Authoritative deterministic RPG platform with executable content, "
        "campaign orchestration, knowledge-scoped runtime sync, production "
        "hosting, content distribution, reconnect/resume, and Creator Studio."
    )

    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (getattr(route, "path", None) == "/health" and "GET" in getattr(route, "methods", set()))
    ]

    @app.get("/health", tags=["platform"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "engine_profile": "advanced" if advanced else "compatibility",
            "platform_profile": "world" if advanced else "compatibility",
            "database_backend": "postgresql"
            if database_url.startswith(("postgres://", "postgresql://"))
            else "sqlite",
        }

    app.include_router(lifecycle_router)
    app.include_router(hosting_router)
    app.include_router(studio_router)
    app.include_router(rule_studio_router)
    app.include_router(distribution_router)
    app.include_router(world_platform_router)
    if advanced:
        install_knowledge_scoped_routes(app)
    return app
