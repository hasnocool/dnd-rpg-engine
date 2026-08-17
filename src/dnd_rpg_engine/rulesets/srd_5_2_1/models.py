# src/dnd_rpg_engine/rulesets/srd_5_2_1/models.py
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AbilityId(StrEnum):
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"


class SkillDefinition(BaseModel):
    id: str
    name: str
    ability: AbilityId


class ClassDefinition(BaseModel):
    id: str
    name: str
    hit_die: int = Field(ge=4, le=12)
    primary_abilities: tuple[AbilityId, ...]
    saving_throw_proficiencies: tuple[AbilityId, AbilityId]
    spellcasting_ability: AbilityId | None = None
    source_page: int = Field(ge=1)


class SpeciesDefinition(BaseModel):
    id: str
    name: str
    speed_feet: int = Field(default=30, ge=0)
    sizes: tuple[str, ...] = ("medium",)
    trait_ids: tuple[str, ...] = ()
    source_page: int = Field(ge=1)


class BackgroundDefinition(BaseModel):
    id: str
    name: str
    skill_proficiencies: tuple[str, str]
    origin_feat_id: str
    source_page: int = Field(ge=1)


class FeatDefinition(BaseModel):
    id: str
    name: str
    category: str
    repeatable: bool = False
    source_page: int = Field(ge=1)


class SRDSourceMetadata(BaseModel):
    release_name: str = "SRD v5.2.1"
    rules_generation: str = "5.5e"
    published_date: str = "2025-05-01"
    release_page: str = "https://www.dndbeyond.com/srd"
    pdf_url: str = "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf"
    license_id: str = "CC-BY-4.0"
    license_url: str = "https://creativecommons.org/licenses/by/4.0/"
    official_host_allowlist: tuple[str, ...] = ("www.dndbeyond.com", "media.dndbeyond.com")
    notes: dict[str, Any] = Field(default_factory=dict)
