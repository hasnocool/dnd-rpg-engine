# tests/test_creator_studio.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dnd_rpg_engine.api.platform import create_platform_app
from dnd_rpg_engine.core.persistence import SQLiteStore
from dnd_rpg_engine.creator.content import ModManifest
from dnd_rpg_engine.creator.studio import CreatorStudio


@pytest.mark.asyncio
async def test_creator_studio_typed_editing_revision_and_export(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "studio.sqlite3")
    await store.initialize()
    studio = CreatorStudio(store)
    project = await studio.create_project(
        name="Northern Marches",
        manifest=ModManifest(id="northern.marches", name="Northern Marches", author="tester"),
    )

    project = await studio.upsert(
        project.id,
        "maps",
        "overworld",
        {"name": "Overworld", "nodes": {}, "edges": []},
    )
    project = await studio.add_map_node(
        project.id,
        "overworld",
        {"id": "town", "name": "Town", "x": 100, "y": 100},
    )
    project = await studio.add_map_node(
        project.id,
        "overworld",
        {"id": "ruins", "name": "Ruins", "x": 350, "y": 180},
    )
    project = await studio.connect_map_nodes(
        project.id,
        "overworld",
        {"source": "town", "target": "ruins", "travel_time": 2.5, "bidirectional": True},
    )
    project = await studio.move_map_node(project.id, "overworld", "ruins", x=400, y=200)
    project = await studio.upsert(
        project.id,
        "creatures",
        "wolf",
        {"name": "Wolf", "tier": 1, "hp": 11, "actions": ["basic_attack"], "ai_profile": "hostile_basic"},
    )
    project = await studio.upsert(
        project.id,
        "rules",
        "campaign_rules",
        {"name": "Campaign Rules", "settings": {"round_seconds": 6}},
    )
    project = await studio.upsert(
        project.id,
        "campaigns",
        "main",
        {
            "name": "Northern Marches",
            "start_map_id": "overworld",
            "active_rule_id": "campaign_rules",
            "flags": {"chapter": 1},
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


def test_platform_app_exposes_v18_health_and_studio(tmp_path) -> None:
    app = create_platform_app(str(tmp_path / "platform.sqlite3"), advanced=True)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["version"] == "1.8.0"
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
