# tests/test_movement.py
from dnd_rpg_engine.tactical.movement import GridMap, find_path, line_of_sight


def test_grid_path_avoids_blocked_cells() -> None:
    grid = GridMap(id="map", width=5, height=5, blocked={(1, 0), (1, 1)})
    path = find_path(grid, (0, 0), (3, 0))
    assert path[0] == (0, 0)
    assert path[-1] == (3, 0)
    assert not any(cell in grid.blocked for cell in path)


def test_line_of_sight_detects_obstacle() -> None:
    grid = GridMap(id="map", width=5, height=5, blocked={(2, 2)})
    assert line_of_sight(grid, (0, 0), (4, 4)) is False
    assert line_of_sight(grid, (0, 0), (4, 0)) is True
