# tests/test_creator_v39.py
from __future__ import annotations

import pytest

from dnd_rpg_engine.core.persistence import SQLiteStore
from dnd_rpg_engine.creator.content import ContentPack, ModManifest
from dnd_rpg_engine.creator.studio import CreatorStudio


@pytest.mark.asyncio
async def test_creator_studio_supports_full_pack_and_scenes(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "creator-v39.sqlite3")
    await store.initialize()
    studio = CreatorStudio(store)
    project = await studio.create_project(
        name="Full Pack",
        manifest=ModManifest(id="full.pack", name="Full Pack", author="tester"),
    )

    project = await studio.upsert(project.id, "actions", "slash", {"name":"Slash","damage":"1d8"})
    project = await studio.upsert(project.id, "conditions", "marked", {"name":"Marked","armor_modifier":-1})
    project = await studio.upsert(project.id, "items", "potion", {"name":"Potion","heal":"1d4"})
    project = await studio.upsert(project.id, "scenes", "arrival", {"name":"Arrival","kind":"exploration","next_scene_ids":["ambush"]})
    project = await studio.upsert(project.id, "scenes", "ambush", {"name":"Ambush","kind":"encounter"})
    project = await studio.upsert(project.id, "npcs", "warden", {"role":"warden","knowledge_tags":["gate"]})
    project = await studio.upsert(project.id, "dynamic_events", "bell", {"event_type":"world.bell","predicates":[],"payload":{"public":True}})
    project = await studio.upsert(project.id, "rules_data", "house", {"difficulty":"heroic"})
    project = await studio.upsert(project.id, "assets", "warden_portrait", {"value":"assets/warden.webp"})

    validation = await studio.validate(project.id)
    assert validation.valid is True
    exported = await studio.export_pack(project.id)
    assert exported.actions["slash"].damage == "1d8"
    assert exported.scenes["arrival"].next_scene_ids == ["ambush"]
    assert exported.npcs["warden"].entity_id == "warden"
    assert exported.rules_data["house"]["difficulty"] == "heroic"
    assert exported.assets["warden_portrait"] == "assets/warden.webp"

    round_trip = ContentPack.from_zip_bytes(exported.to_zip_bytes())
    assert round_trip.scenes["ambush"].kind.value == "encounter"
    assert round_trip.assets == exported.assets


@pytest.mark.asyncio
async def test_scene_validation_rejects_missing_next_scene(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "creator-scene-validation.sqlite3")
    await store.initialize()
    studio = CreatorStudio(store)
    project = await studio.create_project(
        name="Broken Flow",
        manifest=ModManifest(id="broken.flow", name="Broken Flow", author="tester"),
    )
    await studio.upsert(project.id, "scenes", "start", {"name":"Start","next_scene_ids":["missing"]})
    validation = await studio.validate(project.id)
    assert validation.valid is False
    assert any("missing next scene" in error for error in validation.errors)
