from __future__ import annotations

from fastapi.testclient import TestClient

from dnd_rpg_engine.api.platform import create_platform_app
from dnd_rpg_engine.adventure.npcs import NPCProfile


def test_character_creator_edit_and_npc_crud(tmp_path) -> None:
    app = create_platform_app(str(tmp_path / "workshop.sqlite3"), advanced=True)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/campaigns",
            json={"name": "Workshop", "owner_id": "gm", "seed": 7, "time_mode": "hybrid"},
        ).json()
        campaign_id = created["campaign_id"]
        headers = {"X-RPG-Client-ID": created["owner_client_id"]}

        catalog = client.get(f"/api/v1/campaigns/{campaign_id}/characters/catalog")
        assert catalog.status_code == 200
        classes = catalog.json()["classes"]
        assert "fighter" in classes
        assert "wizard" in classes
        assert classes["fighter"]["hit_die"] == 10

        hero = client.post(
            f"/api/v1/campaigns/{campaign_id}/characters",
            headers=headers,
            json={
                "name": "Aria",
                "class_id": "fighter",
                "owner_id": "player-1",
                "species_id": "human",
                "background_id": "wanderer",
                "stats": {"strength": 12, "dexterity": 14, "constitution": 13, "intelligence": 10, "wisdom": 11, "charisma": 15},
                "tags": ["hero"],
            },
        )
        assert hero.status_code == 200
        actor_id = hero.json()["character"]["id"]

        edited = client.patch(
            f"/api/v1/campaigns/{campaign_id}/characters/{actor_id}",
            headers=headers,
            json={
                "name": "Aria Stoneward",
                "background_id": "guide",
                "appearance": {"description": "Weathered travel cloak", "portrait": "assets/aria.png"},
            },
        )
        assert edited.status_code == 200
        assert edited.json()["entity"]["name"] == "Aria Stoneward"
        assert edited.json()["progress"]["background_id"] == "guide"
        assert edited.json()["entity"]["components"]["appearance"]["portrait"] == "assets/aria.png"

        listed = client.get(f"/api/v1/campaigns/{campaign_id}/characters")
        assert any(row["id"] == actor_id for row in listed.json())

        npc = client.post(
            f"/api/v1/campaigns/{campaign_id}/npcs",
            headers=headers,
            json={
                "entity_id": "erin",
                "name": "Erin Vale",
                "role": "blacksmith",
                "stats": {"strength": 14, "dexterity": 10, "constitution": 13, "intelligence": 11, "wisdom": 12, "charisma": 10},
                "resources": {"hp": 18, "max_hp": 18, "temp_hp": 0, "energy": 0, "max_energy": 0},
                "position": {"area_id": "town", "x": 2, "y": 4, "z": 0},
                "tags": ["merchant"],
                "appearance": {"description": "Soot-marked apron"},
                "ai_profile": "ambient_npc",
                "knowledge_tags": ["blacksmithing"],
            },
        )
        assert npc.status_code == 200
        assert npc.json()["entity"]["kind"] == "npc"
        assert NPCProfile.model_validate(npc.json()["profile"]).to_entity().name == "Erin Vale"

        updated = client.patch(
            f"/api/v1/campaigns/{campaign_id}/npcs/erin",
            headers=headers,
            json={**npc.json()["profile"], "role": "master_blacksmith", "faction_id": "smiths_guild"},
        )
        assert updated.status_code == 200
        assert updated.json()["profile"]["role"] == "master_blacksmith"
        assert updated.json()["entity"]["components"]["faction"]["id"] == "smiths_guild"

        removed = client.delete(f"/api/v1/campaigns/{campaign_id}/npcs/erin", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["deleted"] is True


def test_hero_workshop_static_route_and_contract(tmp_path) -> None:
    app = create_platform_app(str(tmp_path / "hero.sqlite3"), advanced=True)
    with TestClient(app) as client:
        page = client.get("/hero")
        assert page.status_code == 200
        assert "Create Character / Hero" in page.text
        assert "NPC Manager" in page.text
        script = client.get("/static/hero.js")
        assert script.status_code == 200
        for fragment in ("/characters/catalog", "/characters", "/npcs", 'method:"PATCH"', 'method:"DELETE"'):
            assert fragment in script.text
