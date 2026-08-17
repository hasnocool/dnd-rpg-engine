# src/dnd_rpg_engine/creator/content.py
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from typing import Any

from pydantic import BaseModel, Field, field_validator

from dnd_rpg_engine.adventure.dialogue import DialogueGraph
from dnd_rpg_engine.adventure.maps import WorldMap
from dnd_rpg_engine.adventure.quests import QuestDefinition
from dnd_rpg_engine.adventure.npcs import NPCProfile
from dnd_rpg_engine.adventure.shops import Shop
from dnd_rpg_engine.living.factions import Faction
from dnd_rpg_engine.living.schedules import NPCSchedule
from dnd_rpg_engine.living.dynamic_events import DynamicEventDefinition
from dnd_rpg_engine.ai.personalities import Personality
from dnd_rpg_engine.ai.encounters import EncounterTemplate
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.conditions import ConditionDefinition
from dnd_rpg_engine.tactical.items import ItemDefinition
from dnd_rpg_engine.tactical.spells import SpellDefinition
from dnd_rpg_engine.core.models import Entity, GameConfig
from dnd_rpg_engine.core.rules import RuleSet

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,63}$")


class ModManifest(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    engine_version: str = ">=1.0.0"
    author: str = "unknown"
    description: str = ""
    license: str = "unspecified"
    dependencies: dict[str, str] = Field(default_factory=dict)
    tags: set[str] = Field(default_factory=set)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not _ID_RE.match(value):
            raise ValueError("mod id must be lowercase and URL/path safe")
        return value


class CreatureTemplate(BaseModel):
    id: str
    name: str
    tier: int = Field(default=1, ge=1, le=100)
    hp: int = Field(default=10, ge=1)
    stats: dict[str, int] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=lambda: ["basic_attack"])
    tags: set[str] = Field(default_factory=set)
    ai_profile: str = "hostile_basic"


class CampaignTemplate(BaseModel):
    id: str
    name: str
    description: str = ""
    config: GameConfig = Field(default_factory=GameConfig)
    active_rule_id: str | None = None
    start_map_id: str | None = None
    entities: list[Entity] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)


class RuleDocument(BaseModel):
    id: str
    name: str
    settings: dict[str, Any] = Field(default_factory=dict)
    expressions: dict[str, str] = Field(default_factory=dict)

    def to_ruleset(self) -> RuleSet:
        allowed = set(RuleSet.model_fields) - {"id", "name"}
        safe_settings = {key: value for key, value in self.settings.items() if key in allowed}
        return RuleSet(id=self.id, name=self.name, **safe_settings)


class ContentPack(BaseModel):
    manifest: ModManifest
    campaigns: dict[str, CampaignTemplate] = Field(default_factory=dict)
    creatures: dict[str, CreatureTemplate] = Field(default_factory=dict)
    actions: dict[str, ActionDefinition] = Field(default_factory=dict)
    conditions: dict[str, ConditionDefinition] = Field(default_factory=dict)
    items: dict[str, ItemDefinition] = Field(default_factory=dict)
    spells: dict[str, SpellDefinition] = Field(default_factory=dict)
    maps: dict[str, WorldMap] = Field(default_factory=dict)
    dialogues: dict[str, DialogueGraph] = Field(default_factory=dict)
    quests: dict[str, QuestDefinition] = Field(default_factory=dict)
    npcs: dict[str, NPCProfile] = Field(default_factory=dict)
    shops: dict[str, Shop] = Field(default_factory=dict)
    factions: dict[str, Faction] = Field(default_factory=dict)
    schedules: dict[str, NPCSchedule] = Field(default_factory=dict)
    dynamic_events: dict[str, DynamicEventDefinition] = Field(default_factory=dict)
    personalities: dict[str, Personality] = Field(default_factory=dict)
    encounters: dict[str, EncounterTemplate] = Field(default_factory=dict)
    rules: dict[str, RuleDocument] = Field(default_factory=dict)
    assets: dict[str, str] = Field(default_factory=dict)

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    def to_zip_bytes(self) -> bytes:
        buffer = io.BytesIO()
        payload = self.model_dump(mode="json")
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(payload["manifest"], indent=2, sort_keys=True))
            for section in (
                "campaigns",
                "creatures",
                "actions",
                "conditions",
                "items",
                "spells",
                "maps",
                "dialogues",
                "quests",
                "npcs",
                "shops",
                "factions",
                "schedules",
                "dynamic_events",
                "personalities",
                "encounters",
                "rules",
                "assets",
            ):
                archive.writestr(f"content/{section}.json", json.dumps(payload[section], indent=2, sort_keys=True))
        return buffer.getvalue()

    @classmethod
    def from_zip_bytes(cls, data: bytes, *, max_uncompressed_bytes: int = 20_000_000) -> ContentPack:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            total = sum(info.file_size for info in archive.infolist())
            if total > max_uncompressed_bytes:
                raise ValueError("content pack exceeds uncompressed size limit")
            names = set(archive.namelist())
            for name in names:
                if name.startswith("/") or ".." in name.split("/"):
                    raise ValueError("unsafe archive path")
            manifest = json.loads(archive.read("manifest.json"))
            payload: dict[str, Any] = {"manifest": manifest}
            for section in (
                "campaigns",
                "creatures",
                "actions",
                "conditions",
                "items",
                "spells",
                "maps",
                "dialogues",
                "quests",
                "npcs",
                "shops",
                "factions",
                "schedules",
                "dynamic_events",
                "personalities",
                "encounters",
                "rules",
                "assets",
            ):
                path = f"content/{section}.json"
                payload[section] = json.loads(archive.read(path)) if path in names else {}
            return cls.model_validate(payload)


class ContentValidator:
    def validate(self, pack: ContentPack) -> list[str]:
        errors: list[str] = []
        for campaign in pack.campaigns.values():
            if campaign.start_map_id and campaign.start_map_id not in pack.maps:
                errors.append(f"campaign {campaign.id} references missing start map {campaign.start_map_id}")
            if campaign.active_rule_id and campaign.active_rule_id not in pack.rules:
                errors.append(f"campaign {campaign.id} references missing rule {campaign.active_rule_id}")
        action_ids = set(pack.actions)
        for creature in pack.creatures.values():
            missing = [action_id for action_id in creature.actions if action_id not in action_ids and action_id != "basic_attack"]
            if missing:
                errors.append(f"creature {creature.id} references missing actions: {', '.join(missing)}")
        condition_ids = set(pack.conditions)
        for spell in pack.spells.values():
            if spell.applies_condition and spell.applies_condition not in condition_ids and spell.applies_condition not in {"slowed", "stunned", "guarded", "burning_arcane"}:
                errors.append(f"spell {spell.id} references missing condition {spell.applies_condition}")
        for world_map in pack.maps.values():
            for edge in world_map.edges:
                if edge.source not in world_map.nodes or edge.target not in world_map.nodes:
                    errors.append(f"map {world_map.id} has edge with missing node: {edge.source}->{edge.target}")
        return errors
