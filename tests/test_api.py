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
        entity = client.post(
            f"/api/v1/campaigns/{campaign_id}/entities",
            json={"id": "hero", "name": "Hero", "kind": "player", "controller": "human"},
        )
        assert entity.status_code == 200
        state = client.get(f"/api/v1/campaigns/{campaign_id}")
        assert state.status_code == 200
        assert state.json()["campaign"]["entities"]["hero"]["name"] == "Hero"
        assert client.get("/").status_code == 200
        assert client.get("/creator").status_code == 200
