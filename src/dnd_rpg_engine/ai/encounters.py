# src/dnd_rpg_engine/ai/encounters.py
from __future__ import annotations

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.dice import DeterministicDice


class EncounterTemplate(BaseModel):
    id: str
    tags: set[str] = Field(default_factory=set)
    opponent_templates: list[str]
    min_tier: int = Field(default=1, ge=1)
    max_tier: int = Field(default=20, ge=1)
    weight: int = Field(default=1, ge=1)


class GeneratedEncounter(BaseModel):
    template_id: str
    opponents: list[str]
    difficulty_tier: int


class EncounterGenerator:
    def __init__(self, dice: DeterministicDice) -> None:
        self.dice = dice
        self.templates: dict[str, EncounterTemplate] = {}

    def register(self, template: EncounterTemplate) -> None:
        self.templates[template.id] = template

    def generate(self, tier: int, *, tags: set[str] | None = None) -> GeneratedEncounter:
        candidates = [
            template
            for template in self.templates.values()
            if template.min_tier <= tier <= template.max_tier and (not tags or template.tags & tags)
        ]
        if not candidates:
            raise ValueError("no encounter template matches the requested tier/tags")
        weighted = [template for template in candidates for _ in range(template.weight)]
        index = self.dice.roll(f"1d{len(weighted)}", stream="gm:encounter").total - 1
        selected = weighted[index]
        return GeneratedEncounter(
            template_id=selected.id,
            opponents=list(selected.opponent_templates),
            difficulty_tier=tier,
        )
