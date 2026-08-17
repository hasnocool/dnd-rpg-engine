import asyncio
from pathlib import Path

import pytest

from dnd_rpg_engine.adventure.maps import AreaEdge, AreaNode, WorldMap
from dnd_rpg_engine.campaign.package import export_campaign_package, import_campaign_package
from dnd_rpg_engine.characters.models import CharacterBuildRequest
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import GameConfig, TimeMode
from dnd_rpg_engine.multiplayer.protocol import ClientIdentity
from dnd_rpg_engine.multiplayer.sessions import CampaignSession


def test_campaign_runner_travel_and_director(tmp_path: Path):
    async def scenario():
        engine = await GameEngine.create("campaign", config=GameConfig(time_mode=TimeMode.TURN_BASED))
        world_map = WorldMap(
            id="world", name="World",
            nodes={"a": AreaNode(id="a", name="A"), "b": AreaNode(id="b", name="B", x=2)},
            edges=[AreaEdge(source="a", target="b", travel_time=2)],
        )
        engine.maps.register(world_map)
        hero = await engine.characters.build(CharacterBuildRequest(
            name="Hero", class_id="fighter", species_id="human", background_id="soldier"
        ), entity_id="hero")
        hero.position.area_id = "world"; hero.position.node_id = "a"
        await engine.add_entity(hero)
        engine.campaign_runner.configure_party({"hero"}, map_id="world", node_id="a")
        result = await engine.campaign_runner.travel("hero", "world", "b", "normal")
        assert result.world_minutes == 120
        assert hero.position.node_id == "b"
        suggestion = await engine.director.suggest()
        assert suggestion.kind in {"explore", "rest"}
        out = tmp_path / "campaign.json"
        package = export_campaign_package(engine.state, out)
        loaded = import_campaign_package(out)
        assert loaded.sha256 == package.sha256
        assert loaded.campaign.id == engine.state.id
    asyncio.run(scenario())


def test_multiplayer_reconnect_and_in_memory_replay():
    async def scenario():
        engine = await GameEngine.create("multi")
        session = CampaignSession(engine.state.id, engine, owner_id="owner")
        identity = ClientIdentity(user_id="owner", display_name="Owner")
        session.join(identity)
        await engine._emit("test.event", payload={"ok": True})
        session.leave(identity.client_id)
        assert not session.connections[identity.client_id].connected
        session.reconnect(identity.client_id, "owner")
        assert session.connections[identity.client_id].connected
        events = await session.replay(identity.client_id)
        assert events[-1].type == "test.event"
        with pytest.raises(PermissionError):
            session.reconnect(identity.client_id, "someone-else")
    asyncio.run(scenario())


def test_character_package_checksum_is_stable():
    async def scenario():
        from dnd_rpg_engine.characters.package import CharacterPackage
        engine = await GameEngine.create("package")
        hero = await engine.characters.build(CharacterBuildRequest(
            name="Hero", class_id="fighter", species_id="human", background_id="soldier",
            skill_proficiencies={"athletics", "perception"},
        ), entity_id="hero")
        package = CharacterPackage.from_entity(hero, engine.characters.state(hero))
        reparsed = CharacterPackage.model_validate_json(package.model_dump_json())
        reparsed.verify()
        assert reparsed.sha256 == package.sha256
    asyncio.run(scenario())


def test_creator_studio_roundtrip_and_director_adaptation():
    async def scenario():
        from dnd_rpg_engine.creator.content import ContentPack, ModManifest, RuleDocument
        from dnd_rpg_engine.creator.studio import CreatorStudio
        pack = ContentPack(manifest=ModManifest(id="studio.test", name="Studio"), rules={
            "core": RuleDocument(id="core", name="Core", settings={})
        })
        studio = CreatorStudio()
        inspected = studio.inspect(pack)
        assert inspected["counts"]["rules"] == 1
        engine = await GameEngine.create("director")
        adapted = engine.director.adapt_after_events(["quest.completed", "combat.entity_defeated"])
        assert adapted == {"pressure": 1, "social_momentum": 1}
    asyncio.run(scenario())
