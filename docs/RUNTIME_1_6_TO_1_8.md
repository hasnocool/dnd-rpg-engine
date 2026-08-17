# v1.6–v1.8 platform architecture

This document describes the layers added after the v1.2–v1.5 runtime foundation. The design keeps the authoritative simulation headless: character advancement, hosted-worker ownership, reconnect state, and Creator Studio output all feed the same command/event/content contracts used by text, web, TUI, 2D, and 3D clients.

## Layering

```text
Browser Creator Studio ─┐
REST / WebSocket clients ├──── /api/v1 ──── CampaignSession
TUI / Godot / CLI ──────┘                       │
                                                 ▼
                                      AdvancedGameEngine
                                        │      │      │
                                        │      │      └── Intelligent actors
                                        │      └───────── Spatial authority
                                        ├──────────────── Character lifecycle
                                        └──────────────── RulesRuntime
                                                 │
                                         command / events
                                                 │
                                      persistence contract
                                      ┌──────────┴─────────┐
                                      ▼                    ▼
                                   SQLite            PostgreSQL
                                local/dev mode      production mode
                                                         │
                                         worker registry + leases
                                                         │
                                        SimulationWorker fleet
```

`GameEngine` remains the compatibility-first engine. `AdvancedGameEngine` opts a campaign into the integrated post-v1.1 behavior and now owns the character lifecycle service in addition to the rules, spatial, and intelligent-actor integrations introduced by v1.2–v1.5.

## v1.6 — Character Lifecycle

### Goals

The lifecycle layer deliberately avoids hard-coding fifth-edition class progression into engine core. Rulesets provide class definitions, advancement tracks, class resources, rest profiles, and equipment metadata. The engine provides authoritative state transitions and events.

### Persistent character state

Lifecycle state is stored in ordinary entity components:

- `character` — species, background, class levels, XP, learned feature IDs, advancement track, unspent ability points;
- `character_resources` — typed per-class or per-character resources with short/long-rest recovery behavior;
- `equipment` — occupied slots, attuned items, and attunement capacity;
- `inventory` — existing inventory representation, reused for ownership checks.

Because these are normal entity components, they are automatically included in campaign snapshots and deterministic event-sourced state.

### Character construction

`CharacterBuildRequest` produces a normal player `Entity`. A class definition determines the initial hit die and resource catalog. The request can provide:

- name;
- class;
- species/background identifiers;
- six ability scores;
- starting level and XP;
- starting equipment;
- controller/owner metadata;
- tags.

The generic default ruleset exposes an `adventurer` class. The SRD integration exposes `build_srd_character_lifecycle()`, which maps the source-backed compact SRD class catalog into generic lifecycle class definitions.

### Advancement

`AdvancementTrack` supports two authoritative modes:

- `xp` — the track defines cumulative thresholds for each level;
- `milestone` — the campaign explicitly marks a character as ready before level-up.

`CharacterProgress.classes` is a mapping rather than a single class field. The total character level is therefore the sum of class levels, allowing multiclass-compatible state without putting multiclass rules into the generic engine.

Level-up produces a typed `LevelUpOutcome` containing:

- previous and new class level;
- new total character level;
- hit-point increase;
- resulting maximum HP;
- features learned;
- ability points granted;
- synchronized class-resource state.

The SRD proficiency helper now reads the lifecycle class-level sum first and retains the legacy `progression.level` fallback for older saves.

### Resources and rests

`ClassResourceDefinition` describes a resource maximum and rest recovery behavior. Examples could represent generic stamina, resolve, maneuvers, spell resources, or a custom ruleset's class feature pool.

`RestProfile` defines:

- short or long rest;
- authoritative duration;
- HP/energy recovery fractions;
- temporary-HP cleanup;
- class-resource recovery behavior.

A completed rest also resets the active `RulesRuntime` turn/action economy through the runtime interface.

### Equipment

`EquipmentDefinition` supports:

- one or more named slots;
- aggregate numeric modifiers;
- tags;
- optional attunement;
- displacement when a newly equipped item claims occupied slots.

The generic lifecycle service does not decide how a ruleset interprets a modifier such as `armor_class`. It exposes deterministic aggregate equipment modifiers for the rules runtime or UI to consume.

### Commands and API

`AdvancedGameEngine` accepts lifecycle operations through the existing `CustomCommand` envelope:

```text
character.award_xp
character.level_up
character.milestone_ready
character.rest
character.equip
character.unequip
character.spend_resource
character.restore_resource
```

Each operation emits authoritative `character.*` events. The platform API additionally exposes typed REST endpoints under:

```text
/api/v1/campaigns/{campaign_id}/characters/...
```

Owner-only operations such as XP awards, level-up, and resource restoration use the existing campaign-session authorization boundary. Actor-owned operations such as rests/equipment are still dispatched through `CampaignSession`, so ordinary multiplayer actor ownership rules remain in force.

## v1.7 — Production Campaign Hosting

### Persistence contract

Local development continues to use `SQLiteStore`. Production deployments can use `PostgreSQLStore`, selected from a PostgreSQL database URL by `create_store()`.

The PostgreSQL backend implements the same asynchronous operations used by the engine:

- campaign save/load/list;
- append/list events;
- save/load snapshots;
- namespaced JSON storage;
- hosted-campaign metadata.

`asyncpg` is an optional dependency and is imported lazily. SQLite-only installations therefore do not need PostgreSQL libraries.

### Migrations

The PostgreSQL store applies ordered, idempotent schema migrations at initialization. The initial migration set creates:

1. campaigns, events, snapshots, KV state, and hosted-campaign metadata;
2. simulation-worker registry and campaign leases;
3. reconnect-ticket lookup index.

Applied migrations are recorded in `schema_migrations`.

### Worker model

Production simulation workers are separate processes. Every worker:

1. registers its `worker_id`, capacity, and metadata;
2. sends heartbeats;
3. reads the hosted campaign set;
4. uses rendezvous hashing to calculate preferred ownership;
5. attempts to acquire an authoritative PostgreSQL campaign lease;
6. loads the campaign into `AdvancedGameEngine`;
7. runs the real-time clock when the campaign timing mode requires it;
8. renews the lease while healthy;
9. releases ownership during rebalancing or shutdown.

The hash router is advisory placement. The database lease is authoritative ownership, preventing two healthy processes from simulating the same campaign concurrently.

### Why rendezvous hashing

Rendezvous hashing provides deterministic placement without a separate coordinator. Adding a worker only moves campaigns whose new worker score becomes the highest. Removing a worker only moves campaigns previously assigned to that worker. This makes scale-out and worker replacement much less disruptive than simple modulo partitioning.

### Reconnect and resume

`ReconnectManager` creates cryptographically random opaque tokens. Raw tokens are only returned to the client; persistence stores the SHA-256 token hash.

A resume record contains:

- campaign ID;
- full `ClientIdentity` needed to rejoin the campaign session;
- last acknowledged event sequence;
- expiration;
- revoked state.

On successful resume:

1. the identity rejoins the campaign session;
2. the client receives events after its checkpoint;
3. the old token is revoked;
4. a fresh token is issued.

Clients can periodically checkpoint the highest event sequence they have durably processed.

### Production commands

Install PostgreSQL support:

```bash
python -m pip install -e '.[hosting]'
```

Start the complete platform server:

```bash
RPG_DATABASE_URL='postgresql://user:pass@host/db' rpg-engine-host
```

The main CLI also accepts a PostgreSQL URL:

```bash
rpg-engine serve --database 'postgresql://user:pass@host/db'
```

Start one or more simulation workers:

```bash
RPG_DATABASE_URL='postgresql://user:pass@host/db' \
RPG_WORKER_CAPACITY=32 \
rpg-engine-worker
```

Multiple workers can point at the same database. Worker IDs are generated from hostname plus a random suffix unless supplied explicitly.

### Deployment shape

A typical production deployment is:

```text
reverse proxy / TLS
        │
        ▼
RPG API/WebSocket replicas
        │
        ├──────── PostgreSQL
        │              ▲
        │              │ leases / state / events
        ▼              │
client sessions        │
                       │
              SimulationWorker × N
```

The API process handles requests, WebSockets, campaign sessions, Creator Studio, and reconnect. Workers own ongoing campaign simulation. PostgreSQL is the shared state and lease authority.

## v1.8 — Creator Studio

### Typed projects, not JSON blobs

The original creator page was a raw JSON editor. Creator Studio now persists `StudioProject` objects whose `pack` field is the actual runtime `ContentPack` model.

Typed sections map directly to engine models:

| Studio section | Runtime model |
| --- | --- |
| Campaigns | `CampaignTemplate` |
| Creatures | `CreatureTemplate` |
| Maps | `WorldMap` |
| Rules | `RuleDocument` |
| Spells | `SpellDefinition` |
| Quests | `QuestDefinition` |

The Studio cannot silently invent a second content format that later needs conversion.

### Revision model

Every successful edit increments the Studio project revision and stores a complete immutable revision snapshot. Restoring an old revision copies its pack into a new current revision; history is not overwritten.

This supports:

- experimentation;
- recovering accidental changes;
- comparing exported pack hashes;
- future collaborative-edit or review workflows.

### Visual map editor

The browser map workspace renders `WorldMap` nodes and edges directly as SVG.

Capabilities include:

- create nodes;
- drag nodes to change editor coordinates;
- edit node name, description, coordinates, and tags;
- select two nodes;
- create directed or bidirectional travel edges;
- configure travel time;
- fit the map viewport.

The same graph remains usable by text clients because node coordinates are presentation metadata rather than the fundamental connectivity model.

### Structured editors

The browser includes typed forms for:

- creature identity, tier, HP, ability scores, actions, tags, and AI profile;
- spell cast time, range, energy cost, ability, damage/heal expressions, condition, duration, and tags;
- quest description, objectives, targets, counts, and rewards;
- common rule settings plus ruleset-specific key/value fields;
- campaign start map, active rules, description, and flags.

### Validation, export, publication

Studio validation calls the existing `ContentValidator`. Export is blocked if the current pack is invalid. Marketplace publication uses the existing `MarketplaceRegistry` and stores the same validated `ContentPack` that runtime campaign instantiation consumes.

### API

Studio endpoints live under:

```text
/api/v1/studio/projects
```

The API supports project creation, typed upserts/deletes, map editing, validation, revision restore, export, and publication.

### Browser entrypoint

Run:

```bash
rpg-engine serve
```

Then open `/creator`. `rpg-engine serve` now launches the complete v1.8 platform factory so the visual page and Studio API are always paired.

## Compatibility guarantees

- `/api/v1` remains the wire namespace; package versioning is independent.
- `GameEngine` remains available for compatibility-first integrations.
- `AdvancedGameEngine` is the integrated v1.2–v1.8 profile.
- SQLite remains supported for local and single-process games.
- Existing renderer clients continue to consume commands/events rather than lifecycle, hosting, or Studio internals.
- SRD mechanics remain in the opt-in SRD ruleset/lifecycle adapters rather than being hard-coded into generic character core.
