# src/dnd_rpg_engine/core/scheduler.py
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(order=True, slots=True)
class ScheduledTask:
    due_time: float
    priority: int
    sequence: int
    id: str = field(compare=False, default_factory=lambda: str(uuid4()))
    kind: str = field(compare=False, default="custom")
    actor_id: str | None = field(compare=False, default=None)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)
    cancelled: bool = field(compare=False, default=False)


class TimelineScheduler:
    """Deterministic simulation-time priority queue."""

    def __init__(self, start_time: float = 0.0) -> None:
        self.now = float(start_time)
        self._heap: list[ScheduledTask] = []
        self._sequence = 0
        self._tasks: dict[str, ScheduledTask] = {}

    def schedule(
        self,
        kind: str,
        *,
        delay: float = 0.0,
        due_time: float | None = None,
        priority: int = 100,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ScheduledTask:
        if delay < 0:
            raise ValueError("delay cannot be negative")
        target = self.now + delay if due_time is None else float(due_time)
        if target < self.now:
            target = self.now
        self._sequence += 1
        task = ScheduledTask(
            due_time=target,
            priority=priority,
            sequence=self._sequence,
            kind=kind,
            actor_id=actor_id,
            payload=dict(payload or {}),
        )
        self._tasks[task.id] = task
        heapq.heappush(self._heap, task)
        return task

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.cancelled = True
        return True

    def requeue(self, task: ScheduledTask) -> None:
        if task.cancelled:
            return
        self._tasks[task.id] = task
        self._sequence = max(self._sequence, task.sequence)
        heapq.heappush(self._heap, task)

    def requeue_many(self, tasks: list[ScheduledTask]) -> None:
        for task in tasks:
            self.requeue(task)

    def cancel_matching(self, *, kind: str | None = None, actor_id: str | None = None) -> int:
        count = 0
        for task in self._tasks.values():
            if task.cancelled:
                continue
            if kind is not None and task.kind != kind:
                continue
            if actor_id is not None and task.actor_id != actor_id:
                continue
            task.cancelled = True
            count += 1
        return count

    def peek(self) -> ScheduledTask | None:
        self._discard_cancelled()
        return self._heap[0] if self._heap else None

    def advance(self, delta: float) -> list[ScheduledTask]:
        if delta < 0:
            raise ValueError("simulation time cannot move backward")
        self.now += delta
        return self.pop_due()

    def advance_to(self, target: float) -> list[ScheduledTask]:
        if target < self.now:
            raise ValueError("simulation time cannot move backward")
        self.now = target
        return self.pop_due()

    def advance_to_next(self) -> list[ScheduledTask]:
        next_task = self.peek()
        if next_task is None:
            return []
        self.now = max(self.now, next_task.due_time)
        return self.pop_due()

    def pop_due(self) -> list[ScheduledTask]:
        due: list[ScheduledTask] = []
        self._discard_cancelled()
        while self._heap and self._heap[0].due_time <= self.now:
            task = heapq.heappop(self._heap)
            self._tasks.pop(task.id, None)
            if not task.cancelled:
                due.append(task)
            self._discard_cancelled()
        return due


    def restore(self, rows: list[dict[str, Any]]) -> None:
        """Restore a persisted scheduler snapshot without changing due times."""
        self._heap.clear()
        self._tasks.clear()
        self._sequence = 0
        for row in rows:
            sequence = int(row.get("sequence", self._sequence + 1))
            task = ScheduledTask(
                due_time=max(self.now, float(row["due_time"])),
                priority=int(row.get("priority", 100)),
                sequence=sequence,
                id=str(row.get("id") or uuid4()),
                kind=str(row.get("kind", "custom")),
                actor_id=row.get("actor_id"),
                payload=dict(row.get("payload") or {}),
            )
            self._sequence = max(self._sequence, sequence)
            self._tasks[task.id] = task
            heapq.heappush(self._heap, task)

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "id": t.id,
                "kind": t.kind,
                "due_time": t.due_time,
                "priority": t.priority,
                "sequence": t.sequence,
                "actor_id": t.actor_id,
                "payload": t.payload,
            }
            for t in sorted(self._heap)
            if not t.cancelled
        ]

    def _discard_cancelled(self) -> None:
        while self._heap and self._heap[0].cancelled:
            task = heapq.heappop(self._heap)
            self._tasks.pop(task.id, None)
