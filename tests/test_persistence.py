# tests/test_persistence.py
import asyncio
from pathlib import Path

from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, GameConfig, TimeMode
from dnd_rpg_engine.core.persistence import SQLiteStore


def test_campaign_state_and_timing_config_round_trip(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = SQLiteStore(tmp_path / "game.sqlite3")
        engine = await GameEngine.create(
            "Persisted",
            config=GameConfig(time_mode=TimeMode.TIMED_TURN_BASED, seed=88, player_decision_timeout_seconds=7),
            store=store,
        )
        await engine.add_entity(
            Entity(id="hero", name="Hero", kind=EntityKind.PLAYER, controller=ControllerKind.HUMAN)
        )
        await engine.tick(0.5)
        campaign_id = engine.state.id
        loaded = await GameEngine.load(campaign_id, store=store)
        assert loaded.state.name == "Persisted"
        assert "hero" in loaded.state.entities
        assert loaded.config.time_mode is TimeMode.TIMED_TURN_BASED
        assert loaded.config.player_decision_timeout_seconds == 7
        assert loaded.state.simulation_time == engine.state.simulation_time
        events = await store.list_events(campaign_id)
        assert any(event.type == "entity.created" for event in events)

    asyncio.run(scenario())
