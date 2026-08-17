# src/dnd_rpg_engine/rules/__init__.py
"""Typed rules runtime, effect pipeline, reactions, and action economy."""

from dnd_rpg_engine.rules.effects import (
    EffectDefinition,
    EffectInstance,
    EffectOperation,
    EffectPipeline,
    EffectTrigger,
    Modifier,
    ModifierKind,
)
from dnd_rpg_engine.rules.runtime import (
    ActionEconomy,
    AttackOutcome,
    DamageOutcome,
    DamagePacket,
    ReactionOpportunity,
    ResolutionContext,
    RollOutcome,
    RollRequest,
    RuleCapability,
    RulesRuntime,
    create_runtime,
    register_runtime,
)

__all__ = [
    "ActionEconomy",
    "AttackOutcome",
    "DamageOutcome",
    "DamagePacket",
    "EffectDefinition",
    "EffectInstance",
    "EffectOperation",
    "EffectPipeline",
    "EffectTrigger",
    "Modifier",
    "ModifierKind",
    "ReactionOpportunity",
    "ResolutionContext",
    "RollOutcome",
    "RollRequest",
    "RuleCapability",
    "RulesRuntime",
    "create_runtime",
    "register_runtime",
]
