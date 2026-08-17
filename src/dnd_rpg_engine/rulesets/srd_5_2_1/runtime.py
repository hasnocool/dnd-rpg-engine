# src/dnd_rpg_engine/rulesets/srd_5_2_1/runtime.py
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, Position, ResourcePool, Stats
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog_store import SRDCatalogStore
from dnd_rpg_engine.rulesets.srd_5_2_1.extended_models import CatalogSection, EncounterCandidate, MonsterCatalogEntry, SpellCatalogEntry
from dnd_rpg_engine.rulesets.srd_5_2_1.toolbox import build_encounter_candidate
from dnd_rpg_engine.tactical.spells import SpellDefinition


class SRDRuntimeCatalog:
    """Offline SRD query/adapter layer used after PDF compilation."""

    def __init__(self, path: str | Path) -> None:
        self.store = SRDCatalogStore(path)

    async def initialize(self) -> None:
        await self.store.initialize()

    async def install_simple_spells(self, engine: "GameEngine") -> int:
        """Register mechanically simple compiled spells in the existing combat registry.

        Complex SRD spells remain queryable in the catalog rather than being
        inaccurately reduced to the engine's small SpellDefinition model.
        """
        rows = await self.store.search(CatalogSection.SPELLS.value, limit=5000)
        installed = 0
        for raw in rows:
            entry = SpellCatalogEntry.model_validate(raw)
            runtime = to_runtime_spell(entry)
            if runtime is None:
                continue
            engine.spells.register(runtime)
            installed += 1
        return installed

    async def encounter_candidate(
        self,
        party_levels: list[int],
        *,
        difficulty: str = "moderate",
        query: str = "",
    ) -> EncounterCandidate:
        rows = await self.store.search(CatalogSection.MONSTERS.value, query, limit=5000)
        candidates = []
        for raw in rows:
            monster = MonsterCatalogEntry.model_validate(raw)
            if monster.challenge_rating is not None:
                candidates.append((monster.id, monster.challenge_rating))
        return build_encounter_candidate(candidates, party_levels, difficulty=difficulty)

    async def monster_entity(
        self,
        monster_id: str,
        *,
        entity_id: str | None = None,
        position: Position | None = None,
        controller: ControllerKind = ControllerKind.AI,
    ) -> Entity:
        raw = await self.store.get(CatalogSection.MONSTERS.value, monster_id)
        if raw is None:
            raise KeyError(f"unknown SRD monster: {monster_id}")
        monster = MonsterCatalogEntry.model_validate(raw)
        abilities = monster.abilities
        return Entity(
            id=entity_id or monster.id,
            name=monster.name,
            kind=EntityKind.CREATURE,
            controller=controller,
            stats=Stats(
                strength=abilities.get("str", 10),
                dexterity=abilities.get("dex", 10),
                constitution=abilities.get("con", 10),
                intelligence=abilities.get("int", 10),
                wisdom=abilities.get("wis", 10),
                charisma=abilities.get("cha", 10),
            ),
            resources=ResourcePool(hp=monster.hit_points or 1, max_hp=monster.hit_points or 1),
            position=position or Position(),
            tags={"srd_5_2_1", monster.creature_type or "creature"},
            components={
                "srd": {
                    "monster_id": monster.id,
                    "challenge_rating": monster.challenge_rating,
                    "xp": monster.xp,
                    "armor_class": monster.armor_class,
                    "speed": monster.speed,
                    "resistances": list(monster.resistances),
                    "immunities": list(monster.immunities),
                    "vulnerabilities": list(monster.vulnerabilities),
                },
                "combat": {"armor_class": monster.armor_class} if monster.armor_class is not None else {},
                "ai": {"action_id": "basic_attack"},
            },
        )


def to_runtime_spell(entry: SpellCatalogEntry) -> SpellDefinition | None:
    damage = entry.damage[0].expression if len(entry.damage) == 1 else None
    heal = entry.healing[0] if len(entry.healing) == 1 else None
    condition = entry.conditions[0] if len(entry.conditions) == 1 else None
    if damage is None and heal is None and condition is None:
        return None
    tags = {"srd_5_2_1", entry.school.lower()}
    if entry.ritual:
        tags.add("ritual")
    if entry.concentration:
        tags.add("concentration")
    return SpellDefinition(
        id=entry.id,
        name=entry.name,
        level=entry.level,
        school=entry.school,
        classes=set(entry.classes),
        cast_time=_cast_time_seconds(entry.casting_time),
        range=_range_units(entry.range),
        energy_cost=max(0, entry.level),
        save_ability=entry.save_ability,
        damage=damage,
        heal=heal,
        damage_type=entry.damage[0].damage_type if entry.damage else "arcane",
        applies_condition=condition,
        concentration=entry.concentration,
        ritual=entry.ritual,
        components=entry.components,
        interruptible=entry.concentration or entry.level > 0,
        tags=tags,
    )


def _cast_time_seconds(value: str) -> float:
    lower = value.lower()
    if "bonus action" in lower:
        return 3.0
    if "reaction" in lower:
        return 1.0
    match = re.search(r"(\d+)\s+minute", lower)
    if match:
        return float(int(match.group(1)) * 60)
    match = re.search(r"(\d+)\s+hour", lower)
    if match:
        return float(int(match.group(1)) * 3600)
    return 6.0


def _range_units(value: str) -> float:
    lower = value.lower()
    if "self" in lower or "touch" in lower:
        return 0.0 if "self" in lower else 1.0
    match = re.search(r"(\d+)\s*feet", lower)
    if match:
        return max(0.0, int(match.group(1)) / 5.0)
    match = re.search(r"(\d+)\s*mile", lower)
    if match:
        return float(int(match.group(1)) * 1056)
    return 12.0
