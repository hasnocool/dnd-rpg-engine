"""Public package surface for the RPG platform."""

from dnd_rpg_engine.characters.lifecycle import CharacterLifecycle, default_character_lifecycle
from dnd_rpg_engine.client import RPGClient, RPGClientConfig
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import CampaignState, Entity, GameConfig, Stats, TimeMode

__all__ = [
    "AdvancedGameEngine",
    "CampaignState",
    "CharacterLifecycle",
    "Entity",
    "GameConfig",
    "GameEngine",
    "RPGClient",
    "RPGClientConfig",
    "Stats",
    "TimeMode",
    "default_character_lifecycle",
]
__version__ = "2.5.0"
