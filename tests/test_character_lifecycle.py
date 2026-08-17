# tests/test_character_lifecycle.py
from __future__ import annotations

import pytest

from dnd_rpg_engine.characters.lifecycle import (
    CharacterBuildRequest,
    CharacterClassDefinition,
    CharacterLifecycle,
    ClassResourceDefinition,
    EquipmentDefinition,
)
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.commands import CustomCommand
from dnd_rpg_engine.core.models import GameConfig, TimeMode
from dnd_rpg_engine.rulesets.srd_5_2_1 import build_srd_character_lifecycle, entity_proficiency_bonus


def test_character_build_level_rest_resources_and_equipment() -> None:
    lifecycle = CharacterLifecycle(
        classes={
            "warden": CharacterClassDefinition(
                id="warden",
                name="Warden",
                hit_die=10,
                resources={
                    "guard": ClassResourceDefinition(
                        id="guard",
                        name="Guard",
                        base_max=2,
                        per_level=1,
                        short_rest_fraction=0.5,
                        long_rest_fraction=1.0,
                    )
                },
            )
        },
        equipment={
            "shield": EquipmentDefinition(
                item_id="shield",
                name="Shield",
                slots=("off_hand",),
                modifiers={"armor_class": 2},
            ),
            "warded_ring": EquipmentDefinition(
                item_id="warded_ring",
                name="Warded Ring",
                slots=("ring",),
                modifiers={"saving_throw": 1},
                requires_attunement=True,
            ),
        },
    )
    entity = lifecycle.build_character(
        CharacterBuildRequest(
            name="Mara",
            class_id="warden",
            starting_equipment=("shield", "warded_ring"),
        )
    )

    progress = lifecycle.progress(entity)
    assert progress.total_level == 1
    assert entity.resources.max_hp == 10
    assert lifecycle.resources(entity)["guard"].current == 2
    assert lifecycle.equipment_state(entity).slots == {"off_hand": "shield", "ring": "warded_ring"}
    assert lifecycle.effective_equipment_modifiers(entity) == {"armor_class": 2.0, "saving_throw": 1.0}

    lifecycle.spend_resource(entity, "guard")
    assert lifecycle.resources(entity)["guard"].current == 1
    lifecycle.rest(entity, "short_rest")
    assert lifecycle.resources(entity)["guard"].current == 2

    lifecycle.award_xp(entity, 1000)
    assert lifecycle.eligible_for_level(entity) is True
    outcome = lifecycle.level_up(entity, "warden")
    assert outcome.total_level == 2
    assert outcome.class_level == 2
    assert lifecycle.resources(entity)["guard"].maximum == 3
    assert entity.resources.max_hp > 10


def test_srd_adapter_builds_all_catalog_classes() -> None:
    lifecycle = build_srd_character_lifecycle()
    assert {"fighter", "wizard", "cleric", "rogue"}.issubset(lifecycle.classes)
    fighter = lifecycle.build_character(CharacterBuildRequest(name="Arden", class_id="fighter"))
    assert lifecycle.progress(fighter).classes == {"fighter": 1}
    assert fighter.resources.max_hp == 10

    lifecycle.award_xp(fighter, 100_000)
    for _ in range(4):
        lifecycle.level_up(fighter, "fighter")
    assert lifecycle.progress(fighter).total_level == 5
    assert entity_proficiency_bonus(fighter) == 3


@pytest.mark.asyncio
async def test_advanced_engine_character_commands_emit_authoritative_events() -> None:
    engine = await AdvancedGameEngine.create(
        config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=101)
    )
    character = await engine.create_character(CharacterBuildRequest(name="Rin", class_id="adventurer"))

    xp = await engine.dispatch(
        CustomCommand(actor_id=character.id, name="character.award_xp", payload={"amount": 1000})
    )
    assert any(event.type == "character.xp_awarded" for event in xp.events)

    leveled = await engine.dispatch(
        CustomCommand(actor_id=character.id, name="character.level_up", payload={"class_id": "adventurer"})
    )
    assert any(event.type == "character.leveled" for event in leveled.events)
    assert engine.character_lifecycle.progress(character).total_level == 2

    character.resources.hp = max(1, character.resources.max_hp - 4)
    rested = await engine.dispatch(
        CustomCommand(actor_id=character.id, name="character.rest", payload={"profile_id": "long_rest"})
    )
    assert character.resources.hp == character.resources.max_hp
    assert any(event.type == "character.rested" for event in rested.events)
