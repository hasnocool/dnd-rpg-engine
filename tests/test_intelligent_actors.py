# tests/test_intelligent_actors.py
from __future__ import annotations

from dnd_rpg_engine.ai.intelligence import Goal, GoalKind, IntelligentActorController, PersistentActorMemory
from dnd_rpg_engine.core.models import CampaignState, ControllerKind, Entity, EntityKind, Position, ResourcePool
from dnd_rpg_engine.tactical.actions import ActionDefinition


def make_state(*, actor_hp: int = 10) -> tuple[CampaignState, Entity, Entity]:
    actor = Entity(
        id="goblin",
        name="Goblin",
        kind=EntityKind.CREATURE,
        controller=ControllerKind.AI,
        resources=ResourcePool(hp=actor_hp, max_hp=10),
        position=Position(area_id="room", x=0, y=0),
        components={"ai": {"target_id": "hero", "hostile": True}},
    )
    hero = Entity(
        id="hero",
        name="Hero",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        resources=ResourcePool(hp=10, max_hp=10),
        position=Position(area_id="room", x=1, y=0),
    )
    state = CampaignState(id="campaign", name="AI test", entities={actor.id: actor, hero.id: hero})
    return state, actor, hero


def test_healthy_actor_prefers_attack_in_range() -> None:
    state, actor, _ = make_state(actor_hp=10)
    controller = IntelligentActorController()
    action = ActionDefinition(id="claw", name="Claw", range=1.5, damage="1d4")
    command, perception, candidate = controller.plan(
        actor,
        state,
        action=action,
        goals=[Goal(id="win", kind=GoalKind.DEFEAT, weight=1.0, target_id="hero", tags={"defeat"})],
    )
    assert command.type == "attack"
    assert candidate.id == "attack"
    assert perception.nearby_hostiles == 1
    assert actor.component("agent_memory")["entries"]


def test_wounded_outnumbered_actor_prefers_survival() -> None:
    state, actor, _ = make_state(actor_hp=2)
    state.entities["hero2"] = Entity(
        id="hero2",
        name="Hero Two",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        position=Position(area_id="room", x=1.2, y=0),
    )
    controller = IntelligentActorController()
    action = ActionDefinition(id="claw", name="Claw", range=1.5, damage="1d4")
    command, _, candidate = controller.plan(
        actor,
        state,
        action=action,
        goals=[Goal(id="live", kind=GoalKind.SURVIVE, weight=2.0, tags={"survive", "flee"})],
    )
    assert command.type == "move"
    assert candidate.id == "flee"


def test_actor_memory_is_component_backed_and_filterable() -> None:
    _, actor, _ = make_state()
    memory = PersistentActorMemory(actor)
    memory.add(simulation_time=1, text="Saw the hero", importance=0.8, tags={"sighting"}, subject_id="hero")
    memory.add(simulation_time=2, text="Found food", importance=0.2, tags={"resource"})
    recalled = memory.recall(now=3, tags={"sighting"})
    assert [entry.text for entry in recalled] == ["Saw the hero"]
    assert len(actor.component("agent_memory")["entries"]) >= 2
