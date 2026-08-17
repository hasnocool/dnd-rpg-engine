# src/dnd_rpg_engine/rules/runtime.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.rules.effects import EffectPipeline, EffectTrigger, Modifier, ModifierKind
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.conditions import ActiveCondition, ConditionRegistry


class RuleCapability(StrEnum):
    CHECKS = "checks"
    ATTACKS = "attacks"
    DAMAGE = "damage"
    EFFECTS = "effects"
    REACTIONS = "reactions"
    ACTION_ECONOMY = "action_economy"
    DEATH_SAVES = "death_saves"
    CONCENTRATION = "concentration"
    SPELL_SLOTS = "spell_slots"
    RESTS = "rests"


class ResolutionContext(BaseModel):
    actor_id: str
    target_id: str | None = None
    action_id: str | None = None
    tags: set[str] = Field(default_factory=set)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModifierTrace(BaseModel):
    base: float
    flat_total: float = 0.0
    multiplier: float = 1.0
    minimum: float | None = None
    maximum: float | None = None
    advantage_sources: list[str] = Field(default_factory=list)
    disadvantage_sources: list[str] = Field(default_factory=list)
    applied: list[Modifier] = Field(default_factory=list)
    final: float


class RollRequest(BaseModel):
    expression: str = "1d20"
    stream: str = "rules"
    base_modifier: int = 0
    target: int | None = None
    context: ResolutionContext


class RollOutcome(BaseModel):
    raw_rolls: list[int]
    selected_roll: int
    modifier: int
    total: int
    success: bool | None = None
    mode: str = "normal"
    trace: ModifierTrace


class DamagePacket(BaseModel):
    amount: int = Field(ge=0)
    damage_type: str = "physical"
    source_id: str | None = None
    tags: set[str] = Field(default_factory=set)


class DamageOutcome(BaseModel):
    incoming: int
    damage_type: str
    after_traits: int
    multiplier: float = 1.0
    immune: bool = False
    resistant: bool = False
    vulnerable: bool = False
    trace: list[str] = Field(default_factory=list)


class AttackOutcome(BaseModel):
    roll: int
    raw_rolls: list[int]
    modifier: int
    total: int
    defense: int
    hit: bool
    damage: int
    critical: bool
    roll_mode: str = "normal"
    attack_trace: ModifierTrace
    damage_trace: list[str] = Field(default_factory=list)


class ReactionOpportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    actor_id: str
    trigger: str
    source_id: str | None = None
    target_id: str | None = None
    opened_at: float = 0.0
    expires_at: float | None = None
    options: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    choice: str | None = None


class ActionEconomy(BaseModel):
    actions: int = Field(default=1, ge=0)
    bonus_actions: int = Field(default=1, ge=0)
    reactions: int = Field(default=1, ge=0)
    movement: float = Field(default=0.0, ge=0)
    spent_actions: int = Field(default=0, ge=0)
    spent_bonus_actions: int = Field(default=0, ge=0)
    spent_reactions: int = Field(default=0, ge=0)
    spent_movement: float = Field(default=0.0, ge=0)

    def reset(self, *, movement: float | None = None) -> None:
        self.spent_actions = 0
        self.spent_bonus_actions = 0
        self.spent_reactions = 0
        self.spent_movement = 0.0
        if movement is not None:
            self.movement = max(0.0, movement)

    def consume(self, kind: str, amount: float = 1.0) -> None:
        if amount < 0:
            raise ValueError("action-economy consumption cannot be negative")
        if kind == "action":
            value = int(amount)
            if self.spent_actions + value > self.actions:
                raise ValueError("no action available")
            self.spent_actions += value
            return
        if kind == "bonus_action":
            value = int(amount)
            if self.spent_bonus_actions + value > self.bonus_actions:
                raise ValueError("no bonus action available")
            self.spent_bonus_actions += value
            return
        if kind == "reaction":
            value = int(amount)
            if self.spent_reactions + value > self.reactions:
                raise ValueError("no reaction available")
            self.spent_reactions += value
            return
        if kind == "movement":
            if self.spent_movement + amount > self.movement + 1e-9:
                raise ValueError("insufficient movement available")
            self.spent_movement += amount
            return
        raise ValueError(f"unknown action-economy resource: {kind}")


@dataclass(slots=True)
class RuntimeRegistration:
    ruleset_id: str
    factory: Callable[[RuleSet, DeterministicDice, ConditionRegistry], "RulesRuntime"]


_RUNTIME_FACTORIES: dict[str, RuntimeRegistration] = {}


def register_runtime(
    ruleset_id: str,
    factory: Callable[[RuleSet, DeterministicDice, ConditionRegistry], "RulesRuntime"],
) -> None:
    _RUNTIME_FACTORIES[ruleset_id] = RuntimeRegistration(ruleset_id=ruleset_id, factory=factory)


def create_runtime(rules: RuleSet, dice: DeterministicDice, conditions: ConditionRegistry) -> "RulesRuntime":
    registration = _RUNTIME_FACTORIES.get(rules.id)
    if registration is not None:
        return registration.factory(rules, dice, conditions)
    return RulesRuntime(rules, dice, conditions)


class RulesRuntime:
    """Typed deterministic rules boundary for authoritative systems."""

    capabilities: frozenset[RuleCapability] = frozenset(
        {
            RuleCapability.CHECKS,
            RuleCapability.ATTACKS,
            RuleCapability.DAMAGE,
            RuleCapability.EFFECTS,
            RuleCapability.REACTIONS,
            RuleCapability.ACTION_ECONOMY,
        }
    )

    def __init__(self, rules: RuleSet, dice: DeterministicDice, conditions: ConditionRegistry) -> None:
        self.rules = rules
        self.dice = dice
        self.conditions = conditions
        self.effects = EffectPipeline()
        self.reactions: dict[str, ReactionOpportunity] = {}
        self.action_economy: dict[str, ActionEconomy] = {}

    def has_capability(self, capability: RuleCapability) -> bool:
        return capability in self.capabilities

    def economy_for(self, actor_id: str) -> ActionEconomy:
        return self.action_economy.setdefault(actor_id, ActionEconomy())

    def reset_turn(self, actor: Entity) -> ActionEconomy:
        movement = float(actor.component("movement").get("speed", actor.component("movement").get("units_per_round", 0.0)))
        economy = self.economy_for(actor.id)
        economy.reset(movement=movement)
        return economy

    def open_reaction(
        self,
        actor_id: str,
        trigger: str,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        now: float = 0.0,
        timeout: float | None = None,
        options: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReactionOpportunity:
        opportunity = ReactionOpportunity(
            actor_id=actor_id,
            trigger=trigger,
            source_id=source_id,
            target_id=target_id,
            opened_at=now,
            expires_at=(now + timeout) if timeout is not None else None,
            options=list(options or []),
            metadata=dict(metadata or {}),
        )
        self.reactions[opportunity.id] = opportunity
        return opportunity

    def resolve_reaction(self, opportunity_id: str, choice: str | None, *, now: float | None = None) -> ReactionOpportunity:
        opportunity = self.reactions[opportunity_id]
        if opportunity.resolved:
            return opportunity
        if now is not None and opportunity.expires_at is not None and now > opportunity.expires_at:
            choice = None
        if choice is not None and opportunity.options and choice not in opportunity.options:
            raise ValueError("reaction choice is not available")
        if choice is not None:
            self.economy_for(opportunity.actor_id).consume("reaction")
        opportunity.choice = choice
        opportunity.resolved = True
        return opportunity

    def expire_reactions(self, now: float) -> list[ReactionOpportunity]:
        expired: list[ReactionOpportunity] = []
        for opportunity in self.reactions.values():
            if opportunity.resolved or opportunity.expires_at is None or opportunity.expires_at > now:
                continue
            opportunity.resolved = True
            opportunity.choice = None
            expired.append(opportunity)
        return sorted(expired, key=lambda value: (value.expires_at or 0.0, value.id))

    def _condition_roll_modifiers(
        self,
        attacker_conditions: list[ActiveCondition],
        target_conditions: list[ActiveCondition],
    ) -> list[Modifier]:
        results: list[Modifier] = []
        for active in attacker_conditions:
            definition = self.conditions.get(active.condition_id)
            if definition is None:
                continue
            for index in range(active.stacks):
                if definition.attack_modifier:
                    results.append(
                        Modifier(
                            id=f"condition:{active.condition_id}:attack:{index}",
                            source_id=active.condition_id,
                            target="attack_roll",
                            kind=ModifierKind.FLAT,
                            value=definition.attack_modifier,
                        )
                    )
                if definition.attack_roll_mode == "advantage":
                    results.append(
                        Modifier(
                            id=f"condition:{active.condition_id}:advantage:{index}",
                            source_id=active.condition_id,
                            target="attack_roll",
                            kind=ModifierKind.ADVANTAGE,
                        )
                    )
                elif definition.attack_roll_mode == "disadvantage":
                    results.append(
                        Modifier(
                            id=f"condition:{active.condition_id}:disadvantage:{index}",
                            source_id=active.condition_id,
                            target="attack_roll",
                            kind=ModifierKind.DISADVANTAGE,
                        )
                    )
        for active in target_conditions:
            definition = self.conditions.get(active.condition_id)
            if definition is None:
                continue
            mode = definition.attacks_against_mode
            if mode == "normal":
                continue
            kind = ModifierKind.ADVANTAGE if mode == "advantage" else ModifierKind.DISADVANTAGE
            for index in range(active.stacks):
                results.append(
                    Modifier(
                        id=f"condition:{active.condition_id}:against:{index}",
                        source_id=active.condition_id,
                        target="attack_roll",
                        kind=kind,
                    )
                )
        return results

    @staticmethod
    def _resolve_modifier_trace(base: float, modifiers: list[Modifier]) -> ModifierTrace:
        flat_total = 0.0
        multiplier = 1.0
        minimum: float | None = None
        maximum: float | None = None
        advantages: list[str] = []
        disadvantages: list[str] = []
        applied = sorted(modifiers, key=lambda value: (value.priority, value.id))
        for modifier in applied:
            if modifier.kind is ModifierKind.FLAT:
                flat_total += modifier.value
            elif modifier.kind is ModifierKind.MULTIPLIER:
                multiplier *= modifier.value
            elif modifier.kind is ModifierKind.MINIMUM:
                minimum = modifier.value if minimum is None else max(minimum, modifier.value)
            elif modifier.kind is ModifierKind.MAXIMUM:
                maximum = modifier.value if maximum is None else min(maximum, modifier.value)
            elif modifier.kind is ModifierKind.ADVANTAGE:
                advantages.append(modifier.source_id or modifier.id)
            elif modifier.kind is ModifierKind.DISADVANTAGE:
                disadvantages.append(modifier.source_id or modifier.id)
        final = (base + flat_total) * multiplier
        if minimum is not None:
            final = max(minimum, final)
        if maximum is not None:
            final = min(maximum, final)
        return ModifierTrace(
            base=base,
            flat_total=flat_total,
            multiplier=multiplier,
            minimum=minimum,
            maximum=maximum,
            advantage_sources=advantages,
            disadvantage_sources=disadvantages,
            applied=applied,
            final=final,
        )

    def resolve_roll(self, request: RollRequest, modifiers: list[Modifier] | None = None) -> RollOutcome:
        relevant = [
            modifier
            for modifier in modifiers or []
            if modifier.target in {"roll", "attack_roll", "check_roll", "save_roll"}
        ]
        relevant.extend(
            self.effects.modifiers_for(
                request.context.actor_id,
                EffectTrigger.BEFORE_ROLL,
                target="roll",
                tags=request.context.tags,
            )
        )
        trace = self._resolve_modifier_trace(request.base_modifier, relevant)
        has_advantage = bool(trace.advantage_sources)
        has_disadvantage = bool(trace.disadvantage_sources)
        mode = "normal"
        if has_advantage != has_disadvantage:
            mode = "advantage" if has_advantage else "disadvantage"
        first = self.dice.roll(request.expression, stream=request.stream).total
        raw_rolls = [first]
        if mode != "normal":
            raw_rolls.append(self.dice.roll(request.expression, stream=request.stream).total)
        selected = max(raw_rolls) if mode == "advantage" else min(raw_rolls) if mode == "disadvantage" else raw_rolls[0]
        modifier = int(trace.final)
        total = selected + modifier
        success = None if request.target is None else total >= request.target
        return RollOutcome(
            raw_rolls=raw_rolls,
            selected_roll=selected,
            modifier=modifier,
            total=total,
            success=success,
            mode=mode,
            trace=trace,
        )

    def action_proficiency_bonus(self, attacker: Entity, action: ActionDefinition) -> int:
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
        modifiers: list[Modifier] = []
        for active in active_conditions or []:
            definition = self.conditions.get(active.condition_id)
            if definition is None or not definition.armor_modifier:
                continue
            for index in range(active.stacks):
                modifiers.append(
                    Modifier(
                        id=f"condition:{active.condition_id}:defense:{index}",
                        source_id=active.condition_id,
                        target="defense",
                        kind=ModifierKind.FLAT,
                        value=definition.armor_modifier,
                    )
                )
        modifiers.extend(self.effects.modifiers_for(target.id, EffectTrigger.BEFORE_ROLL, target="defense"))
        return int(self._resolve_modifier_trace(base, modifiers).final)

    def resolve_damage(self, target: Entity, packet: DamagePacket) -> DamageOutcome:
        defenses = target.component("defenses")
        normalized = packet.damage_type.casefold()
        immunities = {str(value).casefold() for value in defenses.get("immunities", [])}
        resistances = {str(value).casefold() for value in defenses.get("resistances", [])}
        vulnerabilities = {str(value).casefold() for value in defenses.get("vulnerabilities", [])}
        immune = normalized in immunities
        resistant = normalized in resistances
        vulnerable = normalized in vulnerabilities
        trace: list[str] = []
        amount = packet.amount
        multiplier = 1.0
        if immune:
            amount = 0
            multiplier = 0.0
            trace.append(f"immune:{normalized}")
        else:
            if resistant:
                multiplier *= 0.5
                trace.append(f"resistant:{normalized}")
            if vulnerable:
                multiplier *= 2.0
                trace.append(f"vulnerable:{normalized}")
            damage_modifiers = self.effects.modifiers_for(
                target.id,
                EffectTrigger.BEFORE_DAMAGE,
                target="damage",
                tags={normalized, *packet.tags},
            )
            modifier_trace = self._resolve_modifier_trace(float(amount), damage_modifiers)
            amount = max(0, int(modifier_trace.final * multiplier))
            trace.extend(f"effect:{modifier.id}" for modifier in modifier_trace.applied)
        return DamageOutcome(
            incoming=packet.amount,
            damage_type=packet.damage_type,
            after_traits=amount,
            multiplier=multiplier,
            immune=immune,
            resistant=resistant,
            vulnerable=vulnerable,
            trace=trace,
        )

    def resolve_attack(
        self,
        attacker: Entity,
        target: Entity,
        action: ActionDefinition,
        *,
        active_conditions: list[ActiveCondition] | None = None,
        target_conditions: list[ActiveCondition] | None = None,
    ) -> AttackOutcome:
        attacker_conditions = list(active_conditions or [])
        defender_conditions = list(target_conditions or [])
        modifiers = self._condition_roll_modifiers(attacker_conditions, defender_conditions)
        defense = self.defense(target, defender_conditions)
        context = ResolutionContext(
            actor_id=attacker.id,
            target_id=target.id,
            action_id=action.id,
            tags=set(action.tags) | {"attack"},
        )
        roll = self.resolve_roll(
            RollRequest(
                expression="1d20",
                stream=f"combat:attack:{attacker.id}",
                base_modifier=attacker.stats.modifier(action.attack_ability) + self.action_proficiency_bonus(attacker, action),
                target=defense,
                context=context,
            ),
            modifiers,
        )
        critical_success = roll.selected_roll >= self.rules.critical_success_roll
        critical_failure = roll.selected_roll == self.rules.critical_failure_roll
        hit = critical_success or (not critical_failure and bool(roll.success))
        critical = critical_success and hit
        damage = 0
        damage_trace: list[str] = []
        if hit:
            result = self.dice.roll(action.damage, stream=f"combat:damage:{attacker.id}:{action.id}")
            damage = max(self.rules.minimum_damage, result.total + attacker.stats.modifier(action.attack_ability))
            damage_trace.append(f"base:{result.total}")
            if critical:
                extra = self.dice.roll(action.damage, stream=f"combat:critical:{attacker.id}:{action.id}")
                damage += max(0, extra.total)
                damage_trace.append(f"critical:{extra.total}")
        return AttackOutcome(
            roll=roll.selected_roll,
            raw_rolls=roll.raw_rolls,
            modifier=roll.modifier,
            total=roll.total,
            defense=defense,
            hit=hit,
            damage=damage,
            critical=critical,
            roll_mode=roll.mode,
            attack_trace=roll.trace,
            damage_trace=damage_trace,
        )
