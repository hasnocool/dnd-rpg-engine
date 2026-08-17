# tests/test_workbench_static.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "dnd_rpg_engine" / "web" / "static"

WORKBENCH_SCRIPTS = (
    "workbench-v39.js",
    "workbench-v39-utils.js",
    "workbench-v39-lobby.js",
    "workbench-v39-tactical.js",
    "workbench-v39-character.js",
    "workbench-v39-intelligence.js",
    "workbench-v39-operations.js",
)


def test_workbench_exposes_v31_through_v39_views() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for view_id in (
        "view-library", "view-lobby", "view-gm", "view-player", "view-tactical",
        "view-character", "view-visual", "view-director", "view-knowledge",
        "view-automation", "view-analytics", "view-replay", "view-content",
        "view-world", "view-journal", "tactical-map", "character-sheet",
        "knowledge-matrix", "replay-slider", "content-installed",
    ):
        assert f'id="{view_id}"' in html
    assert "/static/workbench-v39.js" in html


def test_workbench_uses_authoritative_platform_routes() -> None:
    script = "\n".join((STATIC / filename).read_text(encoding="utf-8") for filename in WORKBENCH_SCRIPTS)
    expected_fragments = (
        "/api/v1/campaigns", "/commands", "/timing", "/scenes/",
        "/director/proposals", "/runtime", "/events?after=0", "/ws?client_id=",
        "/workbench/session", "/workbench/tactical", "/workbench/analytics",
        "/workbench/knowledge", "/workbench/replay", "/workbench/content",
        "/characters/", "/distribution/releases", "/distribution/resolve",
    )
    for fragment in expected_fragments:
        assert fragment in script


def test_player_views_keep_knowledge_authority_boundary() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    script = "\n".join((STATIC / filename).read_text(encoding="utf-8") for filename in WORKBENCH_SCRIPTS)
    assert "knowledge scoped" in html.lower()
    assert "actor_id=" in script
    assert "server authoritative" in html.lower()
    assert "calculate trusted" not in script.lower()


def test_creator_exposes_full_content_pack_and_scene_flow() -> None:
    html = (STATIC / "creator.html").read_text(encoding="utf-8")
    script = (STATIC / "creator-v39.js").read_text(encoding="utf-8")
    for section in (
        "scenes", "actions", "conditions", "items", "dialogues", "npcs",
        "shops", "factions", "schedules", "dynamic_events", "personalities",
        "encounters", "rules_data", "assets",
    ):
        assert f'data-v39-section="{section}"' in html
    assert "next_scene_ids" in script
    assert "v39-scene-svg" in html
