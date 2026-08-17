# tests/test_srd_runtime.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog_store import SRDCatalogStore
from dnd_rpg_engine.rulesets.srd_5_2_1.extended_models import CompiledCatalogManifest
from dnd_rpg_engine.rulesets.srd_5_2_1.runtime import SRDRuntimeCatalog


def test_runtime_catalog_registers_simple_spells_and_builds_monster_entity(tmp_path) -> None:
    asyncio.run(_runtime_catalog_registers_simple_spells_and_builds_monster_entity(tmp_path))


async def _runtime_catalog_registers_simple_spells_and_builds_monster_entity(tmp_path) -> None:
    path = tmp_path / "srd.sqlite3"
    store = SRDCatalogStore(path)
    await store.initialize()
    source = {"source_page": 107, "source_section": "Spells", "source_hash": None}
    await store.replace_section(
        "spells",
        [
            {
                "id": "arc_spark",
                "name": "Arc Spark",
                "level": 1,
                "school": "Evocation",
                "classes": ["wizard"],
                "casting_time": "Action",
                "range": "60 feet",
                "components": ["V", "S"],
                "duration": "Instantaneous",
                "concentration": False,
                "ritual": False,
                "save_ability": "dexterity",
                "attack_kind": None,
                "damage": [{"expression": "2d6", "damage_type": "lightning"}],
                "healing": [],
                "conditions": [],
                "area_tags": [],
                "source": source,
                "mechanics_hash": "x",
            }
        ],
    )
    await store.replace_section(
        "monsters",
        [
            {
                "id": "moss_guardian",
                "name": "Moss Guardian",
                "size": "medium",
                "creature_type": "Plant",
                "alignment": "Unaligned",
                "armor_class": 13,
                "hit_points": 22,
                "hit_points_formula": "4d8 + 4",
                "speed": "30 ft.",
                "initiative": 1,
                "abilities": {"str": 14, "dex": 12, "con": 12, "int": 6, "wis": 14, "cha": 8},
                "saves": {},
                "challenge_rating": "1",
                "xp": 200,
                "resistances": ["Cold"],
                "immunities": [],
                "vulnerabilities": [],
                "senses": ["Darkvision 60 ft.", "Passive Perception 14"],
                "languages": ["Sylvan"],
                "skills": {"perception": 4},
                "source": {"source_page": 258, "source_section": "Monsters", "source_hash": None},
                "stat_block_hash": "y",
            }
        ],
    )
    await store.put_manifest(
        CompiledCatalogManifest(source_sha256="abc", source_pages=364, compiled_at=datetime.now(UTC).isoformat())
    )

    runtime = SRDRuntimeCatalog(path)
    await runtime.initialize()
    engine = await GameEngine.create("runtime")
    assert await runtime.install_simple_spells(engine) == 1
    spell = engine.spells.require("arc_spark")
    assert spell.level == 1
    assert spell.damage == "2d6"
    assert spell.range == 12.0

    monster = await runtime.monster_entity("moss_guardian")
    assert monster.resources.max_hp == 22
    assert monster.stats.strength == 14
    assert monster.component("combat")["armor_class"] == 13
