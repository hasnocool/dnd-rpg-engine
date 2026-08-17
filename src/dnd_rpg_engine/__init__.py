# src/dnd_rpg_engine/__init__.py
"""Public package surface for the RPG engine."""

from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import CampaignState, Entity, GameConfig, Stats, TimeMode

__all__ = ["CampaignState", "Entity", "GameConfig", "GameEngine", "Stats", "TimeMode"]
__version__ = "1.1.0"
