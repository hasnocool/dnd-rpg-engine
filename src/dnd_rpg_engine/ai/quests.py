# src/dnd_rpg_engine/ai/quests.py
from __future__ import annotations

from dnd_rpg_engine.adventure.quests import ObjectiveType, QuestDefinition, QuestObjective
from dnd_rpg_engine.core.dice import DeterministicDice


class QuestGenerator:
    def __init__(self, dice: DeterministicDice) -> None:
        self.dice = dice

    def generate_visit_quest(self, location_ids: list[str], *, reward: int = 25) -> QuestDefinition:
        if not location_ids:
            raise ValueError("at least one location is required")
        idx = self.dice.roll(f"1d{len(location_ids)}", stream="gm:quest").total - 1
        target = location_ids[idx]
        return QuestDefinition(
            id=f"generated_visit_{target}_{self.dice.counters.get('gm:quest', 0)}",
            name=f"Journey to {target.replace('_', ' ').title()}",
            description=f"Travel to {target.replace('_', ' ')} and report what you find.",
            objectives=[QuestObjective(id="visit", type=ObjectiveType.VISIT, target_id=target)],
            reward_currency=reward,
        )
