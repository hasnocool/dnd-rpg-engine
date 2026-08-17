"""Opt-in structured implementation of the CC-licensed SRD 5.2.1 foundation."""

from dnd_rpg_engine.rulesets.srd_5_2_1.catalog_store import SRDCatalogStore
from dnd_rpg_engine.rulesets.srd_5_2_1.compiler import (
    SRDCompilerDependencyError,
    SRDCompilerError,
    SRDDocument,
    compile_document,
    compile_srd_catalog,
)
from dnd_rpg_engine.rulesets.srd_5_2_1.lifecycle import build_srd_character_lifecycle
from dnd_rpg_engine.rulesets.srd_5_2_1.pack import build_srd_5_2_1_pack
from dnd_rpg_engine.rulesets.srd_5_2_1.rules import (
    SRD_5_2_1_RULESET,
    entity_proficiency_bonus,
    proficiency_bonus,
    skill_bonus,
    spell_attack_bonus,
    spell_save_dc,
)
from dnd_rpg_engine.rulesets.srd_5_2_1.runtime import (
    DeathSaveOutcome,
    SRD521RulesRuntime,
    SRDRuntimeCatalog,
    ZeroHPTransition,
)
from dnd_rpg_engine.rulesets.srd_5_2_1.source import OFFICIAL_SRD_SOURCE, fetch_official_srd_pdf
from dnd_rpg_engine.rulesets.srd_5_2_1.toolbox import (
    CR_XP,
    ENCOUNTER_BUDGETS,
    ENVIRONMENTAL_RULES,
    TERRAIN_TRAVEL_RULES,
    TRAVEL_PACES,
    build_encounter_candidate,
    encounter_budget,
    extended_travel_dc,
    monster_xp,
    special_travel_rate,
)

__all__ = [
    "CR_XP",
    "DeathSaveOutcome",
    "ENCOUNTER_BUDGETS",
    "ENVIRONMENTAL_RULES",
    "OFFICIAL_SRD_SOURCE",
    "SRD521RulesRuntime",
    "SRDCompilerDependencyError",
    "SRDCompilerError",
    "SRDCatalogStore",
    "SRDDocument",
    "SRDRuntimeCatalog",
    "SRD_5_2_1_RULESET",
    "TERRAIN_TRAVEL_RULES",
    "TRAVEL_PACES",
    "ZeroHPTransition",
    "build_encounter_candidate",
    "build_srd_5_2_1_pack",
    "compile_document",
    "compile_srd_catalog",
    "encounter_budget",
    "build_srd_character_lifecycle",
    "entity_proficiency_bonus",
    "extended_travel_dc",
    "fetch_official_srd_pdf",
    "monster_xp",
    "proficiency_bonus",
    "skill_bonus",
    "special_travel_rate",
    "spell_attack_bonus",
    "spell_save_dc",
]
