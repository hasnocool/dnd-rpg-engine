from __future__ import annotations

import asyncio
import hashlib
import math
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel, Field


class SimulationOutcome(BaseModel):
    winner: str | None = None
    duration: float = Field(default=0.0, ge=0)
    player_knockout: bool = False
    resource_utilization: float | None = Field(default=None, ge=0, le=1)
    terminal_state_hash: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    tags: set[str] = Field(default_factory=set)


class ExperimentDefinition(BaseModel):
    id: str
    iterations: int = Field(default=1000, ge=1, le=1_000_000)
    base_seed: int = 1
    concurrency: int = Field(default=8, ge=1, le=256)
    expected_winner: str | None = None
    target_win_rate_min: float | None = Field(default=None, ge=0, le=1)
    target_win_rate_max: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentFinding(BaseModel):
    severity: str
    code: str
    message: str
    value: float | None = None


class ExperimentReport(BaseModel):
    experiment_id: str
    iterations: int
    winner_counts: dict[str, int]
    win_rates: dict[str, float]
    median_duration: float
    p95_duration: float
    knockout_rate: float
    mean_resource_utilization: float | None = None
    metric_means: dict[str, float] = Field(default_factory=dict)
    deterministic_digest: str
    findings: list[ExperimentFinding] = Field(default_factory=list)


class SimulationCase(Protocol):
    async def simulate(self, *, seed: int, index: int) -> SimulationOutcome: ...


class FunctionSimulationCase:
    def __init__(self, fn: Callable[[int, int], SimulationOutcome | Awaitable[SimulationOutcome]]) -> None:
        self.fn = fn

    async def simulate(self, *, seed: int, index: int) -> SimulationOutcome:
        value = self.fn(seed, index)
        if isinstance(value, Awaitable):
            value = await value
        return value


class BalanceAnalyzer:
    def analyze(self, definition: ExperimentDefinition, report: ExperimentReport) -> list[ExperimentFinding]:
        findings: list[ExperimentFinding] = []
        if definition.expected_winner:
            rate = report.win_rates.get(definition.expected_winner, 0.0)
            if definition.target_win_rate_min is not None and rate < definition.target_win_rate_min:
                findings.append(
                    ExperimentFinding(
                        severity="warning",
                        code="win_rate_low",
                        message=f"{definition.expected_winner} wins less often than the configured target",
                        value=rate,
                    )
                )
            if definition.target_win_rate_max is not None and rate > definition.target_win_rate_max:
                findings.append(
                    ExperimentFinding(
                        severity="warning",
                        code="win_rate_high",
                        message=f"{definition.expected_winner} wins more often than the configured target",
                        value=rate,
                    )
                )
        if report.knockout_rate > 0.65:
            findings.append(
                ExperimentFinding(
                    severity="warning",
                    code="knockout_pressure",
                    message="player knockout rate exceeds 65%",
                    value=report.knockout_rate,
                )
            )
        if report.mean_resource_utilization is not None and report.mean_resource_utilization > 0.9:
            findings.append(
                ExperimentFinding(
                    severity="info",
                    code="resource_starvation",
                    message="average resource utilization exceeds 90%",
                    value=report.mean_resource_utilization,
                )
            )
        return findings


class SimulationLab:
    def __init__(self, analyzer: BalanceAnalyzer | None = None) -> None:
        self.analyzer = analyzer or BalanceAnalyzer()

    @staticmethod
    def derived_seed(base_seed: int, index: int) -> int:
        digest = hashlib.sha256(f"{base_seed}:{index}".encode()).digest()
        return int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF

    async def run(self, definition: ExperimentDefinition, case: SimulationCase) -> ExperimentReport:
        semaphore = asyncio.Semaphore(definition.concurrency)
        outcomes: list[SimulationOutcome | None] = [None] * definition.iterations

        async def execute(index: int) -> None:
            async with semaphore:
                outcomes[index] = await case.simulate(seed=self.derived_seed(definition.base_seed, index), index=index)

        async with asyncio.TaskGroup() as group:
            for index in range(definition.iterations):
                group.create_task(execute(index))
        completed = [value for value in outcomes if value is not None]
        report = self.summarize(definition, completed)
        report.findings = self.analyzer.analyze(definition, report)
        return report

    def summarize(self, definition: ExperimentDefinition, outcomes: list[SimulationOutcome]) -> ExperimentReport:
        winner_counts: dict[str, int] = defaultdict(int)
        durations: list[float] = []
        knockouts = 0
        resource_values: list[float] = []
        metrics: dict[str, list[float]] = defaultdict(list)
        digest = hashlib.sha256()
        for index, outcome in enumerate(outcomes):
            winner_counts[outcome.winner or "draw"] += 1
            durations.append(outcome.duration)
            knockouts += int(outcome.player_knockout)
            if outcome.resource_utilization is not None:
                resource_values.append(outcome.resource_utilization)
            for key, value in sorted(outcome.metrics.items()):
                metrics[key].append(float(value))
            digest.update(f"{index}:".encode())
            digest.update(outcome.model_dump_json(exclude_none=True).encode())
            digest.update(b"\n")
        total = max(1, len(outcomes))
        sorted_durations = sorted(durations)
        report = ExperimentReport(
            experiment_id=definition.id,
            iterations=len(outcomes),
            winner_counts=dict(sorted(winner_counts.items())),
            win_rates={key: value / total for key, value in sorted(winner_counts.items())},
            median_duration=_percentile(sorted_durations, 0.5),
            p95_duration=_percentile(sorted_durations, 0.95),
            knockout_rate=knockouts / total,
            mean_resource_utilization=(sum(resource_values) / len(resource_values)) if resource_values else None,
            metric_means={key: sum(values) / len(values) for key, values in sorted(metrics.items()) if values},
            deterministic_digest=digest.hexdigest(),
        )
        return report

    async def compare(
        self,
        definition: ExperimentDefinition,
        cases: dict[str, SimulationCase],
    ) -> dict[str, ExperimentReport]:
        reports: dict[str, ExperimentReport] = {}
        for name in sorted(cases):
            variant = definition.model_copy(update={"id": f"{definition.id}:{name}"})
            reports[name] = await self.run(variant, cases[name])
        return reports


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = min(max(fraction, 0.0), 1.0) * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight
