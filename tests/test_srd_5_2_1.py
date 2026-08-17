# tests/test_srd_5_2_1.py
from __future__ import annotations

import pytest

from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, ResourcePool, Stats
from dnd_rpg_engine.creator.content import ContentPack, ContentValidator
from dnd_rpg_engine.creator.loader import install_content_pack
from dnd_rpg_engine.rulesets.srd_5_2_1 import SRD_5_2_1_RULESET, build_srd_5_2_1_pack, proficiency_bonus
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog import BACKGROUNDS, CLASSES, FEATS, SKILLS, SPECIES
from dnd_rpg_engine.rulesets.srd_5_2_1.source import OFFICIAL_SRD_SOURCE, SRDSourceError, validate_official_source_url
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.conditions import ActiveCondition


def test_srd_source_metadata_and_allowlist() -> None:
    assert OFFICIAL_SRD_SOURCE.release_name == "SRD v5.2.1"
    assert OFFICIAL_SRD_SOURCE.license_id == "CC-BY-4.0"
    validate_official_source_url(OFFICIAL_SRD_SOURCE.pdf_url)
    with pytest.raises(SRDSourceError):
        validate_official_source_url("https://example.com/rules.pdf")
    with pytest.raises(SRDSourceError):
        validate_official_source_url("https://www.dndbeyond.com/basic-rules/example")


def test_srd_catalog_coverage() -> None:
    assert len(SKILLS) == 18
    assert len(CLASSES) == 12
    assert len(SPECIES) == 9
    assert len(BACKGROUNDS) == 4
    assert len(FEATS) >= 15
    assert CLASSES["barbarian"].hit_die == 12
    assert CLASSES["wizard"].spellcasting_ability == "intelligence"


def test_srd_proficiency_progression() -> None:
    assert proficiency_bonus(1) == 2
    assert proficiency_bonus(4) == 2
    assert proficiency_bonus(5) == 3
    assert proficiency_bonus(9) == 4
    assert proficiency_bonus(13) == 5
    assert proficiency_bonus(17) == 6


def test_srd_pack_validates_and_round_trips() -> None:
    pack = build_srd_5_2_1_pack()
    assert ContentValidator().validate(pack) == []
    assert pack.manifest.license == "CC-BY-4.0"
    assert pack.rules_data["coverage"]["prose_bundled"] is False
    restored = ContentPack.from_zip_bytes(pack.to_zip_bytes())
    assert restored.content_hash() == pack.content_hash()
    assert len(restored.conditions) >= 15


def test_temporary_hit_points_absorb_damage_without_stacking() -> None:
    resources = ResourcePool(hp=10, max_hp=10, temp_hp=5)
    assert resources.apply_damage(3) == 3
    assert resources.temp_hp == 2
    assert resources.hp == 10
    resources.grant_temp_hp(1)
    assert resources.temp_hp == 2
    resources.grant_temp_hp(6)
    assert resources.temp_hp == 6
    resources.apply_damage(8)
    assert resources.temp_hp == 0
    assert resources.hp == 8


@pytest.mark.asyncio
async def test_srd_conditions_drive_advantage_disadvantage() -> None:
    engine = await GameEngine.create("SRD test")
    pack = build_srd_5_2_1_pack()
    install_content_pack(engine, pack)
    engine.activate_rules(SRD_5_2_1_RULESET)
    action = ActionDefinition(id="test_strike", name="Test Strike", damage="1d4", range=2.0)
    engine.actions.register(action)
    attacker = Entity(id="attacker", name="Attacker", kind=EntityKind.PLAYER, controller=ControllerKind.HUMAN, stats=Stats(strength=12))
    target = Entity(id="target", name="Target", kind=EntityKind.CREATURE, controller=ControllerKind.AI)
    await engine.add_entity(attacker)
    await engine.add_entity(target)
    engine._set_conditions(attacker, [ActiveCondition(condition_id="blinded")])
    resolution = engine.combat.resolve_attack(
        attacker,
        target,
        action,
        active_conditions=engine._active_conditions(attacker),
        target_conditions=engine._active_conditions(target),
    )
    assert len(resolution.raw_rolls) == 2
    assert resolution.roll == min(resolution.raw_rolls)


@pytest.mark.asyncio
async def test_srd_zero_hp_starts_death_saves_for_player() -> None:
    engine = await GameEngine.create("SRD death saves")
    pack = build_srd_5_2_1_pack()
    install_content_pack(engine, pack)
    engine.activate_rules(SRD_5_2_1_RULESET)
    hero = Entity(
        id="hero",
        name="Hero",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        resources=ResourcePool(hp=0, max_hp=12),
    )
    await engine.add_entity(hero)
    await engine._handle_zero_hp(hero, source_id="hazard", damage=2)
    assert hero.alive is True
    assert hero.component("death_saves")["failures"] == 0
    assert any(condition.condition_id == "unconscious" for condition in engine._active_conditions(hero))
