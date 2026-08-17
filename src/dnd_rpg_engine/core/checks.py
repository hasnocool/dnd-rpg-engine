# src/dnd_rpg_engine/core/checks.py
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import Entity


class RollMode(StrEnum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


class CheckResult(BaseModel):
    ability: str
    dc: int
    raw_rolls: list[int]
    selected_roll: int
    modifier: int
    total: int
    success: bool
    critical_success: bool = False
    critical_failure: bool = False


class CheckService:
    def __init__(self, dice: DeterministicDice) -> None:
        self.dice = dice

    def ability_check(
        self,
        actor: Entity,
        ability: str,
        dc: int,
        *,
        mode: RollMode = RollMode.NORMAL,
        proficiency: int = 0,
        stream: str | None = None,
    ) -> CheckResult:
        rolls = [self.dice.d20(stream=stream or f"check:{actor.id}:{ability}")]
        if mode is not RollMode.NORMAL:
            rolls.append(self.dice.d20(stream=stream or f"check:{actor.id}:{ability}"))
        selected = min(rolls) if mode is RollMode.DISADVANTAGE else max(rolls)
        modifier = actor.stats.modifier(ability) + proficiency
        total = selected + modifier
        return CheckResult(
            ability=ability,
            dc=dc,
            raw_rolls=rolls,
            selected_roll=selected,
            modifier=modifier,
            total=total,
            success=total >= dc,
            critical_success=selected == 20,
            critical_failure=selected == 1,
        )
