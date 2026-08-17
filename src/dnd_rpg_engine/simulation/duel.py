from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.event_sourcing import canonical_json
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.simulation.lab import SimulationOutcome
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.combat import CombatSystem
from dnd_rpg_engine.tactical.conditions import default_conditions


class DuelScenario(BaseModel):
    left: Entity
    right: Entity
    left_action: ActionDefinition
    right_action: ActionDefinition
    rules: RuleSet = Field(default_factory=RuleSet)
    max_actions: int = Field(default=1000, ge=1, le=100_000)


class DuelSimulationCase:
    """Deterministic head-to-head combat case using the active rules runtime.

    This is intentionally presentation-free. It clones both entities for every
    iteration and uses action time as the readiness clock, making it suitable
    for bulk balancing runs without mutating the campaign that supplied the
    actor snapshots.
    """

    def __init__(self, scenario: DuelScenario) -> None:
        self.scenario = scenario

    async def simulate(self, *, seed: int, index: int) -> SimulationOutcome:
        left = self.scenario.left.model_copy(deep=True)
        right = self.scenario.right.model_copy(deep=True)
        dice = DeterministicDice(seed)
        combat = CombatSystem(dice, default_conditions(), self.scenario.rules.model_copy(deep=True))
        ready = {left.id: 0.0, right.id: 0.0}
        actions = {left.id: self.scenario.left_action, right.id: self.scenario.right_action}
        actors = {left.id: left, right.id: right}
        opponents = {left.id: right.id, right.id: left.id}
        damage_done = {left.id: 0, right.id: 0}
        criticals = {left.id: 0, right.id: 0}
        attacks = {left.id: 0, right.id: 0}
        time = 0.0

        for _ in range(self.scenario.max_actions):
            if left.resources.hp <= 0 or right.resources.hp <= 0:
                break
            actor_id = min(ready, key=lambda value: (ready[value], value))
            target_id = opponents[actor_id]
            actor = actors[actor_id]
            target = actors[target_id]
            action = actions[actor_id]
            time = ready[actor_id]
            resolution = combat.resolve_attack(actor, target, action)
            attacks[actor_id] += 1
            if resolution.critical:
                criticals[actor_id] += 1
            if resolution.hit:
                applied = combat.apply_damage_traits(target, resolution.damage, action.damage_type)
                before = target.resources.hp + target.resources.temp_hp
                target.resources.apply_damage(applied)
                damage_done[actor_id] += max(0, before - (target.resources.hp + target.resources.temp_hp))
            ready[actor_id] += action.time_cost

        winner: str | None
        if left.resources.hp <= 0 < right.resources.hp:
            winner = right.id
        elif right.resources.hp <= 0 < left.resources.hp:
            winner = left.id
        else:
            winner = None
        total_initial_hp = self.scenario.left.resources.max_hp + self.scenario.right.resources.max_hp
        total_remaining_hp = max(0, left.resources.hp) + max(0, right.resources.hp)
        utilization = 1.0 - min(1.0, total_remaining_hp / max(1, total_initial_hp))
        terminal = {
            left.id: left.model_dump(mode="json"),
            right.id: right.model_dump(mode="json"),
            "ready": ready,
        }
        terminal_hash = hashlib.sha256(canonical_json(terminal).encode()).hexdigest()
        return SimulationOutcome(
            winner=winner,
            duration=max(time, min(ready.values())),
            player_knockout=any(
                entity.resources.hp <= 0 and entity.kind.value == "player" for entity in (left, right)
            ),
            resource_utilization=utilization,
            terminal_state_hash=terminal_hash,
            metrics={
                f"damage.{left.id}": float(damage_done[left.id]),
                f"damage.{right.id}": float(damage_done[right.id]),
                f"attacks.{left.id}": float(attacks[left.id]),
                f"attacks.{right.id}": float(attacks[right.id]),
                f"criticals.{left.id}": float(criticals[left.id]),
                f"criticals.{right.id}": float(criticals[right.id]),
            },
            tags={"duel"},
        )
