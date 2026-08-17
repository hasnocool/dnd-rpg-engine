# tests/test_scheduler.py
from dnd_rpg_engine.core.scheduler import TimelineScheduler


def test_scheduler_orders_by_time_priority_sequence() -> None:
    scheduler = TimelineScheduler()
    scheduler.schedule("late", delay=2, priority=100)
    scheduler.schedule("low_priority", delay=1, priority=100)
    scheduler.schedule("high_priority", delay=1, priority=10)
    due = scheduler.advance(1)
    assert [task.kind for task in due] == ["high_priority", "low_priority"]
    assert scheduler.advance(1)[0].kind == "late"


def test_scheduler_snapshot_restore() -> None:
    scheduler = TimelineScheduler(4)
    scheduler.schedule("x", delay=3, actor_id="a", payload={"n": 1})
    snapshot = scheduler.snapshot()
    restored = TimelineScheduler(4)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
