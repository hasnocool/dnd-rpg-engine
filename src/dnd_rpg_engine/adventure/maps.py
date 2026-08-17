# src/dnd_rpg_engine/adventure/maps.py
from __future__ import annotations

from pydantic import BaseModel, Field


class AreaNode(BaseModel):
    id: str
    name: str
    description: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    tags: set[str] = Field(default_factory=set)
    scene_binding: str | None = None


class AreaEdge(BaseModel):
    source: str
    target: str
    travel_time: float = Field(default=1.0, gt=0)
    bidirectional: bool = True
    requirements: dict[str, object] = Field(default_factory=dict)


class WorldMap(BaseModel):
    id: str
    name: str
    nodes: dict[str, AreaNode] = Field(default_factory=dict)
    edges: list[AreaEdge] = Field(default_factory=list)

    def neighbors(self, node_id: str) -> list[tuple[AreaNode, float]]:
        results: list[tuple[AreaNode, float]] = []
        for edge in self.edges:
            if edge.source == node_id and edge.target in self.nodes:
                results.append((self.nodes[edge.target], edge.travel_time))
            elif edge.bidirectional and edge.target == node_id and edge.source in self.nodes:
                results.append((self.nodes[edge.source], edge.travel_time))
        return results


class MapRegistry:
    def __init__(self) -> None:
        self._maps: dict[str, WorldMap] = {}

    def register(self, world_map: WorldMap) -> None:
        self._maps[world_map.id] = world_map

    def require(self, map_id: str) -> WorldMap:
        try:
            return self._maps[map_id]
        except KeyError as exc:
            raise KeyError(f"unknown map: {map_id}") from exc

    def all(self) -> tuple[WorldMap, ...]:
        return tuple(self._maps.values())
