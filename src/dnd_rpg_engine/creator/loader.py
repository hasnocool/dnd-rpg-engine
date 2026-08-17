# src/dnd_rpg_engine/creator/loader.py
from __future__ import annotations

from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.creator.content import ContentPack


def install_content_pack(engine: GameEngine, pack: ContentPack) -> None:
    """Install validated content definitions into one running campaign engine."""
    installed = engine.state.metadata.setdefault("installed_content_packs", {})
    installed[f"{pack.manifest.id}@{pack.manifest.version}"] = pack.model_dump(mode="json")
    for action in pack.actions.values():
        engine.actions.register(action)
    for condition in pack.conditions.values():
        engine.conditions.register(condition)
    for item in pack.items.values():
        engine.items.register(item)
        engine.world.economy.register_item(item.id, item.value)
    for spell in pack.spells.values():
        engine.spells.register(spell)
    for world_map in pack.maps.values():
        engine.maps.register(world_map)
    for graph in pack.dialogues.values():
        engine.dialogues.register(graph)
    for quest in pack.quests.values():
        engine.register_quest(quest)
    for profile in pack.npcs.values():
        engine.npcs.register(profile)
    for shop in pack.shops.values():
        engine.shops.register(shop.model_copy(deep=True))
    for faction in pack.factions.values():
        engine.world.factions.register(faction.model_copy(deep=True))
    for schedule in pack.schedules.values():
        engine.world.schedules.register(schedule.model_copy(deep=True))
    for rule in pack.dynamic_events.values():
        engine.world.dynamic_events.register(rule.model_copy(deep=True))
    for personality in pack.personalities.values():
        engine.personalities.register(personality.model_copy(deep=True))
    for encounter in pack.encounters.values():
        engine.encounter_generator.register(encounter.model_copy(deep=True))
    register_scene = getattr(engine, "register_scene", None)
    if callable(register_scene):
        for scene in pack.scenes.values():
            register_scene(scene.model_copy(deep=True))
    for rule_id, document in pack.rules.items():
        engine.rule_documents[rule_id] = document.model_copy(deep=True)
