# tests/test_srd_toolbox.py
from __future__ import annotations

import pytest

from dnd_rpg_engine.rulesets.srd_5_2_1.toolbox import (
    ENCOUNTER_BUDGETS,
    TERRAIN_TRAVEL_RULES,
    TRAVEL_PACES,
    build_encounter_candidate,
    encounter_budget,
    extended_travel_dc,
    monster_xp,
    special_travel_rate,
)


def test_travel_tables_and_special_rate() -> None:
    assert TRAVEL_PACES["normal"].miles_per_day == 24
    assert TRAVEL_PACES["fast"].feet_per_minute == 400
    assert TERRAIN_TRAVEL_RULES["mountain"].pace == "slow"
    rate = special_travel_rate(30, hours=8, pace="normal")
    assert rate == {"miles_per_hour": 3.0, "miles_per_day": 24.0}
    assert special_travel_rate(30, hours=8, pace="fast")["miles_per_day"] == 32.0
    assert extended_travel_dc(1) == 11
    assert extended_travel_dc(4) == 14


def test_encounter_budget_and_candidate_are_deterministic() -> None:
    assert ENCOUNTER_BUDGETS[1].moderate == 75
    assert encounter_budget([3, 3, 3, 3], "moderate") == 900
    assert monster_xp("1/2") == 100
    candidate = build_encounter_candidate(
        [("moss_guardian", 1), ("cave_sprite", "1/2"), ("river_wisp", "1/4")],
        [2, 2, 2, 2],
        difficulty="moderate",
    )
    assert candidate.total_xp <= candidate.budget
    assert candidate.monster_ids


def test_toolbox_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        encounter_budget([21], "moderate")
    with pytest.raises(ValueError):
        encounter_budget([1], "extreme")
    with pytest.raises(ValueError):
        monster_xp("unknown")
