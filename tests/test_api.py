# tests/test_api.py
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_rpg_engine.api.app import create_app


def test_campaign_api_and_static_browser(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "api.sqlite3"))
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        created = client.post(
            "/api/v1/campaigns",
            json={"name": "API Test", "owner_id": "u1", "seed": 1, "time_mode": "turn_based", "player_decision_timeout_seconds": 5},
        )
        assert created.status_code == 200
        campaign_id = created.json()["campaign_id"]
        owner_client_id = created.json()["owner_client_id"]
        unauthenticated_entity = client.post(
            f"/api/v1/campaigns/{campaign_id}/entities",
            json={"id": "blocked", "name": "Blocked", "kind": "player", "controller": "human"},
        )
        assert unauthenticated_entity.status_code == 401
        entity = client.post(
            f"/api/v1/campaigns/{campaign_id}/entities",
            headers={"X-RPG-Client-ID": owner_client_id},
            json={"id": "hero", "name": "Hero", "kind": "player", "controller": "human", "owner_id": "u1"},
        )
        assert entity.status_code == 200
        unauthenticated_command = client.post(
            f"/api/v1/campaigns/{campaign_id}/commands",
            json={"command": {"type": "wait", "actor_id": "hero"}},
        )
        assert unauthenticated_command.status_code == 401
        owner_command = client.post(
            f"/api/v1/campaigns/{campaign_id}/commands",
            headers={"X-RPG-Client-ID": owner_client_id},
            json={"command": {"type": "wait", "actor_id": "hero"}},
        )
        assert owner_command.status_code == 200
        state = client.get(f"/api/v1/campaigns/{campaign_id}")
        assert state.status_code == 200
        assert state.json()["campaign"]["entities"]["hero"]["name"] == "Hero"
        assert client.get("/").status_code == 200
        assert client.get("/creator").status_code == 200
