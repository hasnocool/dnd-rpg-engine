from __future__ import annotations

import asyncio
import math
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Awaitable, Callable

from pydantic import BaseModel, Field


class SimulationSample(BaseModel):
    seed: int
    outcome: str
    metrics: dict[str, float] = Field(default_factory=dict)
    event_counts: dict[str, int] = Field(default_factory=dict)
    steps: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)


class MetricSummary(BaseModel):
    count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    stdev: float
    p10: float
    p90: float


class SimulationReport(BaseModel):
    scenario_id: str
    seeds: list[int]
    sample_count: int
    outcomes: dict[str, int] = Field(default_factory=dict)
    outcome_rates: dict[str, float] = Field(default_factory=dict)
    metrics: dict[str, MetricSummary] = Field(default_factory=dict)
    aggregate_event_counts: dict[str, int] = Field(default_factory=dict)
    samples: list[SimulationSample] = Field(default_factory=list)


class SimulationComparison(BaseModel):
    left_scenario_id: str
    right_scenario_id: str
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    outcome_rate_deltas: dict[str, float] = Field(default_factory=dict)


@dataclass(slots=True)
class SimulationScenario:
    id: str
    run_once: Callable[[int], Awaitable[SimulationSample]]


class SimulationLab:
    """Run deterministic seed matrices and aggregate balance/regression data."""

    def __init__(self, *, max_concurrency: int = 8, retain_samples: bool = True) -> None:
        self.max_concurrency = max(1, max_concurrency)
        self.retain_samples = retain_samples

    @staticmethod
    def seed_matrix(*, start: int = 1, count: int = 1000, stride: int = 1) -> list[int]:
        if count < 1:
            raise ValueError("simulation count must be positive")
        if stride < 1:
            raise ValueError("seed stride must be positive")
        return [start + index * stride for index in range(count)]

    async def run(self, scenario: SimulationScenario, seeds: list[int]) -> SimulationReport:
        if not seeds:
            raise ValueError("simulation requires at least one seed")
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def execute(seed: int) -> SimulationSample:
            async with semaphore:
                sample = await scenario.run_once(seed)
                if sample.seed != seed:
                    sample = sample.model_copy(update={"seed": seed})
                return sample

        samples = await asyncio.gather(*(execute(seed) for seed in seeds))
        samples = sorted(samples, key=lambda value: value.seed)
        return self.aggregate(scenario.id, samples, seeds=seeds)

    def aggregate(
        self,
        scenario_id: str,
        samples: list[SimulationSample],
        *,
        seeds: list[int] | None = None,
    ) -> SimulationReport:
        if not samples:
            raise ValueError("cannot aggregate an empty simulation set")
        outcomes = Counter(sample.outcome for sample in samples)
        metric_names = sorted({key for sample in samples for key in sample.metrics})
        summaries: dict[str, MetricSummary] = {}
        for name in metric_names:
            values = [float(sample.metrics[name]) for sample in samples if name in sample.metrics]
            summaries[name] = self._summary(values)
        events: Counter[str] = Counter()
        for sample in samples:
            events.update(sample.event_counts)
        total = len(samples)
        return SimulationReport(
            scenario_id=scenario_id,
            seeds=list(seeds if seeds is not None else [sample.seed for sample in samples]),
            sample_count=total,
            outcomes=dict(sorted(outcomes.items())),
            outcome_rates={key: value / total for key, value in sorted(outcomes.items())},
            metrics=summaries,
            aggregate_event_counts=dict(sorted(events.items())),
            samples=samples if self.retain_samples else [],
        )

    def compare(self, left: SimulationReport, right: SimulationReport) -> SimulationComparison:
        metric_names = sorted(set(left.metrics) | set(right.metrics))
        outcome_names = sorted(set(left.outcome_rates) | set(right.outcome_rates))
        return SimulationComparison(
            left_scenario_id=left.scenario_id,
            right_scenario_id=right.scenario_id,
            metric_deltas={
                name: right.metrics.get(name, self._zero_summary()).mean
                - left.metrics.get(name, self._zero_summary()).mean
                for name in metric_names
            },
            outcome_rate_deltas={
                name: right.outcome_rates.get(name, 0.0) - left.outcome_rates.get(name, 0.0)
                for name in outcome_names
            },
        )

    @staticmethod
    def _summary(values: list[float]) -> MetricSummary:
        ordered = sorted(values)
        count = len(ordered)
        if count == 0:
            return SimulationLab._zero_summary()
        return MetricSummary(
            count=count,
            minimum=ordered[0],
            maximum=ordered[-1],
            mean=statistics.fmean(ordered),
            median=statistics.median(ordered),
            stdev=statistics.pstdev(ordered) if count > 1 else 0.0,
            p10=SimulationLab._percentile(ordered, 0.10),
            p90=SimulationLab._percentile(ordered, 0.90),
        )

    @staticmethod
    def _percentile(values: list[float], fraction: float) -> float:
        if len(values) == 1:
            return values[0]
        position = (len(values) - 1) * fraction
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            return values[low]
        weight = position - low
        return values[low] * (1.0 - weight) + values[high] * weight

    @staticmethod
    def _zero_summary() -> MetricSummary:
        return MetricSummary(count=0, minimum=0.0, maximum=0.0, mean=0.0, median=0.0, stdev=0.0, p10=0.0, p90=0.0)
