# Architecture

## Principles

1. **Headless core** — the simulation has no dependency on pixels, meshes, HTML, terminal rendering, or input devices.
2. **Commands in, events out** — clients request actions; only the authoritative engine mutates state.
3. **Deterministic randomness** — independent SHA-256-derived RNG streams make tests and replays reproducible.
4. **Timeline first** — turns, live play, bounded pauses, delayed effects, and world events are scheduling policies over one clock.
5. **Async at boundaries** — SQLite runs in worker threads through an async facade; networking uses ASGI/WebSockets; presentation queues never block the simulation loop.
6. **Data-driven content** — content packs register actions, conditions, items, spells, maps, dialogue, quests, campaigns, and rules without editing core engine code.
7. **Authoritative narration boundary** — AI-generated prose can describe engine truth but cannot create truth by itself.

## Module map

```text
src/dnd_rpg_engine/
├── core/        models, commands, events, dice, checks, scheduler, engine, persistence
├── tactical/    actions, combat, conditions, items, spells, movement
├── adventure/   maps, exploration, dialogue, quests, NPCs, shops
├── living/      time, weather, factions, schedules, economy, dynamic events
├── ai/          narrator, memory, personalities, encounters, generated quests
├── multiplayer/ protocol, parties, authoritative campaign sessions
├── creator/     content models, validation, loader, community marketplace registry
├── api/         REST/WebSocket server
└── web/         browser and creator clients
```

## Command/event flow

```text
input client
    │
    ▼
GameCommand
    │
    ├─ optimistic version validation
    ├─ actor ownership validation (multiplayer)
    ├─ readiness / timing validation
    ▼
authoritative system mutation
    │
    ├─ schedule future work
    ├─ update state
    └─ produce GameEvent(s)
           │
           ├─ SQLite append-only event log
           ├─ quest/event consumers
           ├─ WebSocket fan-out
           ├─ TUI/browser/Godot presentation
           └─ optional narrator
```

## Persistence

SQLite uses WAL mode. Every database operation occurs in `asyncio.to_thread()` with short-lived connections, preventing SQLite calls from blocking the event loop or sharing unsafe connection state across threads.

Campaign rows store the latest materialized state. Events are append-only and sequenced. Periodic snapshots capture state + RNG counters + scheduler state. Runtime metadata stores timing configuration, scheduler tasks, decision readiness, and deterministic RNG positions so a campaign can resume with the same timeline.

## Multiplayer

Each campaign has one authoritative `CampaignSession`. Commands are serialized with an async lock per campaign, not globally. Clients have roles (`owner`, `player`, `spectator`) and explicit actor ownership. Spectators are read-only. WebSocket fan-out is presentation-only and cannot backpressure the engine's persisted event path.
