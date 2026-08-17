# src/dnd_rpg_engine/api/platform.py
from __future__ import annotations

import importlib
from typing import Type

from fastapi import FastAPI

from dnd_rpg_engine import __version__
from dnd_rpg_engine.api.hosting import router as hosting_router
from dnd_rpg_engine.api.lifecycle import router as lifecycle_router
from dnd_rpg_engine.api.studio import router as studio_router
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.hosting.postgres import create_store


def create_platform_app(
    database_url: str = "rpg_engine.sqlite3",
    *,
    advanced: bool = True,
) -> FastAPI:
    """Build the v1.8 application while preserving all existing /api/v1 routes.

    The original app module remains compatibility-first and SQLite-oriented.
    This production factory swaps in the storage factory and selected engine
    profile before constructing that same route set, then layers the new
    lifecycle, hosting, and Creator Studio APIs on top.

    One engine profile should be used per process. That is also how production
    workers are deployed, so the module-level compatibility substitution is
    deterministic and does not affect persisted campaign state.
    """

    legacy = importlib.import_module("dnd_rpg_engine.api.app")
    engine_class: Type[GameEngine] = AdvancedGameEngine if advanced else GameEngine
    legacy.SQLiteStore = create_store
    legacy.GameEngine = engine_class
    app = legacy.create_app(database_url)
    app.version = __version__
    app.title = "RPG Engine Platform API"
    app.description = (
        "Authoritative deterministic RPG platform with character lifecycle, "
        "production hosting, reconnect/resume, and Creator Studio."
    )

    # The compatibility app historically hard-coded its health version. Replace
    # only that route while leaving every existing /api/v1 contract untouched.
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
            "database_backend": "postgresql"
            if database_url.startswith(("postgres://", "postgresql://"))
            else "sqlite",
        }

    app.include_router(lifecycle_router)
    app.include_router(hosting_router)
    app.include_router(studio_router)
    return app
