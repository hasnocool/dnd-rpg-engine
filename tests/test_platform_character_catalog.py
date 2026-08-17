from __future__ import annotations

import pytest

from dnd_rpg_engine.api.platform import DndWorldPlatformEngine
from dnd_rpg_engine.characters.lifecycle import CharacterBuildRequest
from dnd_rpg_engine.core.models import GameConfig, TimeMode


EXPECTED_CLASSES = {
    "barbarian",
    "bard",
    "cleric",
    "druid",
    "fighter",
    "monk",
    "paladin",
    "ranger",
    "rogue",
    "sorcerer",
    "warlock",
    "wizard",
}


@pytest.mark.asyncio
async def test_platform_profile_exposes_srd_hero_classes() -> None:
    engine = await DndWorldPlatformEngine.create(
        "Hero Catalog",
        config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=42),
    )

    assert set(engine.character_lifecycle.classes) == EXPECTED_CLASSES
    assert engine.character_lifecycle.classes["fighter"].hit_die == 10
    assert engine.character_lifecycle.classes["wizard"].spellcasting_ability == "intelligence"

    hero = await engine.create_character(
        CharacterBuildRequest(name="Arden", class_id="fighter")
    )
    assert engine.character_lifecycle.progress(hero).classes == {"fighter": 1}
    assert hero.resources.max_hp == 10
