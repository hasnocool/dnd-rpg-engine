# src/dnd_rpg_engine/rulesets/srd_5_2_1/rules.py
from __future__ import annotations

from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog import SKILLS


SRD_5_2_1_RULESET = RuleSet(
    id="srd_5_2_1.core",
    name="Fifth Edition SRD 5.2.1",
    base_defense=10,
    critical_success_roll=20,
    critical_failure_roll=1,
    round_seconds=6.0,
    minimum_damage=0,
    spell_save_base=8,
    death_saves_enabled=True,
    death_save_dc=10,
    death_save_successes_required=3,
    death_save_failures_required=3,
)


def proficiency_bonus(level_or_cr: int) -> int:
    """Return the SRD proficiency bonus for a level/whole-number CR."""
    if level_or_cr < 1:
        raise ValueError("level_or_cr must be positive")
    return 2 + ((level_or_cr - 1) // 4)


def character_level(entity: Entity) -> int:
    raw = entity.component("progression").get("level", 1)
    return max(1, min(20, int(raw)))


def entity_proficiency_bonus(entity: Entity) -> int:
    explicit = entity.component("proficiencies").get("bonus")
    if explicit is not None:
        return int(explicit)
    return proficiency_bonus(character_level(entity))


def skill_bonus(entity: Entity, skill_id: str) -> int:
    skill = SKILLS[skill_id]
    bonus = entity.stats.modifier(skill.ability.value)
    proficiencies = entity.component("proficiencies")
    skills = set(proficiencies.get("skills", []))
    expertise = set(proficiencies.get("expertise", []))
    if skill_id in expertise:
        bonus += entity_proficiency_bonus(entity) * 2
    elif skill_id in skills:
        bonus += entity_proficiency_bonus(entity)
    return bonus


def spell_save_dc(entity: Entity, ability: str) -> int:
    return SRD_5_2_1_RULESET.spell_save_base + entity.stats.modifier(ability) + entity_proficiency_bonus(entity)


def spell_attack_bonus(entity: Entity, ability: str) -> int:
    return entity.stats.modifier(ability) + entity_proficiency_bonus(entity)
