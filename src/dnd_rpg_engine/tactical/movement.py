# src/dnd_rpg_engine/tactical/movement.py
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field


@dataclass(slots=True)
class GridMap:
    id: str
    width: int
    height: int
    blocked: set[tuple[int, int]] = field(default_factory=set)
    difficult: set[tuple[int, int]] = field(default_factory=set)

    def in_bounds(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def walkable(self, cell: tuple[int, int]) -> bool:
        return self.in_bounds(cell) and cell not in self.blocked

    def neighbors(self, cell: tuple[int, int]) -> list[tuple[int, int]]:
        x, y = cell
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [p for p in candidates if self.walkable(p)]

    def movement_cost(self, cell: tuple[int, int]) -> float:
        return 2.0 if cell in self.difficult else 1.0


def find_path(grid: GridMap, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    if not grid.walkable(start) or not grid.walkable(goal):
        return []
    frontier: list[tuple[float, tuple[int, int]]] = [(0.0, start)]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost_so_far: dict[tuple[int, int], float] = {start: 0.0}

    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal:
            break
        for nxt in grid.neighbors(current):
            new_cost = cost_so_far[current] + grid.movement_cost(nxt)
            if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                cost_so_far[nxt] = new_cost
                priority = new_cost + abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1])
                heapq.heappush(frontier, (priority, nxt))
                came_from[nxt] = current

    if goal not in came_from:
        return []
    path: list[tuple[int, int]] = []
    cursor: tuple[int, int] | None = goal
    while cursor is not None:
        path.append(cursor)
        cursor = came_from[cursor]
    return list(reversed(path))


def line_of_sight(grid: GridMap, start: tuple[int, int], end: tuple[int, int]) -> bool:
    """Integer Bresenham LOS against blocked cells."""
    x0, y0 = start
    x1, y1 = end
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        if (x0, y0) not in {start, end} and (x0, y0) in grid.blocked:
            return False
        if (x0, y0) == (x1, y1):
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def euclidean_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.dist(a, b)
