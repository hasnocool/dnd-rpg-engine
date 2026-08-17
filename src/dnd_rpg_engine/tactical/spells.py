# src/dnd_rpg_engine/tactical/spells.py
from __future__ import annotations

from pydantic import BaseModel, Field


class SpellDefinition(BaseModel):
    id: str
    name: str
    level: int = Field(default=0, ge=0, le=9)
    school: str | None = None
    classes: set[str] = Field(default_factory=set)
    cast_time: float = Field(default=6.0, gt=0)
    range: float = Field(default=12.0, ge=0)
    energy_cost: int = Field(default=0, ge=0)
    attack_ability: str = "intelligence"
    save_ability: str | None = None
    damage: str | None = None
    heal: str | None = None
    damage_type: str = "arcane"
    applies_condition: str | None = None
    duration: float | None = Field(default=None, gt=0)
    concentration: bool = False
    ritual: bool = False
    components: tuple[str, ...] = ()
    interruptible: bool = True
    tags: set[str] = Field(default_factory=set)


class SpellRegistry:
    def __init__(self) -> None:
        self._spells: dict[str, SpellDefinition] = {}

    def register(self, spell: SpellDefinition) -> None:
        self._spells[spell.id] = spell

    def require(self, spell_id: str) -> SpellDefinition:
        try:
            return self._spells[spell_id]
        except KeyError as exc:
            raise KeyError(f"unknown spell: {spell_id}") from exc

    def all(self) -> tuple[SpellDefinition, ...]:
        return tuple(self._spells.values())


def default_spells() -> SpellRegistry:
    registry = SpellRegistry()
    registry.register(
        SpellDefinition(
            id="arcane_bolt",
            name="Arcane Bolt",
            cast_time=4.0,
            range=18.0,
            energy_cost=1,
            damage="1d8",
            damage_type="arcane",
        )
    )
    registry.register(
        SpellDefinition(
            id="restoring_light",
            name="Restoring Light",
            cast_time=5.0,
            range=12.0,
            energy_cost=2,
            heal="1d8+2",
        )
    )
    registry.register(
        SpellDefinition(
            id="arcane_snare",
            name="Arcane Snare",
            cast_time=5.0,
            range=12.0,
            energy_cost=2,
            applies_condition="slowed",
            duration=12.0,
        )
    )
    return registry
