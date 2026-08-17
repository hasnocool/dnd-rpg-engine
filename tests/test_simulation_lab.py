from __future__ import annotations

import pytest

from dnd_rpg_engine.simulation import ExperimentDefinition, FunctionSimulationCase, SimulationLab, SimulationOutcome


@pytest.mark.asyncio
async def test_simulation_lab_is_deterministic_and_aggregates_metrics() -> None:
    async def simulate(seed: int, index: int) -> SimulationOutcome:
        return SimulationOutcome(
            winner="heroes" if seed % 4 else "monsters",
            duration=20.0 + (seed % 20),
            player_knockout=seed % 5 == 0,
            resource_utilization=(seed % 100) / 100,
            metrics={"damage": float(seed % 50)},
        )

    definition = ExperimentDefinition(id="encounter", iterations=64, base_seed=77, concurrency=7)
    lab = SimulationLab()
    first = await lab.run(definition, FunctionSimulationCase(simulate))
    second = await lab.run(definition, FunctionSimulationCase(simulate))
    assert first.deterministic_digest == second.deterministic_digest
    assert first.winner_counts == second.winner_counts
    assert first.iterations == 64
    assert 0 <= first.knockout_rate <= 1
    assert "damage" in first.metric_means
