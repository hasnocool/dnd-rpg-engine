# Unified timing model

## Why one scheduler

The engine does not implement a separate "turn combat" and "real-time combat". Every actor and delayed effect lives on one simulation timeline. Mode configuration decides when that timeline is allowed to advance.

## Modes

### `turn_based`

Wall-clock `tick()` calls do not advance simulation time. When a human becomes ready, the scheduler stops before later work executes. After the human submits a command, the engine advances deterministically until the next human decision point.

### `timed_turn_based`

A human readiness event opens a configured real-time decision window. The simulation clock pauses during that window. If the player does nothing, the pause expires and deferred timeline work resumes. The player can remain ready and submit an action later while AI actors continue on their own cadence.

### `real_time`

No decision pause is applied. `run_realtime()` advances simulation time at `ticks_per_second`; actors act whenever their readiness task becomes due.

### `real_time_with_pause`

Identical authoritative timeline to real time, but human readiness opens a bounded decision pause.

### `hybrid`

Designed for live exploration plus tactical decision windows. It uses the same bounded-pause semantics and can be switched to another mode at runtime through the API.

## Clock layers

```text
monotonic wall clock
        │
        ▼
real delta supplied to engine.tick()
        │
        ├─ bounded decision pause consumes wall time without simulation advance
        ▼
simulation clock (scaled by time_scale)
        │
        ├─ actor readiness
        ├─ delayed effects
        ├─ condition ticks
        └─ dynamic tasks
        │
        ▼
world clock (world_minutes_per_sim_second)
        │
        ├─ weather
        ├─ schedules
        ├─ economy
        └─ dynamic world events
```

## Idle behavior

In `real_time`, or after a timed/hybrid decision window expires, a ready human does not block the scheduler. AI entities continue receiving readiness opportunities. Each AI action schedules its next readiness based on the action/movement time, so inactivity naturally permits repeated enemy actions without special polling loops.

## Rendering independence

Rendering frame rate is not simulation tick rate. A 30 FPS web client, 60/120 FPS Godot client, terminal UI, and headless server can all observe the same authoritative timeline.
