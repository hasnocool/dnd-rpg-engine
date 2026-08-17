import asyncio

import pytest

from dnd_rpg_engine.characters.models import CharacterBuildRequest
from dnd_rpg_engine.core.commands import AttackCommand, EndTurnCommand, MoveCommand, RestCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, Position, ResourcePool, Stats, TimeMode, GameConfig
from dnd_rpg_engine.rulesets.srd_5_2_1 import SRD_5_2_1_RULESET


def test_character_builder_and_turn_economy():
    async def scenario():
        engine = await GameEngine.create("characters", config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=99))
        engine.activate_rules(SRD_5_2_1_RULESET)
        hero = await engine.characters.build(CharacterBuildRequest(
            name="Hero", class_id="fighter", species_id="human", background_id="soldier",
            stats=Stats(strength=16, dexterity=14, constitution=14, intelligence=10, wisdom=10, charisma=10),
        ), entity_id="hero")
        target = Entity(id="target", name="Target", kind=EntityKind.CREATURE, controller=ControllerKind.NONE,
                        resources=ResourcePool(hp=30, max_hp=30), position=Position(x=1.5))
        await engine.add_entity(hero)
        await engine.add_entity(target)
        await engine.dispatch(MoveCommand(actor_id="hero", x=0.5, y=0))
        assert engine.characters.state(hero).turn.active
        assert "attack" in engine.characters.available_actions(hero)["available"]
        after_move = engine.characters.state(hero)
        assert after_move.turn.movement_remaining == 27.5
        assert after_move.turn.action_available
        assert "hero" in engine._ready_humans
        await engine.dispatch(AttackCommand(actor_id="hero", target_id="target"))
        after_attack = engine.characters.state(hero)
        assert not after_attack.turn.action_available
        with pytest.raises(ValueError, match="action already used"):
            await engine.dispatch(AttackCommand(actor_id="hero", target_id="target"))
        before_round = engine.characters.state(hero).turn.round_index
        await engine.dispatch(EndTurnCommand(actor_id="hero"))
        next_turn = engine.characters.state(hero).turn
        assert "hero" in engine._ready_humans
        assert next_turn.active
        assert next_turn.round_index == before_round + 1
        assert next_turn.action_available
    asyncio.run(scenario())


def test_rest_and_level_up_are_authoritative():
    async def scenario():
        engine = await GameEngine.create("recovery", config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=7))
        engine.activate_rules(SRD_5_2_1_RULESET)
        hero = await engine.characters.build(CharacterBuildRequest(
            name="Hero", class_id="fighter", species_id="human", background_id="soldier",
            stats=Stats(constitution=14),
        ), entity_id="hero")
        await engine.add_entity(hero)
        hero.resources.hp = max(1, hero.resources.max_hp - 5)
        before_world = engine.world.clock.total_minutes
        result = await engine.dispatch(RestCommand(actor_id="hero", rest_kind="short", hit_dice_to_spend=1))
        assert engine.world.clock.total_minutes == before_world + 60
        assert any(e.type == "character.rest_completed" for e in result.events)
        assert hero.resources.hp > 1
        state = await engine.characters.level_up(hero, target_level=2, reason="test")
        assert state.level == 2
        assert hero.resources.max_hp > 1
        assert hero.component("progression")["level"] == 2
    asyncio.run(scenario())


def test_reaction_window_consumes_reaction():
    async def scenario():
        engine = await GameEngine.create("reaction", config=GameConfig(time_mode=TimeMode.TURN_BASED))
        hero = await engine.characters.build(CharacterBuildRequest(
            name="Hero", class_id="fighter", species_id="human", background_id="soldier"
        ), entity_id="hero")
        await engine.add_entity(hero)
        await engine.dispatch(MoveCommand(actor_id="hero", x=0, y=0))
        window = await engine.open_reaction_window(trigger_event_id="evt", eligible_actor_ids={"hero"}, allowed_reactions={"defend"})
        from dnd_rpg_engine.core.commands import ReactionCommand
        result = await engine.dispatch(ReactionCommand(actor_id="hero", window_id=window, reaction_id="defend"))
        assert any(e.type == "reaction.resolved" for e in result.events)
        assert not engine.characters.state(hero).turn.reaction_available
    asyncio.run(scenario())
