# tests/test_living_world.py
from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import CampaignState
from dnd_rpg_engine.living.dynamic_events import DynamicEventDefinition, EventPredicate
from dnd_rpg_engine.living.economy import EconomySystem
from dnd_rpg_engine.living.world import LivingWorld


def test_economy_price_moves_with_supply_and_demand() -> None:
    economy = EconomySystem()
    economy.register_item("restorative", 100)
    baseline = economy.price("restorative")
    economy.transact("restorative", 10, buying_from_market=True)
    assert economy.price("restorative") > baseline


def test_dynamic_world_event_fires_once() -> None:
    world = LivingWorld(DeterministicDice(1))
    state = CampaignState(seed=1)
    world.dynamic_events.register(
        DynamicEventDefinition(
            id="sunset",
            event_type="world.sunset",
            predicates=[EventPredicate(kind="world_minute", operator="gte", value=10)],
        )
    )
    state.world_minutes = 11
    first = world.dynamic_events.evaluate(state)
    second = world.dynamic_events.evaluate(state)
    assert [event.id for event in first] == ["sunset"]
    assert second == []
