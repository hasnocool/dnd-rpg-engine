# src/dnd_rpg_engine/rulesets/srd_5_2_1/runtime.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import Entity, EntityKind
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.rules.runtime import RuleCapability, RulesRuntime, register_runtime
from dnd_rpg_engine.rulesets.srd_5_2_1.rules import entity_proficiency_bonus
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.conditions import ConditionRegistry


class ZeroHPTransition(BaseModel):
    state: Literal["defeated", "death_saves_started", "death_save_failure", "stable", "recovered"]
    failures_added: int = 0
    failures: int = 0
    successes: int = 0
    reason: str | None = None


class DeathSaveOutcome(BaseModel):
    roll: int
    state: Literal["pending", "defeated", "stable", "recovered"]
    failures: int = 0
    successes: int = 0
    recovered_hp: int = 0


class SRD521RulesRuntime(RulesRuntime):
    """SRD 5.2.1 mechanics that should not live in the generic engine core."""

    capabilities = RulesRuntime.capabilities | frozenset(
        {
            RuleCapability.DEATH_SAVES,
            RuleCapability.CONCENTRATION,
            RuleCapability.SPELL_SLOTS,
            RuleCapability.RESTS,
        }
    )

    def action_proficiency_bonus(self, attacker: Entity, action: ActionDefinition) -> int:
        if not action.proficiency_key:
            return 0
        proficiencies = attacker.component("proficiencies")
        keys = set(proficiencies.get("actions", [])) | set(proficiencies.get("categories", []))
        return entity_proficiency_bonus(attacker) if action.proficiency_key in keys else 0

    def handle_zero_hp(
        self,
        entity: Entity,
        *,
        critical: bool = False,
        excess_damage: int = 0,
        was_at_zero: bool = False,
    ) -> ZeroHPTransition:
        if entity.kind is not EntityKind.PLAYER:
            entity.alive = False
            return ZeroHPTransition(state="defeated", reason="non_player")
        if excess_damage >= entity.resources.max_hp:
            entity.alive = False
            return ZeroHPTransition(state="defeated", reason="massive_damage")

        death = entity.component("death_saves")
        if not was_at_zero:
            death.update({"successes": 0, "failures": 0, "stable": False})
            return ZeroHPTransition(state="death_saves_started")

        if bool(death.get("stable")):
            death["stable"] = False
        failures_added = 2 if critical else 1
        death["failures"] = int(death.get("failures", 0)) + failures_added
        death["successes"] = int(death.get("successes", 0))
        if death["failures"] >= self.rules.death_save_failures_required:
            entity.alive = False
            return ZeroHPTransition(
                state="defeated",
                failures_added=failures_added,
                failures=int(death["failures"]),
                successes=int(death["successes"]),
            )
        return ZeroHPTransition(
            state="death_save_failure",
            failures_added=failures_added,
            failures=int(death["failures"]),
            successes=int(death["successes"]),
        )

    def resolve_death_save(self, entity: Entity) -> DeathSaveOutcome:
        death = entity.component("death_saves")
        if entity.resources.hp > 0:
            return DeathSaveOutcome(roll=0, state="recovered", recovered_hp=entity.resources.hp)
        if bool(death.get("stable")):
            return DeathSaveOutcome(roll=0, state="stable")

        roll = self.dice.d20(stream=f"death_save:{entity.id}")
        if roll == 20:
            entity.resources.hp = 1
            death.update({"successes": 0, "failures": 0, "stable": False})
            return DeathSaveOutcome(roll=roll, state="recovered", recovered_hp=1)
        if roll == 1:
            death["failures"] = int(death.get("failures", 0)) + 2
        elif roll >= self.rules.death_save_dc:
            death["successes"] = int(death.get("successes", 0)) + 1
        else:
            death["failures"] = int(death.get("failures", 0)) + 1

        failures = int(death.get("failures", 0))
        successes = int(death.get("successes", 0))
        if failures >= self.rules.death_save_failures_required:
            entity.alive = False
            return DeathSaveOutcome(roll=roll, state="defeated", failures=failures, successes=successes)
        if successes >= self.rules.death_save_successes_required:
            death.update({"successes": 0, "failures": 0, "stable": True})
            return DeathSaveOutcome(roll=roll, state="stable")
        return DeathSaveOutcome(roll=roll, state="pending", failures=failures, successes=successes)

    def recover_from_zero_hp(self, entity: Entity) -> ZeroHPTransition:
        death = entity.component("death_saves")
        death.update({"successes": 0, "failures": 0, "stable": False})
        return ZeroHPTransition(state="recovered")


def _factory(rules: RuleSet, dice: DeterministicDice, conditions: ConditionRegistry) -> RulesRuntime:
    return SRD521RulesRuntime(rules, dice, conditions)


register_runtime("srd_5_2_1.core", _factory)
