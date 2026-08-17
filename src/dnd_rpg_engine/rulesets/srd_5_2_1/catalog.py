# src/dnd_rpg_engine/rulesets/srd_5_2_1/catalog.py
from __future__ import annotations

from dnd_rpg_engine.rulesets.srd_5_2_1.models import (
    AbilityId,
    BackgroundDefinition,
    ClassDefinition,
    FeatDefinition,
    SkillDefinition,
    SpeciesDefinition,
)


SKILLS: dict[str, SkillDefinition] = {
    row.id: row
    for row in (
        SkillDefinition(id="acrobatics", name="Acrobatics", ability=AbilityId.DEXTERITY),
        SkillDefinition(id="animal_handling", name="Animal Handling", ability=AbilityId.WISDOM),
        SkillDefinition(id="arcana", name="Arcana", ability=AbilityId.INTELLIGENCE),
        SkillDefinition(id="athletics", name="Athletics", ability=AbilityId.STRENGTH),
        SkillDefinition(id="deception", name="Deception", ability=AbilityId.CHARISMA),
        SkillDefinition(id="history", name="History", ability=AbilityId.INTELLIGENCE),
        SkillDefinition(id="insight", name="Insight", ability=AbilityId.WISDOM),
        SkillDefinition(id="intimidation", name="Intimidation", ability=AbilityId.CHARISMA),
        SkillDefinition(id="investigation", name="Investigation", ability=AbilityId.INTELLIGENCE),
        SkillDefinition(id="medicine", name="Medicine", ability=AbilityId.WISDOM),
        SkillDefinition(id="nature", name="Nature", ability=AbilityId.INTELLIGENCE),
        SkillDefinition(id="perception", name="Perception", ability=AbilityId.WISDOM),
        SkillDefinition(id="performance", name="Performance", ability=AbilityId.CHARISMA),
        SkillDefinition(id="persuasion", name="Persuasion", ability=AbilityId.CHARISMA),
        SkillDefinition(id="religion", name="Religion", ability=AbilityId.INTELLIGENCE),
        SkillDefinition(id="sleight_of_hand", name="Sleight of Hand", ability=AbilityId.DEXTERITY),
        SkillDefinition(id="stealth", name="Stealth", ability=AbilityId.DEXTERITY),
        SkillDefinition(id="survival", name="Survival", ability=AbilityId.WISDOM),
    )
}


CLASSES: dict[str, ClassDefinition] = {
    row.id: row
    for row in (
        ClassDefinition(id="barbarian", name="Barbarian", hit_die=12, primary_abilities=(AbilityId.STRENGTH,), saving_throw_proficiencies=(AbilityId.STRENGTH, AbilityId.CONSTITUTION), source_page=28),
        ClassDefinition(id="bard", name="Bard", hit_die=8, primary_abilities=(AbilityId.CHARISMA,), saving_throw_proficiencies=(AbilityId.DEXTERITY, AbilityId.CHARISMA), spellcasting_ability=AbilityId.CHARISMA, source_page=31),
        ClassDefinition(id="cleric", name="Cleric", hit_die=8, primary_abilities=(AbilityId.WISDOM,), saving_throw_proficiencies=(AbilityId.WISDOM, AbilityId.CHARISMA), spellcasting_ability=AbilityId.WISDOM, source_page=36),
        ClassDefinition(id="druid", name="Druid", hit_die=8, primary_abilities=(AbilityId.WISDOM,), saving_throw_proficiencies=(AbilityId.INTELLIGENCE, AbilityId.WISDOM), spellcasting_ability=AbilityId.WISDOM, source_page=41),
        ClassDefinition(id="fighter", name="Fighter", hit_die=10, primary_abilities=(AbilityId.STRENGTH, AbilityId.DEXTERITY), saving_throw_proficiencies=(AbilityId.STRENGTH, AbilityId.CONSTITUTION), source_page=47),
        ClassDefinition(id="monk", name="Monk", hit_die=8, primary_abilities=(AbilityId.DEXTERITY, AbilityId.WISDOM), saving_throw_proficiencies=(AbilityId.STRENGTH, AbilityId.DEXTERITY), source_page=49),
        ClassDefinition(id="paladin", name="Paladin", hit_die=10, primary_abilities=(AbilityId.STRENGTH, AbilityId.CHARISMA), saving_throw_proficiencies=(AbilityId.WISDOM, AbilityId.CHARISMA), spellcasting_ability=AbilityId.CHARISMA, source_page=53),
        ClassDefinition(id="ranger", name="Ranger", hit_die=10, primary_abilities=(AbilityId.DEXTERITY, AbilityId.WISDOM), saving_throw_proficiencies=(AbilityId.STRENGTH, AbilityId.DEXTERITY), spellcasting_ability=AbilityId.WISDOM, source_page=57),
        ClassDefinition(id="rogue", name="Rogue", hit_die=8, primary_abilities=(AbilityId.DEXTERITY,), saving_throw_proficiencies=(AbilityId.DEXTERITY, AbilityId.INTELLIGENCE), source_page=61),
        ClassDefinition(id="sorcerer", name="Sorcerer", hit_die=6, primary_abilities=(AbilityId.CHARISMA,), saving_throw_proficiencies=(AbilityId.CONSTITUTION, AbilityId.CHARISMA), spellcasting_ability=AbilityId.CHARISMA, source_page=64),
        ClassDefinition(id="warlock", name="Warlock", hit_die=8, primary_abilities=(AbilityId.CHARISMA,), saving_throw_proficiencies=(AbilityId.WISDOM, AbilityId.CHARISMA), spellcasting_ability=AbilityId.CHARISMA, source_page=70),
        ClassDefinition(id="wizard", name="Wizard", hit_die=6, primary_abilities=(AbilityId.INTELLIGENCE,), saving_throw_proficiencies=(AbilityId.INTELLIGENCE, AbilityId.WISDOM), spellcasting_ability=AbilityId.INTELLIGENCE, source_page=77),
    )
}


SPECIES: dict[str, SpeciesDefinition] = {
    row.id: row
    for row in (
        SpeciesDefinition(id="dragonborn", name="Dragonborn", speed_feet=30, sizes=("medium",), trait_ids=("draconic_ancestry", "breath_weapon", "damage_resistance", "darkvision", "draconic_flight"), source_page=84),
        SpeciesDefinition(id="dwarf", name="Dwarf", speed_feet=30, sizes=("medium",), trait_ids=("darkvision", "dwarven_resilience", "dwarven_toughness", "stonecunning"), source_page=84),
        SpeciesDefinition(id="elf", name="Elf", speed_feet=30, sizes=("medium",), trait_ids=("darkvision", "elven_lineage", "fey_ancestry", "keen_senses", "trance"), source_page=84),
        SpeciesDefinition(id="gnome", name="Gnome", speed_feet=30, sizes=("small",), trait_ids=("darkvision", "gnomish_cunning", "gnomish_lineage"), source_page=85),
        SpeciesDefinition(id="goliath", name="Goliath", speed_feet=35, sizes=("medium",), trait_ids=("giant_ancestry", "large_form", "powerful_build"), source_page=85),
        SpeciesDefinition(id="halfling", name="Halfling", speed_feet=30, sizes=("small",), trait_ids=("brave", "halfling_nimbleness", "luck", "naturally_stealthy"), source_page=86),
        SpeciesDefinition(id="human", name="Human", speed_feet=30, sizes=("medium", "small"), trait_ids=("resourceful", "skillful", "versatile"), source_page=86),
        SpeciesDefinition(id="orc", name="Orc", speed_feet=30, sizes=("medium",), trait_ids=("adrenaline_rush", "darkvision", "relentless_endurance"), source_page=86),
        SpeciesDefinition(id="tiefling", name="Tiefling", speed_feet=30, sizes=("medium", "small"), trait_ids=("darkvision", "fiendish_legacy", "otherworldly_presence"), source_page=86),
    )
}


BACKGROUNDS: dict[str, BackgroundDefinition] = {
    row.id: row
    for row in (
        BackgroundDefinition(id="acolyte", name="Acolyte", skill_proficiencies=("insight", "religion"), origin_feat_id="magic_initiate", source_page=83),
        BackgroundDefinition(id="criminal", name="Criminal", skill_proficiencies=("sleight_of_hand", "stealth"), origin_feat_id="alert", source_page=83),
        BackgroundDefinition(id="sage", name="Sage", skill_proficiencies=("arcana", "history"), origin_feat_id="magic_initiate", source_page=83),
        BackgroundDefinition(id="soldier", name="Soldier", skill_proficiencies=("athletics", "intimidation"), origin_feat_id="savage_attacker", source_page=83),
    )
}


FEATS: dict[str, FeatDefinition] = {
    row.id: row
    for row in (
        FeatDefinition(id="alert", name="Alert", category="origin", source_page=87),
        FeatDefinition(id="magic_initiate", name="Magic Initiate", category="origin", repeatable=True, source_page=87),
        FeatDefinition(id="savage_attacker", name="Savage Attacker", category="origin", source_page=87),
        FeatDefinition(id="ability_score_improvement", name="Ability Score Improvement", category="general", repeatable=True, source_page=87),
        FeatDefinition(id="archery", name="Archery", category="fighting_style", source_page=87),
        FeatDefinition(id="defense", name="Defense", category="fighting_style", source_page=87),
        FeatDefinition(id="great_weapon_fighting", name="Great Weapon Fighting", category="fighting_style", source_page=87),
        FeatDefinition(id="two_weapon_fighting", name="Two-Weapon Fighting", category="fighting_style", source_page=87),
        FeatDefinition(id="boon_of_combat_prowess", name="Boon of Combat Prowess", category="epic_boon", source_page=88),
        FeatDefinition(id="boon_of_dimensional_travel", name="Boon of Dimensional Travel", category="epic_boon", source_page=88),
        FeatDefinition(id="boon_of_fate", name="Boon of Fate", category="epic_boon", source_page=88),
        FeatDefinition(id="boon_of_irresistible_offense", name="Boon of Irresistible Offense", category="epic_boon", source_page=88),
        FeatDefinition(id="boon_of_night_spirit", name="Boon of the Night Spirit", category="epic_boon", source_page=88),
        FeatDefinition(id="boon_of_spell_recall", name="Boon of Spell Recall", category="epic_boon", source_page=88),
        FeatDefinition(id="boon_of_truesight", name="Boon of Truesight", category="epic_boon", source_page=88),
    )
}
