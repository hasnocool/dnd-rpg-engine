# tests/test_workbench_static.py
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "dnd_rpg_engine" / "web" / "static"


def test_workbench_exposes_primary_views() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for view_id in (
        "view-library",
        "view-gm",
        "view-player",
        "view-world",
        "view-journal",
        "campaign-list",
        "gm-map",
        "player-map",
        "events",
    ):
        assert f'id="{view_id}"' in html


def test_workbench_uses_authoritative_platform_routes() -> None:
    script = "\n".join(
        (STATIC / filename).read_text(encoding="utf-8")
        for filename in (
            "app.js",
            "workbench-core.js",
            "workbench-render.js",
            "workbench-session.js",
        )
    )
    expected_fragments = (
        "/api/v1/campaigns",
        "/commands",
        "/timing",
        "/scenes/",
        "/director/proposals",
        "/runtime?actor_id=",
        "/events?after=0",
        "/ws?client_id=",
    )
    for fragment in expected_fragments:
        assert fragment in script


def test_player_view_is_described_as_knowledge_scoped() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "knowledge scoped" in html.lower()
