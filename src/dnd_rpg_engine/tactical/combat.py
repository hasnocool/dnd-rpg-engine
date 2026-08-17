# src/dnd_rpg_engine/tactical/combat.py
from __future__ import annotations

from dataclasses import dataclass, field

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.conditions import ActiveCondition, ConditionRegistry, RollEffect


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


class CombatSystem:
    def __init__(self, dice: DeterministicDice, conditions: ConditionRegistry, rules: RuleSet | None = None) -> None:
        self.dice = dice
        self.conditions = conditions
        self.rules = rules or RuleSet()
        self.encounters: dict[str, Encounter] = {}

    def defense(self, target: Entity, active_conditions: list[ActiveCondition] | None = None) -> int:
        armor = target.component("armor")
        dexterity_modifier = target.stats.modifier("dexterity")
        if armor.get("fixed_ac") is not None:
            base = int(armor["fixed_ac"])
        else:
            base_ac = int(armor.get("base_ac", self.rules.base_defense))
            dex_cap = armor.get("dex_cap")
            dex_bonus = dexterity_modifier if bool(armor.get("add_dexterity", True)) else 0
            if dex_cap is not None:
                dex_bonus = min(dex_bonus, int(dex_cap))
            base = base_ac + dex_bonus
        base += int(armor.get("shield_bonus", 0)) + int(armor.get("bonus", 0))
        for active in active_conditions or []:
            definition = self.conditions.get(active.condition_id)
            if definition is not None:
                base += definition.armor_modifier * active.stacks
        return base

    def resolve_attack(
        self,
        attacker: Entity,
        target: Entity,
        action: ActionDefinition,
        *,
        active_conditions: list[ActiveCondition] | None = None,
        target_conditions: list[ActiveCondition] | None = None,
    ) -> AttackResolution:
        roll_mode = self._attack_roll_mode(active_conditions or [], target_conditions or [])
        raw_rolls = self._roll_d20(attacker.id, roll_mode)
        raw = self._select_roll(raw_rolls, roll_mode)
        modifier = attacker.stats.modifier(action.attack_ability)
        modifier += self._action_proficiency_bonus(attacker, action)
        for active in active_conditions or []:
            definition = self.conditions.get(active.condition_id)
            if definition is not None:
                modifier += definition.attack_modifier * active.stacks
        total = raw + modifier
        defense = self.defense(target, target_conditions)
        hit = raw >= self.rules.critical_success_roll or (raw != self.rules.critical_failure_roll and total >= defense)
        critical = raw >= self.rules.critical_success_roll and hit
        damage = 0
        if hit:
            result = self.dice.roll(action.damage, stream=f"combat:damage:{attacker.id}:{action.id}")
            damage = max(self.rules.minimum_damage, result.total + attacker.stats.modifier(action.attack_ability))
            if critical:
                extra = self.dice.roll(action.damage, stream=f"combat:critical:{attacker.id}:{action.id}")
                damage += max(0, extra.total)
        return AttackResolution(raw, raw_rolls, modifier, total, defense, hit, damage, critical)

    def apply_damage_traits(self, target: Entity, amount: int, damage_type: str) -> int:
        defenses = target.component("defenses")
        normalized = damage_type.lower()
        if normalized in {str(value).lower() for value in defenses.get("immunities", [])}:
            return 0
        if normalized in {str(value).lower() for value in defenses.get("vulnerabilities", [])}:
            return amount * 2
        if normalized in {str(value).lower() for value in defenses.get("resistances", [])}:
            return amount // 2
        return amount

    def _action_proficiency_bonus(self, attacker: Entity, action: ActionDefinition) -> int:
        if not action.proficiency_key:
            return 0
        proficiencies = attacker.component("proficiencies")
        keys = set(proficiencies.get("actions", [])) | set(proficiencies.get("categories", []))
        if action.proficiency_key not in keys:
            return 0
        explicit = proficiencies.get("bonus")
        if explicit is not None:
            return int(explicit)
        level = max(1, int(attacker.component("progression").get("level", 1)))
        return 2 + ((level - 1) // 4)

    def _attack_roll_mode(
        self,
        attacker_conditions: list[ActiveCondition],
        target_conditions: list[ActiveCondition],
    ) -> RollEffect:
        effects: list[RollEffect] = []
        for active in attacker_conditions:
            definition = self.conditions.get(active.condition_id)
            if definition and definition.attack_roll_mode != "normal":
                effects.append(definition.attack_roll_mode)
        for active in target_conditions:
            definition = self.conditions.get(active.condition_id)
            if definition and definition.attacks_against_mode != "normal":
                effects.append(definition.attacks_against_mode)
        has_advantage = "advantage" in effects
        has_disadvantage = "disadvantage" in effects
        if has_advantage == has_disadvantage:
            return "normal"
        return "advantage" if has_advantage else "disadvantage"

    def _roll_d20(self, attacker_id: str, mode: RollEffect) -> tuple[int, ...]:
        first = self.dice.d20(stream=f"combat:attack:{attacker_id}")
        if mode == "normal":
            return (first,)
        second = self.dice.d20(stream=f"combat:attack:{attacker_id}")
        return (first, second)

    @staticmethod
    def _select_roll(rolls: tuple[int, ...], mode: RollEffect) -> int:
        if mode == "advantage":
            return max(rolls)
        if mode == "disadvantage":
            return min(rolls)
        return rolls[0]
