from fastapi.testclient import TestClient

from dnd_rpg_engine.api.app import create_app


def test_v2_playable_campaign_bootstrap(tmp_path):
    app = create_app(str(tmp_path / "engine.sqlite3"))
    with TestClient(app) as client:
        response = client.post("/api/v2/playable-campaigns", json={
            "campaign_name": "Playable",
            "owner_id": "owner",
            "seed": 5,
            "time_mode": "turn_based",
            "character": {
                "name": "Hero",
                "class_id": "fighter",
                "species_id": "human",
                "background_id": "soldier",
                "level": 1,
            },
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["character"]["class_id"] == "fighter"
        cid, actor, owner_client = data["campaign_id"], data["character_id"], data["owner_client_id"]
        sheet = client.get(f"/api/v1/campaigns/{cid}/characters/{actor}")
        assert sheet.status_code == 200
        assert "end_turn" in sheet.json()["legal_actions"]["available"]
        lobby = client.get(f"/api/v1/campaigns/{cid}/lobby")
        assert lobby.status_code == 200
        assert lobby.json()["campaign_id"] == cid
        xp = client.post(
            f"/api/v1/campaigns/{cid}/characters/{actor}/xp",
            headers={"X-RPG-Client-ID": owner_client}, json={"amount": 300},
        )
        assert xp.status_code == 200
        assert xp.json()["character"]["level"] == 2
        exported = client.get(f"/api/v1/campaigns/{cid}/export")
        assert exported.status_code == 200
        assert exported.json()["sha256"]
