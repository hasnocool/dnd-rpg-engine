# Architecture

## Principles

1. **Headless core** — simulation has no dependency on pixels, meshes, HTML, terminal rendering, or input devices.
2. **Commands in, events out** — clients request actions; only authoritative engine services mutate trusted state.
3. **Deterministic randomness** — independent SHA-256-derived RNG streams make tests, simulation runs, and replay reproducible.
4. **Timeline first** — turns, live play, bounded pauses, delayed effects, reactions, schedules, and world events are policies over one simulation timeline.
5. **Async at boundaries** — SQLite work runs through `asyncio.to_thread()` with short-lived connections; PostgreSQL/networking are asynchronous; presentation queues do not block the authoritative mutation path.
6. **Data-driven content** — typed content packs and bounded executable rule graphs extend campaigns without arbitrary server-side scripts.
7. **Authority-aware presentation** — Workbench, Hero/NPC Workshop, Creator Studio, TUI, REST/WebSocket clients, and visual adapters submit requests and render projections; none becomes a second rules engine.
8. **Knowledge is not truth** — actor/player projections are derived from perception and remembered knowledge rather than exposing hidden live state.
9. **AI proposes or commands through normal boundaries** — narration and Director intelligence cannot bypass validation or directly invent authoritative truth.

## Engine profiles

```text
GameEngine
  compatibility-first deterministic simulation
       │
       ▼
AdvancedGameEngine
  RulesRuntime + event sourcing + SpatialAuthority
  + intelligent actors + CharacterLifecycle
       │
       ▼
WorldPlatformEngine
  executable rules + CampaignOrchestrator
  + KnowledgeAuthority + AIDirector
  + RuntimeSynchronizer + persistent-world services
```

`rpg-engine serve` and `rpg-engine-host` use the world-platform profile by default. Compatibility surfaces remain available for integrations that intentionally target earlier behavior.

## Module map

```text
src/dnd_rpg_engine/
├── core/          models, commands, events, dice, checks, scheduler, engines, persistence
├── rules/         typed runtime, modifiers, effects, reactions, executable rule compiler/executor
├── tactical/      actions, combat, conditions, items, spells, movement
├── spatial/       graph/grid/continuous spaces, pathfinding, LOS, cover, movement authority
├── adventure/     maps, exploration, dialogue, quests, NPCs, shops
├── living/        time, weather, factions, schedules, economy, dynamic events
├── ai/            narrator, actor intelligence, memory, personalities, encounters, Director
├── characters/    lifecycle, progression, resources, rests, equipment
├── multiplayer/   protocol, parties, authoritative campaign sessions
├── creator/       content models, validation, Studio projects, loader, marketplace/distribution
├── world/         orchestration, knowledge/runtime sync, persistent-world/shard primitives
├── hosting/       PostgreSQL, migrations, workers, leases, reconnect/resume
├── api/           REST/WebSocket routers and platform app composition
└── web/           Campaign Workbench, Hero/NPC Workshop, Creator Studio
```

## Authoritative command/event flow

```text
client / UI / adapter
        │
        ▼
validated request or GameCommand
        │
        ├─ identity / actor-ownership validation
        ├─ optimistic version validation
        ├─ readiness / timing validation
        ├─ rules / resource / spatial validation
        ▼
authoritative engine service
        │
        ├─ mutate state
        ├─ schedule future work
        └─ produce GameEvent(s)
               │
               ├─ append-only event persistence
               ├─ event-source journal where enabled
               ├─ quest/world consumers
               ├─ knowledge filtering
               ├─ WebSocket fan-out
               ├─ runtime snapshots/deltas
               └─ optional narration/presentation
```

The browser never calculates a trusted hit, movement cost, progression result, NPC schedule outcome, resource spend, line of sight, or AI decision locally.

## Campaign orchestration and knowledge

`CampaignOrchestrator` owns active scene lifecycle and determines which scene-related entities are active or preloaded. `KnowledgeAuthority` creates actor-scoped views from authoritative campaign truth. `RuntimeSynchronizer` then converts full owner state or redacted knowledge views into canonical/hash-verified client snapshots and deltas.

```text
CampaignState truth
      │
      ├── CampaignOrchestrator
      ├── RulesRuntime / SpatialAuthority / CharacterLifecycle
      └── living-world + AI systems
      │
      ▼
PerceptionSystem
      │
      ▼
KnowledgeAuthority
      │
      ▼
RuntimeSynchronizer
      │
      ▼
Workbench / player client / Godot / remote adapter
```

## Creator and actor-management split

The v4.0 product layer intentionally separates reusable source content from campaign-instance actors:

```text
Creator Studio (/creator)
  project revisions + ContentPack source
        │ validate / publish / install
        ▼
Running campaign
        ├── Campaign Workbench (/)
        └── Hero & NPC Workshop (/hero)
```

Hero creation delegates to `CharacterLifecycle`. Safe character edits do not bypass advancement/equipment/resource rules. NPC CRUD is owner-only and keeps registered `NPCProfile` data synchronized with the live entity and schedule assignment.

## Persistence

SQLite uses WAL mode. SQLite database work occurs through `asyncio.to_thread()` with short-lived connections, preventing blocking calls on the event loop and avoiding unsafe cross-thread connection sharing.

PostgreSQL is the production backend for hosted deployments and supports the same campaign/event/snapshot/JSON persistence contracts plus worker/lease/reconnect metadata.

Campaign rows store the latest materialized state. Events are append-only and sequenced. Snapshots capture state plus deterministic runtime metadata. Event-sourced profiles additionally maintain hash-chained state journals for verification/replay/branching. Runtime metadata preserves timing configuration, scheduler tasks, RNG positions, and related deterministic state across resume.

## Hosting and persistent worlds

Production simulation workers use stable preferred placement plus PostgreSQL leases so a campaign has one authoritative simulator. Reconnect tickets are opaque and stored by hash.

The v3.0 persistent-world layer adds shard registration, region affinity/routing, Lamport-ordered cross-shard messages, and hash-verified two-phase entity handoff. These are deterministic engine contracts; deployment transport, service discovery, capacity planning, and observability remain infrastructure responsibilities.

## Multiplayer

Each campaign has one authoritative `CampaignSession`. Commands are serialized with an async lock per campaign rather than one global lock. Clients have server-resolved roles (`owner`, `player`, `spectator`) and explicit actor ownership. Spectators are read-only. WebSocket fan-out is presentation-only and cannot backpressure the persisted authoritative event path.

## Browser surfaces

- `/` — Campaign Workbench for campaign/session operations and live play.
- `/hero` — v4.0 Hero & NPC Workshop for campaign-instance actors.
- `/creator` — reusable content/project authoring and publication.
- `/docs` — OpenAPI.

See `WORKBENCH.md`, `ACTORS_4_0.md`, `CREATOR.md`, and `API.md` for the product-specific flows.
