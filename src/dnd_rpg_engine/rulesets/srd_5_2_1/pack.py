# src/dnd_rpg_engine/rulesets/srd_5_2_1/pack.py
from __future__ import annotations

from dnd_rpg_engine.creator.content import ContentPack, ModManifest, RuleDocument
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog import BACKGROUNDS, CLASSES, FEATS, SKILLS, SPECIES
from dnd_rpg_engine.rulesets.srd_5_2_1.rules import SRD_5_2_1_RULESET
from dnd_rpg_engine.rulesets.srd_5_2_1.source import OFFICIAL_SRD_SOURCE
from dnd_rpg_engine.tactical.conditions import ConditionDefinition


def _conditions() -> dict[str, ConditionDefinition]:
    return {
        "blinded": ConditionDefinition(id="blinded", name="Blinded", attack_roll_mode="disadvantage", attacks_against_mode="advantage", tags={"sight_blocked"}),
        "charmed": ConditionDefinition(id="charmed", name="Charmed", tags={"social_constraint"}),
        "deafened": ConditionDefinition(id="deafened", name="Deafened", tags={"hearing_blocked"}),
        "exhaustion": ConditionDefinition(id="exhaustion", name="Exhaustion", tags={"cumulative"}),
        "frightened": ConditionDefinition(id="frightened", name="Frightened", tags={"fear"}),
        "grappled": ConditionDefinition(id="grappled", name="Grappled", movement_multiplier=0.0, tags={"speed_zero"}),
        "incapacitated": ConditionDefinition(id="incapacitated", name="Incapacitated", blocks_actions=True, tags={"no_bonus_action", "no_reaction"}),
        "invisible": ConditionDefinition(id="invisible", name="Invisible", attack_roll_mode="advantage", attacks_against_mode="disadvantage", tags={"concealed"}),
        "paralyzed": ConditionDefinition(id="paralyzed", name="Paralyzed", movement_multiplier=0.0, blocks_actions=True, attacks_against_mode="advantage", tags={"speed_zero", "no_reaction"}),
        "petrified": ConditionDefinition(id="petrified", name="Petrified", movement_multiplier=0.0, blocks_actions=True, attacks_against_mode="advantage", tags={"speed_zero", "damage_resistant_all"}),
        "poisoned": ConditionDefinition(id="poisoned", name="Poisoned", attack_roll_mode="disadvantage", tags={"ability_checks_disadvantage"}),
        "prone": ConditionDefinition(id="prone", name="Prone", tags={"crawl_or_stand"}),
        "restrained": ConditionDefinition(id="restrained", name="Restrained", movement_multiplier=0.0, attack_roll_mode="disadvantage", attacks_against_mode="advantage", tags={"speed_zero", "dex_save_disadvantage"}),
        "stunned": ConditionDefinition(id="stunned", name="Stunned", movement_multiplier=0.0, blocks_actions=True, attacks_against_mode="advantage", tags={"speed_zero", "no_reaction"}),
        "unconscious": ConditionDefinition(id="unconscious", name="Unconscious", movement_multiplier=0.0, blocks_actions=True, attacks_against_mode="advantage", tags={"speed_zero", "prone", "no_reaction"}),
    }


def build_srd_5_2_1_pack() -> ContentPack:
    """Build the bundled structured SRD rules foundation.

    The pack intentionally stores mechanics, identifiers, and source provenance,
    not long-form SRD prose. This keeps the engine data-oriented and lets the
    official SRD remain the human-readable source of truth.
    """
    catalog = {
        "source": OFFICIAL_SRD_SOURCE.model_dump(mode="json"),
        "skills": {key: value.model_dump(mode="json") for key, value in SKILLS.items()},
        "classes": {key: value.model_dump(mode="json") for key, value in CLASSES.items()},
        "species": {key: value.model_dump(mode="json") for key, value in SPECIES.items()},
        "backgrounds": {key: value.model_dump(mode="json") for key, value in BACKGROUNDS.items()},
        "feats": {key: value.model_dump(mode="json") for key, value in FEATS.items()},
        "coverage": {
            "implemented": [
                "d20 ability modifiers",
                "proficiency progression",
                "skills and expertise",
                "armor-class baseline",
                "advantage/disadvantage attack resolution",
                "temporary hit points",
                "death saving throws",
                "core conditions",
                "class/species/background/feat catalogs",
                "six-second round mapping",
            ],
            "source_of_truth": OFFICIAL_SRD_SOURCE.release_page,
            "prose_bundled": False,
        },
    }
    return ContentPack(
        manifest=ModManifest(
            id="srd_5_2_1",
            name="Fifth Edition SRD 5.2.1 Rules Foundation",
            version="1.0.0",
            engine_version=">=1.1.0",
            author="dnd-rpg-engine contributors",
            description="Structured runtime mechanics sourced from the CC-licensed SRD 5.2.1 release.",
            license="CC-BY-4.0",
            tags={"5e-compatible", "srd", "ruleset"},
        ),
        conditions=_conditions(),
        rules={
            "srd_5_2_1.core": RuleDocument(
                id="srd_5_2_1.core",
                name="Fifth Edition SRD 5.2.1",
                settings=SRD_5_2_1_RULESET.model_dump(mode="json", exclude={"id", "name"}),
            )
        },
        rules_data=catalog,
    )
