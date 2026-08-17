# src/dnd_rpg_engine/tactical/combat.py
from __future__ import annotations

from dataclasses import dataclass, field

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.conditions import ActiveCondition, ConditionRegistry


@dataclass(slots=True)
class CombatantState:
    entity_id: str
    next_ready_at: float = 0.0
    conditions: list[ActiveCondition] = field(default_factory=list)


@dataclass(slots=True)
class Encounter:
    id: str
    participants: dict[str, CombatantState]
    active: bool = True
    started_at: float = 0.0
    round_length: float = 6.0


@dataclass(frozen=True, slots=True)
class AttackResolution:
    roll: int
    modifier: int
    total: int
    defense: int
    hit: bool
    damage: int
    critical: bool


class CombatSystem:
    def __init__(self, dice: DeterministicDice, conditions: ConditionRegistry, rules: RuleSet | None = None) -> None:
        self.dice = dice
        self.conditions = conditions
        self.rules = rules or RuleSet()
        self.encounters: dict[str, Encounter] = {}

    def defense(self, target: Entity, active_conditions: list[ActiveCondition] | None = None) -> int:
        base = self.rules.base_defense + target.stats.modifier("dexterity")
        for active in active_conditions or []:
            base += self.conditions.require(active.condition_id).armor_modifier * active.stacks
        return base

    def resolve_attack(
        self,
        attacker: Entity,
        target: Entity,
        action: ActionDefinition,
        *,
        active_conditions: list[ActiveCondition] | None = None,
    ) -> AttackResolution:
        raw = self.dice.d20(stream=f"combat:attack:{attacker.id}")
        modifier = attacker.stats.modifier(action.attack_ability)
        for active in active_conditions or []:
            modifier += self.conditions.require(active.condition_id).attack_modifier * active.stacks
        total = raw + modifier
        defense = self.defense(target)
        hit = raw >= self.rules.critical_success_roll or (raw != self.rules.critical_failure_roll and total >= defense)
        critical = raw >= self.rules.critical_success_roll and hit
        damage = 0
        if hit:
            result = self.dice.roll(action.damage, stream=f"combat:damage:{attacker.id}:{action.id}")
            damage = max(self.rules.minimum_damage, result.total + attacker.stats.modifier(action.attack_ability))
            if critical:
                extra = self.dice.roll(action.damage, stream=f"combat:critical:{attacker.id}:{action.id}")
                damage += max(0, extra.total)
        return AttackResolution(raw, modifier, total, defense, hit, damage, critical)
