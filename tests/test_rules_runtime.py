# tests/test_rules_runtime.py
from __future__ import annotations

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import Entity, ResourcePool, Stats
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.rules.effects import EffectDefinition, EffectTrigger, Modifier, ModifierKind
from dnd_rpg_engine.rules.runtime import DamagePacket, ResolutionContext, RollRequest, RuleCapability, RulesRuntime
from dnd_rpg_engine.rulesets.srd_5_2_1 import SRD521RulesRuntime, SRD_5_2_1_RULESET
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.combat import CombatSystem
from dnd_rpg_engine.tactical.conditions import ActiveCondition, ConditionDefinition, ConditionRegistry


def make_conditions() -> ConditionRegistry:
    registry = ConditionRegistry()
    registry.register(ConditionDefinition(id="blinded", name="Blinded", attack_roll_mode="disadvantage"))
    registry.register(ConditionDefinition(id="invisible", name="Invisible", attack_roll_mode="advantage"))
    return registry


def test_runtime_modifier_trace_and_advantage_cancel() -> None:
    runtime = RulesRuntime(RuleSet(), DeterministicDice(11), make_conditions())
    actor = Entity(id="actor", name="Actor", stats=Stats(strength=14))
    target = Entity(id="target", name="Target")
    action = ActionDefinition(id="strike", name="Strike", damage="1d4")
    outcome = runtime.resolve_attack(
        actor,
        target,
        action,
        active_conditions=[ActiveCondition(condition_id="blinded"), ActiveCondition(condition_id="invisible")],
    )
    assert outcome.roll_mode == "normal"
    assert len(outcome.raw_rolls) == 1
    assert outcome.attack_trace.advantage_sources == ["invisible"]
    assert outcome.attack_trace.disadvantage_sources == ["blinded"]


def test_effect_pipeline_changes_roll_and_damage() -> None:
    runtime = RulesRuntime(RuleSet(), DeterministicDice(3), make_conditions())
    runtime.effects.register(
        EffectDefinition(
            id="blessing",
            name="Blessing",
            triggers={EffectTrigger.BEFORE_ROLL},
            modifiers=[Modifier(id="blessing-roll", target="roll", kind=ModifierKind.FLAT, value=2)],
        )
    )
    runtime.effects.register(
        EffectDefinition(
            id="ward",
            name="Ward",
            triggers={EffectTrigger.BEFORE_DAMAGE},
            modifiers=[Modifier(id="ward-damage", target="damage", kind=ModifierKind.MULTIPLIER, value=0.5)],
        )
    )
    runtime.effects.apply("blessing", "hero")
    runtime.effects.apply("ward", "hero")
    roll = runtime.resolve_roll(
        RollRequest(
            context=ResolutionContext(actor_id="hero"),
            base_modifier=3,
            target=10,
            stream="test:effect",
        )
    )
    assert roll.modifier == 5
    hero = Entity(id="hero", name="Hero", resources=ResourcePool(hp=20, max_hp=20))
    damage = runtime.resolve_damage(hero, DamagePacket(amount=10, damage_type="fire"))
    assert damage.after_traits == 5
    assert "effect:ward-damage" in damage.trace


def test_reactions_consume_action_economy() -> None:
    runtime = RulesRuntime(RuleSet(), DeterministicDice(5), make_conditions())
    opportunity = runtime.open_reaction("hero", "enemy_left_reach", now=4, timeout=3, options=["attack", "ignore"])
    resolved = runtime.resolve_reaction(opportunity.id, "attack", now=5)
    assert resolved.choice == "attack"
    assert runtime.economy_for("hero").spent_reactions == 1


def test_srd_rules_hot_swap_to_srd_runtime() -> None:
    combat = CombatSystem(DeterministicDice(9), make_conditions())
    combat.rules = SRD_5_2_1_RULESET
    assert isinstance(combat.runtime, SRD521RulesRuntime)
    assert combat.runtime.has_capability(RuleCapability.DEATH_SAVES)
