# src/dnd_rpg_engine/core/rules.py
from __future__ import annotations

from pydantic import BaseModel, Field


class RuleSet(BaseModel):
    """Safe, data-driven rule knobs used by the authoritative simulation.

    Creator-authored rule documents may change these validated values without
    executing arbitrary code. More complex rules can be implemented as normal
    Python plugins around the same command/event interfaces.
    """

    id: str = "core.default"
    name: str = "Core Default"
    base_defense: int = Field(default=10, ge=0, le=100)
    critical_success_roll: int = Field(default=20, ge=2, le=100)
    critical_failure_roll: int = Field(default=1, ge=1, le=99)
    round_seconds: float = Field(default=6.0, gt=0, le=3600)
    minimum_damage: int = Field(default=0, ge=0, le=1000)
    diagonal_movement_multiplier: float = Field(default=1.41421356237, ge=1.0, le=3.0)
    spell_save_base: int = Field(default=8, ge=0, le=100)
    death_saves_enabled: bool = False
    death_save_dc: int = Field(default=10, ge=1, le=100)
    death_save_successes_required: int = Field(default=3, ge=1, le=10)
    death_save_failures_required: int = Field(default=3, ge=1, le=10)
