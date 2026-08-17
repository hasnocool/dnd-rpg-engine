# tests/test_srd_catalog_store.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from dnd_rpg_engine.rulesets.srd_5_2_1.catalog_store import SRDCatalogStore
from dnd_rpg_engine.rulesets.srd_5_2_1.extended_models import CompiledCatalogManifest


def test_catalog_store_round_trip_and_search(tmp_path) -> None:
    asyncio.run(_catalog_store_round_trip_and_search(tmp_path))


async def _catalog_store_round_trip_and_search(tmp_path) -> None:
    store = SRDCatalogStore(tmp_path / "srd.sqlite3")
    await store.initialize()
    await store.replace_section(
        "spells",
        [
            {"id": "arc_spark", "name": "Arc Spark", "source": {"source_page": 107}},
            {"id": "quiet_light", "name": "Quiet Light", "source": {"source_page": 108}},
        ],
    )
    manifest = CompiledCatalogManifest(
        source_sha256="abc",
        source_pages=364,
        compiled_at=datetime.now(UTC).isoformat(),
        section_counts={"spells": 2},
    )
    await store.put_manifest(manifest)

    assert await store.count("spells") == 2
    assert (await store.get("spells", "arc_spark"))["name"] == "Arc Spark"
    assert [row["id"] for row in await store.search("spells", "Arc")] == ["arc_spark"]
    assert await store.sections() == {"spells": 2}
    restored = await store.manifest()
    assert restored is not None
    assert restored.source_pages == 364
