# tests/test_workbench_api.py
from __future__ import annotations

from fastapi.testclient import TestClient

from dnd_rpg_engine.api.platform import create_platform_app


def _owner_campaign(client: TestClient) -> tuple[str, dict[str, str]]:
    created = client.post(
        "/api/v1/campaigns",
        json={"name": "Workbench Test", "owner_id": "gm", "seed": 7, "time_mode": "hybrid"},
    )
    assert created.status_code == 200
    body = created.json()
    return body["campaign_id"], {"X-RPG-Client-ID": body["owner_client_id"]}


def test_v39_workbench_owner_endpoints(tmp_path) -> None:
    app = create_platform_app(str(tmp_path / "workbench.sqlite3"), advanced=True)
    with TestClient(app) as client:
        campaign_id, headers = _owner_campaign(client)

        session = client.get(f"/api/v1/campaigns/{campaign_id}/workbench/session", headers=headers)
        assert session.status_code == 200
        assert session.json()["owner_id"] == "gm"

        party = client.post(
            f"/api/v1/campaigns/{campaign_id}/workbench/parties",
            headers=headers,
            json={"id": "heroes", "name": "Heroes"},
        )
        assert party.status_code == 200
        assert party.json()["id"] == "heroes"

        catalog = client.get(f"/api/v1/campaigns/{campaign_id}/workbench/catalog", headers=headers)
        assert catalog.status_code == 200
        assert any(row["id"] == "basic_attack" for row in catalog.json()["actions"])
        assert "conditions" in catalog.json()

        tactical = client.get(f"/api/v1/campaigns/{campaign_id}/workbench/tactical", headers=headers)
        assert tactical.status_code == 200
        assert tactical.json()["knowledge_scoped"] is False

        analytics = client.get(f"/api/v1/campaigns/{campaign_id}/workbench/analytics", headers=headers)
        assert analytics.status_code == 200
        assert analytics.json()["campaign_id"] == campaign_id

        replay = client.get(f"/api/v1/campaigns/{campaign_id}/workbench/replay", headers=headers)
        assert replay.status_code == 200
        assert "branching_available" in replay.json()

        content = client.get(f"/api/v1/campaigns/{campaign_id}/workbench/content", headers=headers)
        assert content.status_code == 200
        assert content.json()["packs"] == []

        proposals = client.get(f"/api/v1/campaigns/{campaign_id}/director/proposals", headers=headers)
        assert proposals.status_code == 200
        assert proposals.json()
        proposal_id = proposals.json()[0]["id"]
        accepted = client.post(
            f"/api/v1/campaigns/{campaign_id}/workbench/director/{proposal_id}/accept",
            headers=headers,
            json={"note": "test decision"},
        )
        assert accepted.status_code == 200
        assert accepted.json()["decision"] == "accepted"

        knowledge = client.get(f"/api/v1/campaigns/{campaign_id}/workbench/knowledge", headers=headers)
        assert knowledge.status_code == 200
        assert knowledge.json()["campaign_id"] == campaign_id


def test_player_tactical_projection_is_knowledge_scoped(tmp_path) -> None:
    app = create_platform_app(str(tmp_path / "player.sqlite3"), advanced=True)
    with TestClient(app) as client:
        campaign_id, owner_headers = _owner_campaign(client)
        entity = client.post(
            f"/api/v1/campaigns/{campaign_id}/entities",
            headers=owner_headers,
            json={"id":"hero","name":"Hero","kind":"player","controller":"human","owner_id":"alice"},
        )
        assert entity.status_code == 200
        joined = client.post(
            f"/api/v1/campaigns/{campaign_id}/join",
            json={"user_id":"alice","display_name":"Alice","role":"player","actor_ids":[]},
        )
        assert joined.status_code == 200
        player_headers = {"X-RPG-Client-ID": joined.json()["client_id"]}
        tactical = client.get(
            f"/api/v1/campaigns/{campaign_id}/workbench/tactical?actor_id=hero",
            headers=player_headers,
        )
        assert tactical.status_code == 200
        assert tactical.json()["knowledge_scoped"] is True
        assert "hero" in tactical.json()["entities"]
