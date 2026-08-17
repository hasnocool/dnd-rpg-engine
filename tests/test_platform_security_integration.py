from __future__ import annotations

from fastapi.testclient import TestClient

from dnd_rpg_engine.api.platform import create_platform_app


BOOTSTRAP = "test-bootstrap-key-123456"
SECRET = "test-auth-secret-" + ("x" * 48)


def headers(token: str, *, client_id: str | None = None) -> dict[str, str]:
    value = {"Authorization": f"Bearer {token}"}
    if client_id:
        value["X-RPG-Client-ID"] = client_id
    return value


def bootstrap(client: TestClient, user_id: str, display_name: str) -> str:
    response = client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-RPG-Bootstrap-Key": BOOTSTRAP},
        json={"user_id": user_id, "display_name": display_name},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_authenticated_platform_enforces_tenancy_transport_and_studio(tmp_path) -> None:
    app = create_platform_app(
        str(tmp_path / "platform.sqlite3"),
        auth_required=True,
        auth_secret=SECRET,
        bootstrap_key=BOOTSTRAP,
    )
    with TestClient(app) as client:
        owner_token = bootstrap(client, "owner", "Owner")
        player_token = bootstrap(client, "player", "Player")

        assert client.get("/api/v1/campaigns").status_code == 401
        assert client.post(
            "/api/v1/campaigns",
            headers=headers(owner_token),
            json={"name": "legacy"},
        ).status_code == 409

        organization = client.post(
            "/api/v1/secure/organizations",
            headers=headers(owner_token),
            json={"name": "Guild"},
        )
        assert organization.status_code == 200, organization.text
        organization_id = organization.json()["id"]
        workspace = client.post(
            f"/api/v1/secure/organizations/{organization_id}/workspaces",
            headers=headers(owner_token),
            json={"name": "World"},
        )
        assert workspace.status_code == 200, workspace.text
        workspace_id = workspace.json()["id"]

        created = client.post(
            "/api/v1/secure/campaigns",
            headers=headers(owner_token),
            json={
                "name": "Secure Campaign",
                "seed": 7,
                "time_mode": "turn_based",
                "organization_id": organization_id,
                "workspace_id": workspace_id,
            },
        )
        assert created.status_code == 200, created.text
        campaign_id = created.json()["campaign_id"]
        owner_client_id = created.json()["owner_client_id"]

        grant = client.post(
            "/api/v1/secure/memberships",
            headers=headers(owner_token),
            json={
                "user_id": "player",
                "scope_type": "campaign",
                "scope_id": campaign_id,
                "role": "player",
            },
        )
        assert grant.status_code == 200, grant.text

        joined = client.post(
            f"/api/v1/secure/campaigns/{campaign_id}/join",
            headers=headers(player_token),
            json={},
        )
        assert joined.status_code == 200, joined.text
        player_client_id = joined.json()["client_id"]

        character = client.post(
            f"/api/v1/campaigns/{campaign_id}/characters",
            headers=headers(owner_token, client_id=owner_client_id),
            json={"name": "Player Hero", "class_id": "adventurer", "owner_id": "player"},
        )
        assert character.status_code == 200, character.text
        actor_id = character.json()["character"]["id"]

        reliable = client.post(
            f"/api/v1/reliable/campaigns/{campaign_id}/commands",
            headers=headers(player_token),
            json={
                "client_id": player_client_id,
                "client_sequence": 1,
                "command": {"type": "wait", "actor_id": actor_id, "command_id": "wait-1"},
            },
        )
        assert reliable.status_code == 200, reliable.text
        first_ack = reliable.json()
        assert first_ack["duplicate"] is False

        duplicate = client.post(
            f"/api/v1/reliable/campaigns/{campaign_id}/commands",
            headers=headers(player_token),
            json={
                "client_id": player_client_id,
                "client_sequence": 1,
                "command": {"type": "wait", "actor_id": actor_id, "command_id": "wait-1"},
            },
        )
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["duplicate"] is True
        assert duplicate.json()["engine_version"] == first_ack["engine_version"]

        stolen_client = client.post(
            f"/api/v1/reliable/campaigns/{campaign_id}/commands",
            headers=headers(player_token),
            json={
                "client_id": owner_client_id,
                "client_sequence": 1,
                "command": {"type": "wait", "actor_id": actor_id},
            },
        )
        assert stolen_client.status_code == 403

        legacy_command = client.post(
            f"/api/v1/campaigns/{campaign_id}/commands",
            headers=headers(player_token, client_id=player_client_id),
            json={"command": {"type": "wait", "actor_id": actor_id}},
        )
        assert legacy_command.status_code == 409

        project = client.post(
            "/api/v1/studio/projects",
            headers=headers(owner_token),
            json={
                "name": "Private Project",
                "manifest": {"id": "private-project", "name": "Private Project", "author": "Owner"},
                "organization_id": organization_id,
                "workspace_id": workspace_id,
            },
        )
        assert project.status_code == 200, project.text
        project_id = project.json()["id"]
        assert client.get(
            f"/api/v1/studio/projects/{project_id}", headers=headers(owner_token)
        ).status_code == 200
        assert client.get(
            f"/api/v1/studio/projects/{project_id}", headers=headers(player_token)
        ).status_code == 403

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["version"] == "2.5.0"
        assert health.json()["authentication_required"] is True
