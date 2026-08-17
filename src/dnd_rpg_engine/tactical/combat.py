# src/dnd_rpg_engine/tactical/combat.py
from __future__ import annotations

from dataclasses import dataclass, field

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.rules.runtime import DamagePacket, RulesRuntime, create_runtime
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
    raw_rolls: tuple[int, ...]
    modifier: int
    total: int
    defense: int
    hit: bool
    damage: int
    critical: bool
    roll_mode: str = "normal"
    attack_trace: dict | None = None
    damage_trace: tuple[str, ...] = ()


class CombatSystem:
    """Compatibility facade over the active typed RulesRuntime.

    Engine callers keep using CombatSystem while concrete rules interpretation
    lives behind the runtime boundary. Assigning ``combat.rules`` hot-swaps the
    runtime using the registered ruleset factory.
    """

    def __init__(self, dice: DeterministicDice, conditions: ConditionRegistry, rules: RuleSet | None = None) -> None:
        self.dice = dice
        self.conditions = conditions
        self._rules = rules or RuleSet()
        self.runtime: RulesRuntime = create_runtime(self._rules, self.dice, self.conditions)
        self.encounters: dict[str, Encounter] = {}

    @property
    def rules(self) -> RuleSet:
        return self._rules

    @rules.setter
    def rules(self, value: RuleSet) -> None:
        previous_effects = getattr(self.runtime, "effects", None) if hasattr(self, "runtime") else None
        previous_economy = getattr(self.runtime, "action_economy", {}) if hasattr(self, "runtime") else {}
        previous_reactions = getattr(self.runtime, "reactions", {}) if hasattr(self, "runtime") else {}
        self._rules = value
        self.runtime = create_runtime(value, self.dice, self.conditions)
        if previous_effects is not None:
            self.runtime.effects = previous_effects
        self.runtime.action_economy.update(previous_economy)
        self.runtime.reactions.update(previous_reactions)

    @property
    def effects(self):
        return self.runtime.effects

    @property
    def reactions(self):
        return self.runtime.reactions

    @property
    def action_economy(self):
        return self.runtime.action_economy

    def defense(self, target: Entity, active_conditions: list[ActiveCondition] | None = None) -> int:
        return self.runtime.defense(target, active_conditions)

    def resolve_attack(
        self,
        attacker: Entity,
        target: Entity,
        action: ActionDefinition,
        *,
        active_conditions: list[ActiveCondition] | None = None,
        target_conditions: list[ActiveCondition] | None = None,
    ) -> AttackResolution:
        outcome = self.runtime.resolve_attack(
            attacker,
            target,
            action,
            active_conditions=active_conditions,
            target_conditions=target_conditions,
        )
        return AttackResolution(
            roll=outcome.roll,
            raw_rolls=tuple(outcome.raw_rolls),
            modifier=outcome.modifier,
            total=outcome.total,
            defense=outcome.defense,
            hit=outcome.hit,
            damage=outcome.damage,
            critical=outcome.critical,
            roll_mode=outcome.roll_mode,
            attack_trace=outcome.attack_trace.model_dump(mode="json"),
            damage_trace=tuple(outcome.damage_trace),
        )

    def apply_damage_traits(self, target: Entity, amount: int, damage_type: str) -> int:
        outcome = self.runtime.resolve_damage(
            target,
            DamagePacket(amount=max(0, amount), damage_type=damage_type),
        )
        return outcome.after_traits
