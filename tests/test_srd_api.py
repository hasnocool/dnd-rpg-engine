# tests/test_srd_api.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_rpg_engine.api.app import create_app
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog_store import SRDCatalogStore
from dnd_rpg_engine.rulesets.srd_5_2_1.extended_models import CompiledCatalogManifest


def test_read_only_srd_catalog_api(tmp_path: Path) -> None:
    catalog_path = tmp_path / "srd.sqlite3"
    asyncio.run(_seed_catalog(catalog_path))
    app = create_app(str(tmp_path / "api.sqlite3"), str(catalog_path))
    with TestClient(app) as client:
        info = client.get("/api/v1/srd/catalog")
        assert info.status_code == 200
        assert info.json()["sections"]["spells"] == 1
        search = client.get("/api/v1/srd/catalog/spells", params={"q": "Arc"})
        assert search.status_code == 200
        assert search.json()[0]["id"] == "arc_spark"
        budget = client.get("/api/v1/srd/encounter-budget", params={"levels": "3,3,3,3", "difficulty": "moderate"})
        assert budget.status_code == 200
        assert budget.json()["xp_budget"] == 900


def test_srd_catalog_api_is_optional(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "api.sqlite3"))
    with TestClient(app) as client:
        assert client.get("/api/v1/srd/catalog").status_code == 404


async def _seed_catalog(path: Path) -> None:
    store = SRDCatalogStore(path)
    await store.initialize()
    await store.replace_section("spells", [{"id": "arc_spark", "name": "Arc Spark", "source_page": 107}])
    await store.put_manifest(
        CompiledCatalogManifest(
            source_sha256="abc",
            source_pages=364,
            compiled_at=datetime.now(UTC).isoformat(),
            section_counts={"spells": 1},
        )
    )
