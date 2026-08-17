# src/dnd_rpg_engine/rulesets/srd_5_2_1/extended_models.py
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CatalogSection(StrEnum):
    SPELLS = "spells"
    CLASS_FEATURES = "class_features"
    CLASS_PROGRESSIONS = "class_progressions"
    SUBCLASSES = "subclasses"
    FEATS = "feats"
    MAGIC_ITEMS = "magic_items"
    MONSTERS = "monsters"
    TRAVEL = "travel"
    ENVIRONMENT = "environment"
    ENCOUNTERS = "encounters"


class SourceRef(BaseModel):
    source_page: int = Field(ge=1, le=1000)
    source_section: str
    source_hash: str | None = None


class DiceExpression(BaseModel):
    expression: str
    damage_type: str | None = None


class SpellCatalogEntry(BaseModel):
    id: str
    name: str
    level: int = Field(ge=0, le=9)
    school: str
    classes: tuple[str, ...] = ()
    casting_time: str = ""
    range: str = ""
    components: tuple[str, ...] = ()
    duration: str = ""
    concentration: bool = False
    ritual: bool = False
    save_ability: str | None = None
    attack_kind: str | None = None
    damage: tuple[DiceExpression, ...] = ()
    healing: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    area_tags: tuple[str, ...] = ()
    source: SourceRef
    mechanics_hash: str


class ClassFeatureEntry(BaseModel):
    id: str
    name: str
    class_id: str
    level: int = Field(ge=1, le=20)
    subclass_id: str | None = None
    tags: tuple[str, ...] = ()
    source: SourceRef
    mechanics_hash: str


class ClassProgressionLevel(BaseModel):
    class_id: str
    level: int = Field(ge=1, le=20)
    proficiency_bonus: int = Field(ge=2, le=6)
    feature_ids: tuple[str, ...] = ()
    subclass_feature_ids: tuple[str, ...] = ()
    spell_slots: tuple[int, ...] = ()

    @property
    def id(self) -> str:
        return f"{self.class_id}.{self.level}"


class SubclassDefinition(BaseModel):
    id: str
    name: str
    class_id: str
    source: SourceRef
    feature_ids: tuple[str, ...] = ()


class FeatCatalogEntry(BaseModel):
    id: str
    name: str
    category: str
    repeatable: bool = False
    prerequisites: tuple[str, ...] = ()
    source: SourceRef


class MagicItemCatalogEntry(BaseModel):
    id: str
    name: str
    category: str
    rarity: str | None = None
    attunement: bool = False
    charges: int | None = Field(default=None, ge=0)
    tags: tuple[str, ...] = ()
    source: SourceRef
    mechanics_hash: str


class MonsterCatalogEntry(BaseModel):
    id: str
    name: str
    size: str | None = None
    creature_type: str | None = None
    alignment: str | None = None
    armor_class: int | None = Field(default=None, ge=0, le=50)
    hit_points: int | None = Field(default=None, ge=0)
    hit_points_formula: str | None = None
    speed: str | None = None
    initiative: int | None = None
    abilities: dict[str, int] = Field(default_factory=dict)
    saves: dict[str, int] = Field(default_factory=dict)
    challenge_rating: str | None = None
    xp: int | None = Field(default=None, ge=0)
    resistances: tuple[str, ...] = ()
    immunities: tuple[str, ...] = ()
    vulnerabilities: tuple[str, ...] = ()
    senses: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    skills: dict[str, int] = Field(default_factory=dict)
    source: SourceRef
    stat_block_hash: str


class TravelPaceDefinition(BaseModel):
    id: str
    feet_per_minute: int = Field(gt=0)
    miles_per_hour: int = Field(gt=0)
    miles_per_day: int = Field(gt=0)
    perception_survival_mode: str = "normal"
    stealth_mode: str = "normal"
    source_page: int = 192


class TerrainTravelRule(BaseModel):
    id: str
    pace: str
    encounter_distance: str
    foraging_dc: int = Field(ge=0)
    navigation_dc: int = Field(ge=0)
    search_dc: int = Field(ge=0)
    source_page: int = 192


class EnvironmentalRule(BaseModel):
    id: str
    name: str
    check_ability: str | None = None
    dc: int | None = Field(default=None, ge=0)
    interval_seconds: float | None = Field(default=None, gt=0)
    consequence: str | None = None
    tags: tuple[str, ...] = ()
    source_page: int = Field(ge=1)


class EncounterBudgetDefinition(BaseModel):
    level: int = Field(ge=1, le=20)
    low: int = Field(ge=0)
    moderate: int = Field(ge=0)
    high: int = Field(ge=0)
    source_page: int = 202


class EncounterCandidate(BaseModel):
    monster_ids: tuple[str, ...]
    total_xp: int
    budget: int
    utilization: float = Field(ge=0)


class CompilationDiagnostic(BaseModel):
    severity: str
    section: str
    source_page: int | None = None
    message: str


class CompiledCatalogManifest(BaseModel):
    schema_version: int = 1
    srd_version: str = "5.2.1"
    source_sha256: str
    source_pages: int = Field(ge=1)
    compiled_at: str
    section_counts: dict[str, int] = Field(default_factory=dict)
    omitted_sections: dict[str, str] = Field(default_factory=dict)
    diagnostics: list[CompilationDiagnostic] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
