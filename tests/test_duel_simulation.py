from __future__ import annotations

import pytest

from dnd_rpg_engine.core.models import Entity, EntityKind, ResourcePool
from dnd_rpg_engine.simulation import DuelScenario, DuelSimulationCase, ExperimentDefinition, SimulationLab
from dnd_rpg_engine.tactical.actions import ActionDefinition


@pytest.mark.asyncio
async def test_duel_simulation_is_deterministic_and_does_not_mutate_inputs() -> None:
    left = Entity(id="left", name="Left", kind=EntityKind.PLAYER, resources=ResourcePool(hp=24, max_hp=24))
    right = Entity(id="right", name="Right", resources=ResourcePool(hp=24, max_hp=24))
    action = ActionDefinition(id="strike", name="Strike", damage="1d6", time_cost=6.0)
    scenario = DuelScenario(left=left, right=right, left_action=action, right_action=action)
    definition = ExperimentDefinition(id="duel", iterations=32, base_seed=123, concurrency=5)
    lab = SimulationLab()
    first = await lab.run(definition, DuelSimulationCase(scenario))
    second = await lab.run(definition, DuelSimulationCase(scenario))
    assert first.deterministic_digest == second.deterministic_digest
    assert sum(first.winner_counts.values()) == 32
    assert left.resources.hp == 24
    assert right.resources.hp == 24
