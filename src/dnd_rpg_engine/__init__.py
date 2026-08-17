# src/dnd_rpg_engine/__init__.py
"""Public package surface for the RPG engine."""

from dnd_rpg_engine.characters.lifecycle import CharacterLifecycle, default_character_lifecycle
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import CampaignState, Entity, GameConfig, Stats, TimeMode
from dnd_rpg_engine.rulesets.srd_5_2_1 import SRDRuntimeCatalog

__all__ = [
    "AdvancedGameEngine",
    "CampaignState",
    "CharacterLifecycle",
    "Entity",
    "GameConfig",
    "GameEngine",
    "SRDRuntimeCatalog",
    "Stats",
    "TimeMode",
    "default_character_lifecycle",
]
__version__ = "1.8.0"
