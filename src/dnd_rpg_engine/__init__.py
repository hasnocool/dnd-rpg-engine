"""Public package surface for the RPG engine."""

from dnd_rpg_engine.characters.lifecycle import CharacterLifecycle, default_character_lifecycle
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import CampaignState, Entity, GameConfig, Stats, TimeMode
from dnd_rpg_engine.core.world_engine import WorldPlatformEngine

__all__ = [
    "AdvancedGameEngine",
    "CampaignState",
    "CharacterLifecycle",
    "Entity",
    "GameConfig",
    "GameEngine",
    "Stats",
    "TimeMode",
    "WorldPlatformEngine",
    "default_character_lifecycle",
]
__version__ = "3.0.0"
