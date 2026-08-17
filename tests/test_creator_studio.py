from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dnd_rpg_engine.adventure.maps import AreaEdge, AreaNode
from dnd_rpg_engine.api.platform import create_platform_app
from dnd_rpg_engine.core.persistence import SQLiteStore
from dnd_rpg_engine.creator.content import ModManifest
from dnd_rpg_engine.creator.studio import CreatorStudio


@pytest.mark.asyncio
async def test_creator_studio_typed_editing_revisions_and_validation(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "studio.sqlite3")
    await store.initialize()
    studio = CreatorStudio(store)
    project = await studio.create_project(
        name="Island Campaign",
        manifest=ModManifest(
            id="island.campaign",
            name="Island Campaign",
            version="1.0.0",
            author="tester",
            license="CC0-1.0",
        ),
    )

    project = await studio.upsert(
        project.id,
        "maps",
        "overworld",
        {
            "name": "Overworld",
            "nodes": {
                "camp": {"id": "camp", "name": "Camp", "x": 100, "y": 100},
                "ruins": {"id": "ruins", "name": "Ruins", "x": 300, "y": 200},
            },
            "edges": [],
        },
    )
    project = await studio.connect_map_nodes(
        project.id,
        "overworld",
        AreaEdge(source="camp", target="ruins", travel_time=2.5),
    )
    project = await studio.move_map_node(project.id, "overworld", "ruins", x=400, y=250)
    project = await studio.upsert(
        project.id,
        "creatures",
        "wolf",
        {
            "name": "Wolf",
            "tier": 1,
            "hp": 11,
            "stats": {"strength": 12, "dexterity": 15},
            "action_ids": ["basic_attack"],
        },
    )
    project = await studio.upsert(
        project.id,
        "campaigns",
        "island",
        {
            "name": "Island",
            "description": "A small campaign",
            "start_area_id": "camp",
            "entity_ids": [],
            "quest_ids": [],
        },
    )

    validation = await studio.validate(project.id)
    assert validation.valid is True
    exported = await studio.export_pack(project.id)
    assert exported.maps["overworld"].nodes["ruins"].x == 400
    assert exported.maps["overworld"].edges[0].travel_time == 2.5
    assert exported.creatures["wolf"].hp == 11

    current_revision = project.revision
    await studio.delete(project.id, "creatures", "wolf")
    restored = await studio.restore_revision(project.id, current_revision)
    assert "wolf" in restored.pack.creatures
    assert restored.revision > current_revision


def test_platform_app_exposes_v25_health_and_studio(tmp_path) -> None:
    app = create_platform_app(str(tmp_path / "platform.sqlite3"), advanced=True)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["version"] == "2.5.0"
        assert health.json()["engine_profile"] == "advanced"

        created = client.post(
            "/api/v1/studio/projects",
            json={
                "name": "Web Project",
                "manifest": {
                    "id": "web.project",
                    "name": "Web Project",
                    "version": "1.0.0",
                    "author": "tester",
                    "license": "CC0-1.0",
                },
            },
        )
        assert created.status_code == 200
        project_id = created.json()["id"]
        fetched = client.get(f"/api/v1/studio/projects/{project_id}")
        assert fetched.status_code == 200
        assert fetched.json()["pack"]["manifest"]["id"] == "web.project"
