from __future__ import annotations

from fastapi.testclient import TestClient

from dnd_rpg_engine.api.app import create_app
from dnd_rpg_engine.api.platform import create_platform_app


def _assert_hero_route(app) -> None:
    with TestClient(app) as client:
        response = client.get("/hero")
        assert response.status_code == 200
        assert "Create Character / Hero" in response.text
        assert "NPC Manager" in response.text


def test_hero_route_is_available_on_common_app(tmp_path) -> None:
    _assert_hero_route(create_app(str(tmp_path / "common.sqlite3")))


def test_hero_route_is_available_on_platform_app(tmp_path) -> None:
    _assert_hero_route(create_platform_app(str(tmp_path / "platform.sqlite3"), advanced=True))
