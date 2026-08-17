# src/dnd_rpg_engine/rulesets/srd_5_2_1/__init__.py
"""Opt-in structured implementation of the CC-licensed SRD 5.2.1 foundation."""

from dnd_rpg_engine.rulesets.srd_5_2_1.pack import build_srd_5_2_1_pack
from dnd_rpg_engine.rulesets.srd_5_2_1.rules import (
    SRD_5_2_1_RULESET,
    entity_proficiency_bonus,
    proficiency_bonus,
    skill_bonus,
    spell_attack_bonus,
    spell_save_dc,
)
from dnd_rpg_engine.rulesets.srd_5_2_1.source import OFFICIAL_SRD_SOURCE, fetch_official_srd_pdf

__all__ = [
    "OFFICIAL_SRD_SOURCE",
    "SRD_5_2_1_RULESET",
    "build_srd_5_2_1_pack",
    "entity_proficiency_bonus",
    "fetch_official_srd_pdf",
    "proficiency_bonus",
    "skill_bonus",
    "spell_attack_bonus",
    "spell_save_dc",
]
