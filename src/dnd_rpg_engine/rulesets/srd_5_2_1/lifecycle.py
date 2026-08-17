# src/dnd_rpg_engine/rulesets/srd_5_2_1/lifecycle.py
from __future__ import annotations

from dnd_rpg_engine.characters.lifecycle import AdvancementTrack, CharacterClassDefinition, CharacterLifecycle
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog import CLASSES


def build_srd_character_lifecycle(
    *,
    advancement_track: AdvancementTrack | None = None,
) -> CharacterLifecycle:
    """Create a lifecycle catalog from the compact SRD class metadata.

    This adapter deliberately consumes only mechanics already represented by
    the source-backed SRD catalog. Detailed class progression rows can be
    registered later without changing the lifecycle or engine contracts.
    """

    definitions: dict[str, CharacterClassDefinition] = {}
    for class_id, source in CLASSES.items():
        definitions[class_id] = CharacterClassDefinition(
            id=source.id,
            name=source.name,
            hit_die=source.hit_die,
            primary_abilities=tuple(ability.value for ability in source.primary_abilities),
            saving_throw_proficiencies=tuple(ability.value for ability in source.saving_throw_proficiencies),
            spellcasting_ability=source.spellcasting_ability.value if source.spellcasting_ability is not None else None,
            tags={"srd_5_2_1"},
        )
    return CharacterLifecycle(advancement_track=advancement_track, classes=definitions)
