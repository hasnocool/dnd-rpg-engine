# tests/test_srd_compiler.py
from __future__ import annotations

import asyncio

from dnd_rpg_engine.rulesets.srd_5_2_1.catalog_store import SRDCatalogStore
from dnd_rpg_engine.rulesets.srd_5_2_1.compiler import SRDDocument, compile_document


def _synthetic_document() -> SRDDocument:
    pages = [""] * 364
    pages[0] = "System Reference Document 5.2.1\nLegal Information"
    pages[27] = """
Barbarian
Level 1: Primal Focus
A compact synthetic feature used only by the parser test.
"""
    pages[29] = """
Path of the Berserker
Level 3: Focused Fury
A compact synthetic subclass feature used only by the parser test.
"""
    pages[106] = """
Arc Spark
Level 1 Evocation (Wizard)
Casting Time: Action
Range: 60 feet
Components: V, S
Duration: Instantaneous
Dexterity Saving Throw: a target tests its agility.
Failure: 2d6 Lightning damage.

Quiet Light
Evocation Cantrip (Cleric, Wizard)
Casting Time: Action
Range: 30 feet
Components: V
Duration: 1 minute
A harmless light appears.
"""
    pages[208] = """
Lantern of Quiet Stars
Wondrous Item, Uncommon (Requires Attunement)
This item has 3 charges. Its light can be dimmed.

Ring of Calm
Ring, Rare
A compact synthetic description.
"""
    pages[257] = """
Moss Guardian
Moss Guardian
Medium Plant, Unaligned
AC 13 Initiative +1 (11)
HP 22 (4d8 + 4)
Speed 30 ft.
MOD SAVE MOD SAVE MOD SAVE
Str 14 +2 +2 Dex 12 +1 +1 Con 12 +1 +1
Int 6 -2 -2 Wis 14 +2 +2 Cha 8 -1 -1
Skills Perception +4
Resistances Cold
Senses Darkvision 60 ft.; Passive Perception 14
Languages Sylvan
CR 1 (XP 200; PB +2)
Traits
Photosynthesis. Synthetic parser-test text.
"""
    return SRDDocument.from_pages(pages, source_sha256="synthetic-sha")


def test_compiler_builds_offline_catalog_without_source_prose(tmp_path) -> None:
    asyncio.run(_compiler_builds_offline_catalog_without_source_prose(tmp_path))


async def _compiler_builds_offline_catalog_without_source_prose(tmp_path) -> None:
    db = tmp_path / "srd.sqlite3"
    manifest = await compile_document(_synthetic_document(), db)
    store = SRDCatalogStore(db)

    assert manifest.section_counts["spells"] == 2
    assert manifest.section_counts["magic_items"] == 2
    assert manifest.section_counts["monsters"] == 1
    assert manifest.section_counts["class_progressions"] == 240
    assert manifest.section_counts["subclasses"] == 12
    assert manifest.section_counts["feats"] >= 15
    assert manifest.section_counts["encounters"] == 20
    assert "weapon_catalog_and_masteries" in manifest.omitted_sections

    spell = await store.get("spells", "arc_spark")
    assert spell is not None
    assert spell["level"] == 1
    assert spell["save_ability"] == "dexterity"
    assert spell["damage"][0]["expression"] == "2d6"

    monster = await store.get("monsters", "moss_guardian")
    assert monster is not None
    assert monster["armor_class"] == 13
    assert monster["hit_points"] == 22
    assert monster["challenge_rating"] == "1"
    assert "actions" not in monster
    assert "gear" not in monster

    raw_db = db.read_bytes()
    assert b"Photosynthesis. Synthetic parser-test text." not in raw_db
    assert b"A compact synthetic feature used only by the parser test." not in raw_db
