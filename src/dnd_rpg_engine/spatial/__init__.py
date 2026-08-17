# src/dnd_rpg_engine/spatial/__init__.py
"""Authoritative graph, grid, 2D, and 3D spatial simulation."""

from dnd_rpg_engine.spatial.world import (
    AxisAlignedBox,
    ContinuousSpace,
    CoverLevel,
    GraphSpace,
    GridSpace,
    MoveValidation,
    SpatialAuthority,
    SpatialMode,
    TerrainCell,
    Vector3,
)

__all__ = [
    "AxisAlignedBox",
    "ContinuousSpace",
    "CoverLevel",
    "GraphSpace",
    "GridSpace",
    "MoveValidation",
    "SpatialAuthority",
    "SpatialMode",
    "TerrainCell",
    "Vector3",
]
