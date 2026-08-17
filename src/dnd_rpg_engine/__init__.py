# src/dnd_rpg_engine/__init__.py
"""Public package surface for the RPG engine."""

from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import CampaignState, Entity, GameConfig, Stats, TimeMode

__all__ = ["AdvancedGameEngine", "CampaignState", "Entity", "GameConfig", "GameEngine", "Stats", "TimeMode"]
__version__ = "1.5.0"
