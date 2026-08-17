# tests/test_spatial_authority.py
from __future__ import annotations

from dnd_rpg_engine.spatial import (
    AxisAlignedBox,
    ContinuousSpace,
    CoverLevel,
    GraphSpace,
    GridSpace,
    SpatialAuthority,
    TerrainCell,
    Vector3,
)


def test_grid_path_collision_los_cover_and_budget() -> None:
    grid = GridSpace("arena", 6, 6)
    grid.set_terrain((1, 0), TerrainCell(blocks_movement=True, blocks_los=True))
    grid.set_terrain((2, 2), TerrainCell(cover=CoverLevel.HALF))
    grid.place("hero", (0, 0))
    result = grid.validate_move("hero", (3, 0), max_cost=10)
    assert result.allowed is True
    assert (1, 0) not in result.path
    assert grid.line_of_sight((0, 0), (3, 0)) is False
    assert grid.cover_between((0, 2), (4, 2)) is CoverLevel.HALF
    limited = grid.validate_move("hero", (5, 5), max_cost=1)
    assert limited.allowed is False
    assert limited.reason == "movement budget exceeded"


def test_graph_authority_respects_capacity_and_cost() -> None:
    graph = GraphSpace("world")
    graph.add_node("a")
    graph.add_node("b")
    graph.add_node("c", capacity=1)
    graph.add_edge("a", "b", cost=2)
    graph.add_edge("b", "c", cost=3)
    graph.place("hero", "a")
    result = graph.validate_move("hero", "c", max_cost=5)
    assert result.allowed is True
    assert result.path == ["a", "b", "c"]
    assert result.cost == 5


def test_continuous_space_rejects_crossing_obstacle() -> None:
    space = ContinuousSpace(
        "scene",
        dimensions=2,
        minimum=Vector3(x=0, y=0, z=0),
        maximum=Vector3(x=10, y=10, z=0),
    )
    space.add_obstacle(
        AxisAlignedBox(
            minimum=Vector3(x=4, y=0, z=-1),
            maximum=Vector3(x=6, y=10, z=1),
        )
    )
    space.place("hero", Vector3(x=2, y=5, z=0), radius=0.25)
    blocked = space.validate_move("hero", Vector3(x=8, y=5, z=0), max_distance=10)
    assert blocked.allowed is False
    assert "blocking geometry" in str(blocked.reason)
    assert space.line_of_sight(Vector3(x=2, y=5), Vector3(x=8, y=5)) is False


def test_spatial_authority_routes_to_registered_space() -> None:
    authority = SpatialAuthority()
    grid = GridSpace("grid", 3, 3)
    grid.place("hero", (0, 0))
    authority.register(grid)
    result = authority.validate_move("grid", "hero", (1, 1), budget=2)
    assert result.allowed is True
