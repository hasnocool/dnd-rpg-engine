# src/dnd_rpg_engine/spatial/world.py
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import count
from typing import Any

from pydantic import BaseModel, Field


class SpatialMode(StrEnum):
    GRAPH = "graph"
    GRID = "grid"
    CONTINUOUS_2D = "continuous_2d"
    CONTINUOUS_3D = "continuous_3d"


class CoverLevel(StrEnum):
    NONE = "none"
    HALF = "half"
    THREE_QUARTERS = "three_quarters"
    FULL = "full"


class Vector3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: "Vector3") -> float:
        return math.dist((self.x, self.y, self.z), (other.x, other.y, other.z))


class MoveValidation(BaseModel):
    allowed: bool
    reason: str | None = None
    cost: float = 0.0
    path: list[Any] = Field(default_factory=list)


@dataclass(slots=True)
class TerrainCell:
    movement_cost: float = 1.0
    blocks_movement: bool = False
    blocks_los: bool = False
    cover: CoverLevel = CoverLevel.NONE
    tags: set[str] = field(default_factory=set)


class GraphSpace:
    mode = SpatialMode.GRAPH

    def __init__(self, space_id: str) -> None:
        self.id = space_id
        self.nodes: set[str] = set()
        self.edges: dict[str, dict[str, float]] = {}
        self.capacities: dict[str, int | None] = {}
        self.occupants: dict[str, str] = {}

    def add_node(self, node_id: str, *, capacity: int | None = None) -> None:
        if capacity is not None and capacity < 1:
            raise ValueError("graph node capacity must be positive")
        self.nodes.add(node_id)
        self.edges.setdefault(node_id, {})
        self.capacities[node_id] = capacity

    def add_edge(self, source: str, target: str, *, cost: float = 1.0, bidirectional: bool = True) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise KeyError("graph edge references unknown node")
        if cost <= 0:
            raise ValueError("graph edge cost must be positive")
        self.edges[source][target] = cost
        if bidirectional:
            self.edges[target][source] = cost

    def place(self, entity_id: str, node_id: str) -> None:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        if not self._has_capacity(node_id, excluding=entity_id):
            raise ValueError("graph node is occupied")
        self.occupants[entity_id] = node_id

    def _has_capacity(self, node_id: str, *, excluding: str | None = None) -> bool:
        capacity = self.capacities.get(node_id)
        if capacity is None:
            return True
        current = sum(1 for entity_id, location in self.occupants.items() if location == node_id and entity_id != excluding)
        return current < capacity

    def path(self, start: str, goal: str, *, actor_id: str | None = None) -> list[str]:
        if start not in self.nodes or goal not in self.nodes:
            return []
        serial = count()
        frontier: list[tuple[float, int, str]] = [(0.0, next(serial), start)]
        costs = {start: 0.0}
        previous: dict[str, str | None] = {start: None}
        while frontier:
            cost, _, current = heapq.heappop(frontier)
            if cost != costs[current]:
                continue
            if current == goal:
                break
            for neighbor, edge_cost in sorted(self.edges[current].items()):
                if neighbor == goal and not self._has_capacity(neighbor, excluding=actor_id):
                    continue
                new_cost = cost + edge_cost
                if new_cost >= costs.get(neighbor, math.inf):
                    continue
                costs[neighbor] = new_cost
                previous[neighbor] = current
                heapq.heappush(frontier, (new_cost, next(serial), neighbor))
        if goal not in previous:
            return []
        result: list[str] = []
        cursor: str | None = goal
        while cursor is not None:
            result.append(cursor)
            cursor = previous[cursor]
        return list(reversed(result))

    def path_cost(self, path: list[str]) -> float:
        if len(path) < 2:
            return 0.0
        return sum(self.edges[a][b] for a, b in zip(path, path[1:], strict=False))

    def validate_move(self, entity_id: str, destination: str, *, max_cost: float | None = None) -> MoveValidation:
        start = self.occupants.get(entity_id)
        if start is None:
            return MoveValidation(allowed=False, reason="entity is not placed in graph space")
        path = self.path(start, destination, actor_id=entity_id)
        if not path:
            return MoveValidation(allowed=False, reason="no authoritative graph path")
        cost = self.path_cost(path)
        if max_cost is not None and cost > max_cost + 1e-9:
            return MoveValidation(allowed=False, reason="movement budget exceeded", cost=cost, path=path)
        return MoveValidation(allowed=True, cost=cost, path=path)


class GridSpace:
    mode = SpatialMode.GRID

    def __init__(self, space_id: str, width: int, height: int, *, diagonal: bool = True) -> None:
        if width < 1 or height < 1:
            raise ValueError("grid dimensions must be positive")
        self.id = space_id
        self.width = width
        self.height = height
        self.diagonal = diagonal
        self.terrain: dict[tuple[int, int], TerrainCell] = {}
        self.occupants: dict[str, tuple[int, int]] = {}

    def in_bounds(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def set_terrain(self, cell: tuple[int, int], terrain: TerrainCell) -> None:
        if not self.in_bounds(cell):
            raise ValueError("terrain cell is out of bounds")
        if terrain.movement_cost <= 0:
            raise ValueError("terrain movement cost must be positive")
        self.terrain[cell] = terrain

    def terrain_at(self, cell: tuple[int, int]) -> TerrainCell:
        return self.terrain.get(cell, TerrainCell())

    def occupied(self, cell: tuple[int, int], *, excluding: str | None = None) -> bool:
        return any(entity_id != excluding and position == cell for entity_id, position in self.occupants.items())

    def walkable(self, cell: tuple[int, int], *, actor_id: str | None = None) -> bool:
        return self.in_bounds(cell) and not self.terrain_at(cell).blocks_movement and not self.occupied(cell, excluding=actor_id)

    def place(self, entity_id: str, cell: tuple[int, int]) -> None:
        if not self.walkable(cell, actor_id=entity_id):
            raise ValueError("grid cell is blocked or occupied")
        self.occupants[entity_id] = cell

    def _neighbors(self, cell: tuple[int, int], actor_id: str | None) -> list[tuple[tuple[int, int], float]]:
        x, y = cell
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if self.diagonal:
            directions.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])
        results: list[tuple[tuple[int, int], float]] = []
        for dx, dy in directions:
            neighbor = (x + dx, y + dy)
            if not self.walkable(neighbor, actor_id=actor_id):
                continue
            diagonal = dx != 0 and dy != 0
            if diagonal:
                if not self.walkable((x + dx, y), actor_id=actor_id) or not self.walkable((x, y + dy), actor_id=actor_id):
                    continue
            step = self.terrain_at(neighbor).movement_cost * (math.sqrt(2.0) if diagonal else 1.0)
            results.append((neighbor, step))
        return sorted(results)

    def path(self, start: tuple[int, int], goal: tuple[int, int], *, actor_id: str | None = None) -> list[tuple[int, int]]:
        if not self.walkable(start, actor_id=actor_id) or not self.walkable(goal, actor_id=actor_id):
            return []
        serial = count()
        frontier: list[tuple[float, int, tuple[int, int]]] = [(0.0, next(serial), start)]
        cost_so_far = {start: 0.0}
        previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        while frontier:
            _, _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for neighbor, step_cost in self._neighbors(current, actor_id):
                new_cost = cost_so_far[current] + step_cost
                if new_cost >= cost_so_far.get(neighbor, math.inf):
                    continue
                cost_so_far[neighbor] = new_cost
                previous[neighbor] = current
                heuristic = math.dist(neighbor, goal)
                heapq.heappush(frontier, (new_cost + heuristic, next(serial), neighbor))
        if goal not in previous:
            return []
        result: list[tuple[int, int]] = []
        cursor: tuple[int, int] | None = goal
        while cursor is not None:
            result.append(cursor)
            cursor = previous[cursor]
        return list(reversed(result))

    def path_cost(self, path: list[tuple[int, int]]) -> float:
        cost = 0.0
        for a, b in zip(path, path[1:], strict=False):
            diagonal = a[0] != b[0] and a[1] != b[1]
            cost += self.terrain_at(b).movement_cost * (math.sqrt(2.0) if diagonal else 1.0)
        return cost

    def validate_move(
        self,
        entity_id: str,
        destination: tuple[int, int],
        *,
        max_cost: float | None = None,
    ) -> MoveValidation:
        start = self.occupants.get(entity_id)
        if start is None:
            return MoveValidation(allowed=False, reason="entity is not placed in grid space")
        path = self.path(start, destination, actor_id=entity_id)
        if not path:
            return MoveValidation(allowed=False, reason="no authoritative grid path")
        cost = self.path_cost(path)
        if max_cost is not None and cost > max_cost + 1e-9:
            return MoveValidation(allowed=False, reason="movement budget exceeded", cost=cost, path=path)
        return MoveValidation(allowed=True, cost=cost, path=path)

    @staticmethod
    def _line_cells(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        x0, y0 = start
        x1, y1 = end
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        result: list[tuple[int, int]] = []
        while True:
            result.append((x0, y0))
            if (x0, y0) == (x1, y1):
                return result
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def line_of_sight(self, start: tuple[int, int], end: tuple[int, int]) -> bool:
        if not self.in_bounds(start) or not self.in_bounds(end):
            return False
        cells = self._line_cells(start, end)
        return not any(self.terrain_at(cell).blocks_los for cell in cells[1:-1])

    def cover_between(self, start: tuple[int, int], end: tuple[int, int]) -> CoverLevel:
        if not self.line_of_sight(start, end):
            return CoverLevel.FULL
        rank = {CoverLevel.NONE: 0, CoverLevel.HALF: 1, CoverLevel.THREE_QUARTERS: 2, CoverLevel.FULL: 3}
        best = CoverLevel.NONE
        for cell in self._line_cells(start, end)[1:-1]:
            cover = self.terrain_at(cell).cover
            if rank[cover] > rank[best]:
                best = cover
        return best


@dataclass(slots=True)
class AxisAlignedBox:
    minimum: Vector3
    maximum: Vector3
    blocks_movement: bool = True
    blocks_los: bool = True
    cover: CoverLevel = CoverLevel.FULL

    def contains(self, point: Vector3, *, radius: float = 0.0) -> bool:
        return (
            self.minimum.x - radius <= point.x <= self.maximum.x + radius
            and self.minimum.y - radius <= point.y <= self.maximum.y + radius
            and self.minimum.z - radius <= point.z <= self.maximum.z + radius
        )


class ContinuousSpace:
    def __init__(self, space_id: str, *, dimensions: int = 3, minimum: Vector3 | None = None, maximum: Vector3 | None = None) -> None:
        if dimensions not in {2, 3}:
            raise ValueError("continuous space dimensions must be 2 or 3")
        self.id = space_id
        self.dimensions = dimensions
        self.mode = SpatialMode.CONTINUOUS_2D if dimensions == 2 else SpatialMode.CONTINUOUS_3D
        self.minimum = minimum or Vector3(x=-math.inf, y=-math.inf, z=-math.inf)
        self.maximum = maximum or Vector3(x=math.inf, y=math.inf, z=math.inf)
        self.obstacles: list[AxisAlignedBox] = []
        self.occupants: dict[str, tuple[Vector3, float]] = {}

    def add_obstacle(self, obstacle: AxisAlignedBox) -> None:
        self.obstacles.append(obstacle)

    def _bounded(self, point: Vector3, radius: float = 0.0) -> bool:
        return (
            self.minimum.x + radius <= point.x <= self.maximum.x - radius
            and self.minimum.y + radius <= point.y <= self.maximum.y - radius
            and (self.dimensions == 2 or self.minimum.z + radius <= point.z <= self.maximum.z - radius)
        )

    def collision(self, point: Vector3, *, radius: float = 0.0, excluding: str | None = None) -> str | None:
        if not self._bounded(point, radius):
            return "bounds"
        for index, obstacle in enumerate(self.obstacles):
            if obstacle.blocks_movement and obstacle.contains(point, radius=radius):
                return f"obstacle:{index}"
        for entity_id, (position, other_radius) in self.occupants.items():
            if entity_id == excluding:
                continue
            if position.distance_to(point) < radius + other_radius:
                return f"entity:{entity_id}"
        return None

    def place(self, entity_id: str, position: Vector3, *, radius: float = 0.0) -> None:
        collision = self.collision(position, radius=radius, excluding=entity_id)
        if collision is not None:
            raise ValueError(f"continuous position collides with {collision}")
        self.occupants[entity_id] = (position.model_copy(deep=True), max(0.0, radius))

    @staticmethod
    def _segment_intersects_box(start: Vector3, end: Vector3, box: AxisAlignedBox, dimensions: int) -> bool:
        t_min, t_max = 0.0, 1.0
        axes = ((start.x, end.x, box.minimum.x, box.maximum.x), (start.y, end.y, box.minimum.y, box.maximum.y))
        if dimensions == 3:
            axes += ((start.z, end.z, box.minimum.z, box.maximum.z),)
        for origin, destination, minimum, maximum in axes:
            direction = destination - origin
            if abs(direction) < 1e-12:
                if origin < minimum or origin > maximum:
                    return False
                continue
            inverse = 1.0 / direction
            near = (minimum - origin) * inverse
            far = (maximum - origin) * inverse
            if near > far:
                near, far = far, near
            t_min = max(t_min, near)
            t_max = min(t_max, far)
            if t_min > t_max:
                return False
        return True

    def line_of_sight(self, start: Vector3, end: Vector3) -> bool:
        return not any(
            obstacle.blocks_los and self._segment_intersects_box(start, end, obstacle, self.dimensions)
            for obstacle in self.obstacles
        )

    def cover_between(self, start: Vector3, end: Vector3) -> CoverLevel:
        rank = {CoverLevel.NONE: 0, CoverLevel.HALF: 1, CoverLevel.THREE_QUARTERS: 2, CoverLevel.FULL: 3}
        best = CoverLevel.NONE
        for obstacle in self.obstacles:
            if not self._segment_intersects_box(start, end, obstacle, self.dimensions):
                continue
            if obstacle.blocks_los:
                return CoverLevel.FULL
            if rank[obstacle.cover] > rank[best]:
                best = obstacle.cover
        return best

    def validate_move(self, entity_id: str, destination: Vector3, *, max_distance: float | None = None) -> MoveValidation:
        current = self.occupants.get(entity_id)
        if current is None:
            return MoveValidation(allowed=False, reason="entity is not placed in continuous space")
        start, radius = current
        collision = self.collision(destination, radius=radius, excluding=entity_id)
        if collision is not None:
            return MoveValidation(allowed=False, reason=f"destination collides with {collision}")
        distance = start.distance_to(destination)
        if max_distance is not None and distance > max_distance + 1e-9:
            return MoveValidation(allowed=False, reason="movement budget exceeded", cost=distance)
        if any(
            obstacle.blocks_movement and self._segment_intersects_box(start, destination, obstacle, self.dimensions)
            for obstacle in self.obstacles
        ):
            return MoveValidation(allowed=False, reason="movement segment crosses blocking geometry", cost=distance)
        return MoveValidation(allowed=True, cost=distance, path=[start.model_dump(mode="json"), destination.model_dump(mode="json")])


class SpatialAuthority:
    """Registry and authoritative query facade for graph, grid, and continuous spaces."""

    def __init__(self) -> None:
        self.spaces: dict[str, GraphSpace | GridSpace | ContinuousSpace] = {}

    def register(self, space: GraphSpace | GridSpace | ContinuousSpace) -> None:
        self.spaces[space.id] = space

    def require(self, space_id: str) -> GraphSpace | GridSpace | ContinuousSpace:
        try:
            return self.spaces[space_id]
        except KeyError as exc:
            raise KeyError(f"unknown spatial authority space: {space_id}") from exc

    def validate_move(self, space_id: str, entity_id: str, destination: Any, *, budget: float | None = None) -> MoveValidation:
        space = self.require(space_id)
        if isinstance(space, GraphSpace):
            return space.validate_move(entity_id, str(destination), max_cost=budget)
        if isinstance(space, GridSpace):
            cell = tuple(destination)
            if len(cell) != 2:
                raise ValueError("grid destination must contain x and y")
            return space.validate_move(entity_id, (int(cell[0]), int(cell[1])), max_cost=budget)
        point = destination if isinstance(destination, Vector3) else Vector3.model_validate(destination)
        return space.validate_move(entity_id, point, max_distance=budget)
