# tests/test_advanced_engine.py
from __future__ import annotations

import pytest

from dnd_rpg_engine import AdvancedGameEngine
from dnd_rpg_engine.core.commands import CustomCommand, MoveCommand
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, GameConfig, Position, TimeMode
from dnd_rpg_engine.spatial import GraphSpace, GridSpace, TerrainCell


@pytest.mark.asyncio
async def test_advanced_engine_enforces_grid_spatial_authority() -> None:
    engine = await AdvancedGameEngine.create(config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=21))
    grid = GridSpace("arena", 4, 4)
    grid.set_terrain((1, 0), TerrainCell(blocks_movement=True, blocks_los=True))
    engine.register_spatial_space(grid)
    hero = Entity(
        id="hero",
        name="Hero",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        position=Position(area_id="arena", x=0, y=0),
        components={"spatial": {"space_id": "arena"}, "movement": {"budget": 6.0, "units_per_second": 1.5}},
    )
    await engine.add_entity(hero)
    grid.place("hero", (0, 0))

    with pytest.raises(ValueError, match="authoritative grid path|blocked|occupied"):
        await engine.dispatch(MoveCommand(actor_id="hero", x=1, y=0))

    result = await engine.dispatch(MoveCommand(actor_id="hero", x=0, y=1))
    assert grid.occupants["hero"] == (0, 1)
    assert any(event.type == "entity.moved" for event in result.events)


@pytest.mark.asyncio
async def test_advanced_engine_supports_graph_move_through_custom_command() -> None:
    engine = await AdvancedGameEngine.create(config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=22))
    graph = GraphSpace("world")
    graph.add_node("village")
    graph.add_node("forest")
    graph.add_edge("village", "forest", cost=3.0)
    engine.register_spatial_space(graph)
    hero = Entity(
        id="hero",
        name="Hero",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        position=Position(area_id="world", node_id="village"),
        components={"spatial": {"space_id": "world"}, "movement": {"units_per_second": 1.5}},
    )
    await engine.add_entity(hero)
    graph.place("hero", "village")

    result = await engine.dispatch(
        CustomCommand(
            actor_id="hero",
            name="spatial_move",
            payload={"space_id": "world", "destination": "forest", "budget": 3.0},
        )
    )
    assert graph.occupants["hero"] == "forest"
    assert hero.position.node_id == "forest"
    move_event = next(event for event in result.events if event.type == "entity.moved")
    assert move_event.payload["spatial_mode"] == "graph"
    assert move_event.payload["path"] == ["village", "forest"]


@pytest.mark.asyncio
async def test_advanced_engine_uses_intelligent_actor_planner() -> None:
    engine = await AdvancedGameEngine.create(
        config=GameConfig(time_mode=TimeMode.REAL_TIME, seed=23, pause_when_player_ready=False)
    )
    hero = Entity(
        id="hero",
        name="Hero",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        position=Position(area_id="room", x=1, y=0),
    )
    enemy = Entity(
        id="enemy",
        name="Enemy",
        kind=EntityKind.CREATURE,
        controller=ControllerKind.AI,
        position=Position(area_id="room", x=0, y=0),
        components={"ai": {"target_id": "hero", "action_id": "basic_attack", "hostile": True}},
    )
    await engine.add_entity(hero)
    await engine.add_entity(enemy)

    result = await engine.tick(0.1)
    decision = next(event for event in result.events if event.type == "ai.decision")
    assert decision.actor_id == "enemy"
    assert decision.payload["candidate"] == "attack"
    assert any(event.type == "combat.attack_resolved" and event.actor_id == "enemy" for event in result.events)
    assert enemy.component("agent_memory")["entries"]
