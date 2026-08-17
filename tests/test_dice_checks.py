# tests/test_dice_checks.py
from dnd_rpg_engine.core.checks import CheckService, RollMode
from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import Entity, Stats


def test_dice_is_deterministic_per_seed_and_stream() -> None:
    a = DeterministicDice(99)
    b = DeterministicDice(99)
    assert [a.roll("2d6+3", stream="x").total for _ in range(5)] == [
        b.roll("2d6+3", stream="x").total for _ in range(5)
    ]


def test_check_advantage_selects_highest_roll() -> None:
    actor = Entity(name="Scout", stats=Stats(dexterity=16))
    service = CheckService(DeterministicDice(12))
    result = service.ability_check(actor, "dexterity", 10, mode=RollMode.ADVANTAGE)
    assert len(result.raw_rolls) == 2
    assert result.selected_roll == max(result.raw_rolls)
    assert result.modifier == 3
