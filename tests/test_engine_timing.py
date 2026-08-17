# tests/test_engine_timing.py
import asyncio

from dnd_rpg_engine.core.commands import WaitCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import (
    ControllerKind,
    Entity,
    EntityKind,
    GameConfig,
    Position,
    ResourcePool,
    TimeMode,
)


def make_entities() -> tuple[Entity, Entity]:
    hero = Entity(
        id="hero",
        name="Hero",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        resources=ResourcePool(hp=40, max_hp=40),
        position=Position(x=0, y=0),
    )
    rival = Entity(
        id="rival",
        name="Rival",
        kind=EntityKind.CREATURE,
        controller=ControllerKind.AI,
        resources=ResourcePool(hp=40, max_hp=40),
        position=Position(x=1, y=0),
        components={"ai": {"target_id": "hero", "action_id": "basic_attack"}},
    )
    return hero, rival


def test_realtime_enemy_keeps_acting_while_player_is_idle() -> None:
    async def scenario() -> None:
        engine = await GameEngine.create(
            config=GameConfig(time_mode=TimeMode.REAL_TIME, seed=3, pause_when_player_ready=False)
        )
        hero, rival = make_entities()
        await engine.add_entity(hero)
        await engine.add_entity(rival)
        first = await engine.tick(0.1)
        later = await engine.tick(12.5)
        attacks = [event for event in [*first.events, *later.events] if event.type == "combat.attack_resolved" and event.actor_id == "rival"]
        assert len(attacks) >= 2

    asyncio.run(scenario())


def test_hybrid_decision_window_defers_enemy_then_releases_timeline() -> None:
    async def scenario() -> None:
        engine = await GameEngine.create(
            config=GameConfig(
                time_mode=TimeMode.HYBRID,
                seed=4,
                pause_when_player_ready=True,
                player_decision_timeout_seconds=2,
            )
        )
        hero, rival = make_entities()
        await engine.add_entity(hero)
        await engine.add_entity(rival)
        before = await engine.tick(0.1)
        assert not any(event.type == "combat.attack_resolved" and event.actor_id == "rival" for event in before.events)
        during = await engine.tick(1.0)
        assert not any(event.type == "combat.attack_resolved" and event.actor_id == "rival" for event in during.events)
        released = await engine.tick(1.1)
        assert any(event.type == "combat.attack_resolved" and event.actor_id == "rival" for event in released.events)
        later = await engine.tick(7.0)
        assert any(event.type == "combat.attack_resolved" and event.actor_id == "rival" for event in later.events)

    asyncio.run(scenario())


def test_strict_turn_mode_does_not_advance_from_wall_clock() -> None:
    async def scenario() -> None:
        engine = await GameEngine.create(config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=5))
        hero, rival = make_entities()
        await engine.add_entity(hero)
        await engine.add_entity(rival)
        await engine.start_encounter(["hero", "rival"])
        hp = hero.resources.hp
        sim = engine.state.simulation_time
        await engine.tick(999)
        assert hero.resources.hp == hp
        assert engine.state.simulation_time == sim
        # Once the human acts, the engine advances the timeline to the next human decision point.
        if "hero" in engine.state_payload()["ready_humans"]:
            result = await engine.dispatch(WaitCommand(actor_id="hero"))
            assert result.simulation_time >= sim

    asyncio.run(scenario())
