# Production Authority & Playability — v4.1 to v5.0

This document defines the recommended production-maturity phase after the completed v4.0 Hero & NPC Experience milestone.

The project already has broad subsystem coverage: deterministic simulation, executable rules, event sourcing, spatial authority, intelligent actors, character lifecycle, Creator Studio, campaign orchestration, knowledge authority, runtime synchronization, content distribution, persistent-world foundations, multiplayer, and actor-management workflows.

The next phase should prioritize **depth, integration, correctness, operability, compatibility, and actual playability** before adding another major independent subsystem.

## Guiding principle

The central risk is breadth outrunning production depth.

The next milestones therefore focus on proving that existing systems work together under realistic campaign operation, restart, concurrency, failure, replay, migration, and hosted-multiplayer conditions.

```text
v4.0 Hero & NPC Experience
      ↓
v4.1 End-to-End Campaign Runtime
      ↓
v4.2 Runtime Correctness
      ↓
v4.3 Identity + Authorization
      ↓
v4.4 Observability
      ↓
v4.5 Scale + Performance
      ↓
v4.6 Player Experience
      ↓
v4.7 Campaign Import / Export
      ↓
v4.8 Content Compatibility
      ↓
v4.9 Production Multiplayer
      ↓
v5.0 Production RPG Platform
```

---

# v4.1 — End-to-End Campaign Runtime

The first priority is a canonical campaign that proves the existing architecture works as one complete gameplay loop.

## Canonical runtime flow

```text
Create campaign
      ↓
Install rules/content
      ↓
Create heroes
      ↓
Create/add NPCs
      ↓
Start scene
      ↓
Explore world
      ↓
NPC schedules + AI operate
      ↓
Encounter starts
      ↓
Players take actions
      ↓
Rules/effects/reactions resolve
      ↓
Knowledge changes
      ↓
Quest/world/faction state changes
      ↓
Scene transitions
      ↓
Rest/downtime/travel
      ↓
Save
      ↓
Server restart
      ↓
Reconnect
      ↓
Resume identically
      ↓
Replay/branch campaign
```

## Campaign Certification Suite

Create one canonical deterministic campaign that exercises:

- hero creation;
- NPC creation;
- content installation;
- scene orchestration;
- exploration;
- dialogue;
- quest progression;
- NPC schedules;
- weather/time;
- factions;
- combat;
- movement and LOS;
- spells;
- reactions;
- conditions;
- inventory;
- rests;
- AI actors;
- knowledge filtering;
- multiplayer ownership;
- event persistence;
- server restart;
- reconnection;
- replay;
- runtime snapshots;
- campaign completion.

The suite should assert the final deterministic campaign hash and verify that restart/resume/replay produce the same result.

## Acceptance criteria

- [ ] canonical campaign fixture exists in-repo;
- [ ] one command-driven integration path covers campaign creation through completion;
- [ ] save/restart/resume reproduces identical state;
- [ ] reconnect restores client state from authoritative server data;
- [ ] replay reproduces the final state hash;
- [ ] branch/rewind tests prove deterministic divergence from a known journal point;
- [ ] no browser/client-side special casing is required to make the scenario pass;
- [ ] SQLite and PostgreSQL-backed variants are covered where applicable.

---

# v4.2 — Runtime Correctness

The deterministic architecture should be protected by runtime invariants, property tests, fuzzing, concurrency tests, and controlled failure injection.

## Core invariants

Examples include:

```text
entity IDs are globally unique
HP never exceeds configured maximum unless explicitly permitted
resources cannot become negative
inventory ownership is singular unless stack semantics allow otherwise
an actor cannot occupy impossible coordinates
two solid actors cannot occupy exclusive space
hidden knowledge never contains live hidden-state references
dead/incapacitated actors cannot take prohibited actions
action economy never overspends
a consumed item cannot be consumed twice
an entity cannot belong authoritatively to two shards
one campaign cannot have two authoritative workers
event sequence numbers never regress
event hashes always form an uninterrupted chain
replaying events generates the exact state hash
command idempotency produces exactly one mutation
knowledge projection never reveals forbidden components
```

## Test strategy

- Hypothesis property tests;
- randomized valid command sequences;
- deterministic fuzz seeds retained on failure;
- replay verification after generated sequences;
- persistence round trips;
- restart tests;
- malformed ContentPack testing;
- malformed executable-rule graph testing;
- ownership/permission fuzzing;
- concurrent command dispatch testing;
- worker lease contention tests;
- network/database failure injection around persistence and reconnect boundaries.

## Acceptance criteria

- [ ] formal invariant registry exists;
- [ ] invariant checks can run in tests and optionally diagnostic builds;
- [ ] randomized campaigns retain reproducible seeds on failure;
- [ ] generated command sequences verify replay hashes;
- [ ] concurrency tests cover duplicate commands and lease contention;
- [ ] failure-injection tests cover interrupted persistence/reconnect/transfer paths;
- [ ] hidden-state leakage property tests exist for knowledge projections.

---

# v4.3 — Identity + Authorization

The current client/user identity mechanism is appropriate for local development but should become a pluggable hosted identity boundary.

## Proposed model

```text
IdentityProvider
      │
      ├── LocalIdentityProvider
      ├── APIKeyIdentityProvider
      ├── JWTIdentityProvider
      └── OAuthOIDCIdentityProvider
                  │
                  ▼
              Principal
                  │
          campaign membership
                  │
             actor ownership
                  │
                  ▼
        AuthorizationPolicy
```

Every authority-sensitive operation should resolve identity and authorization server-side.

## Protected capabilities

- campaign ownership;
- NPC CRUD;
- actor ownership;
- AI Director accept/dismiss;
- Creator publication;
- content installation;
- shard administration;
- replay/rewind;
- branching;
- campaign deletion;
- privileged knowledge views;
- administrative hosting operations.

## Acceptance criteria

- [ ] `IdentityProvider` abstraction;
- [ ] local development provider preserves current zero-friction workflows;
- [ ] API-key identity provider;
- [ ] JWT provider;
- [ ] OAuth/OIDC provider interface;
- [ ] typed `Principal` and campaign membership model;
- [ ] centralized authorization policy checks;
- [ ] audit records for privileged mutations;
- [ ] negative authorization integration suite.

---

# v4.4 — Observability

The engine should expose production-grade diagnostics across command execution, persistence, scheduling, rules, AI, networking, workers, replay, and sharding.

## OpenTelemetry-compatible metrics

Recommended metrics include:

```text
rpg_commands_total
rpg_command_latency_seconds
rpg_events_total
rpg_event_persist_latency_seconds
rpg_active_campaigns
rpg_loaded_entities
rpg_scheduler_tasks
rpg_scheduler_lag_seconds
rpg_rules_executions_total
rpg_rules_execution_steps
rpg_rules_execution_seconds
rpg_ai_decisions_total
rpg_ai_decision_seconds
rpg_websocket_clients
rpg_websocket_queue_depth
rpg_database_latency_seconds
rpg_worker_campaigns
rpg_lease_conflicts_total
rpg_lease_renew_failures_total
rpg_shard_transfer_total
rpg_shard_transfer_failures_total
rpg_replay_hash_mismatch_total
```

## Trace shape

```text
HTTP request
  → identity / authorization
  → command dispatch
  → rules resolution
  → spatial validation
  → state mutation
  → event append
  → quest/living consumers
  → knowledge projection
  → websocket fanout
```

## Structured logging

Logs should consistently include correlation/causation IDs, campaign ID, actor ID, command ID, event sequence, worker/shard identity, and deterministic replay context when available.

## Acceptance criteria

- [ ] OpenTelemetry-compatible tracing hooks;
- [ ] Prometheus/OpenMetrics-compatible metrics export;
- [ ] structured JSON logs;
- [ ] correlation and causation propagation;
- [ ] campaign/worker/shard health endpoints;
- [ ] replay hash mismatch diagnostic path;
- [ ] scheduler lag and WebSocket backpressure diagnostics.

---

# v4.5 — Scale + Performance

Use the existing Simulation Lab and dedicated benchmarks to measure the engine itself.

## Standard workloads

| Scenario | Target |
| --- | ---: |
| Small encounter | 10 actors |
| Large encounter | 100 actors |
| Settlement | 1,000 actors |
| Regional simulation | 10,000 actors |
| Scheduler stress | 100,000 scheduled events |
| Replay | 1,000,000 persisted events |
| Content registry | 10,000 packs/releases |
| Knowledge projection | 1,000 actors × viewers |
| WebSocket fanout | 100–1,000 clients |
| Distributed handoff | thousands of migrations |

## Measurements

- commands/sec;
- events/sec;
- scheduler lag;
- database writes/sec;
- replay throughput;
- snapshot cost;
- knowledge-filtering cost;
- memory/entity;
- AI planning cost;
- pathfinding cost;
- WebSocket fanout latency;
- cross-shard transfer latency/failure rate.

## Acceptance criteria

- [ ] reproducible benchmark harness;
- [ ] benchmark fixtures versioned with the repository;
- [ ] CPU, memory, database, scheduler, AI, spatial, and networking profiles;
- [ ] performance baselines published in CI artifacts;
- [ ] regression thresholds for critical workloads;
- [ ] profiling guidance for local and production deployments.

---

# v4.6 — Player Experience

The next major UX surface should be a dedicated player client rather than another editor.

## `/player`

A player should be able to play without navigating GM-oriented operational surfaces.

```text
┌──────────────────────────────────────────┐
│ Character           Scene          Clock │
├────────────┬─────────────────────────────┤
│ Character  │                             │
│ HP         │           MAP               │
│ AC         │                             │
│ Effects    │                             │
│ Resources  │                             │
├────────────┼─────────────────────────────┤
│ Actions    │ Event / narrative timeline  │
│ Attack     │                             │
│ Spell      │                             │
│ Item       │                             │
│ Interact   │                             │
└────────────┴─────────────────────────────┘
```

## Acceptance criteria

- [ ] dedicated `/player` route;
- [ ] mobile-friendly responsive layout;
- [ ] knowledge-scoped state only;
- [ ] character/resource/effect summary;
- [ ] authoritative action palette;
- [ ] tactical and narrative views converge into one play flow;
- [ ] reconnect/resume UX is automatic and state-safe;
- [ ] no GM-only diagnostics exposed to players.

---

# v4.7 — Campaign Import / Export

Campaigns need a durable portability and backup lifecycle independent from reusable content packs.

## Capabilities

- portable campaign archive format;
- schema/version metadata;
- export validation;
- backup and restore;
- campaign cloning;
- archival state;
- optional redacted/player-safe exports;
- migration on import;
- integrity hashes;
- content dependency lock capture.

## Acceptance criteria

- [ ] campaign archive schema;
- [ ] deterministic export manifest and integrity hash;
- [ ] import validation and migration path;
- [ ] backup/restore integration tests;
- [ ] campaign clone operation;
- [ ] archive/read-only mode;
- [ ] dependency lock/content provenance included.

---

# v4.8 — Content Compatibility

Every durable serialized format should gain explicit schema evolution and migration support before future engine versions accumulate incompatible state.

## Schema-versioned durable formats

Apply explicit schema versions and migration registries to:

- ContentPack;
- campaign state;
- snapshots;
- event payloads;
- NPC profiles;
- character state;
- executable rule graphs;
- Creator projects;
- distribution metadata;
- runtime bindings;
- campaign archives.

## Migration model

```text
serialized v1
      ↓
MigrationRegistry
      ↓
v2
      ↓
v3
      ↓
current
```

## Protocol contracts

Define transport-independent envelopes such as:

```text
CommandEnvelope
EventEnvelope
SnapshotEnvelope
DeltaEnvelope
ErrorEnvelope
CapabilityEnvelope
```

with common metadata:

```text
protocol_version
schema_version
engine_version
campaign_id
correlation_id
causation_id
command_id
sequence
timestamp
```

## Acceptance criteria

- [ ] explicit schema version on durable formats;
- [ ] migration registry and chained migrations;
- [ ] backward-compatibility test fixtures;
- [ ] protocol envelope models;
- [ ] capability/deprecation negotiation;
- [ ] compatibility matrix documented and tested;
- [ ] old campaign/content fixtures remain loadable across supported migrations.

---

# v4.9 — Production Multiplayer

Build production multiplayer behavior on top of the existing authoritative session model.

## Capabilities

- robust reconnection/resume;
- command acknowledgements;
- latency-aware UX without client authority;
- bounded outbound queues and backpressure;
- presence and session heartbeat state;
- rate limiting;
- duplicate command handling;
- disconnect/reconnect race handling;
- multi-worker failover testing;
- WebSocket slow-consumer handling;
- authorization-aware reconnect tickets.

## Acceptance criteria

- [ ] explicit command acknowledgement protocol;
- [ ] reconnect from last confirmed event sequence;
- [ ] bounded WebSocket queues;
- [ ] slow-consumer policy;
- [ ] presence/heartbeat model;
- [ ] rate limiting for commands and joins;
- [ ] deterministic duplicate-command behavior;
- [ ] failover test with worker ownership transfer;
- [ ] multiplayer soak tests.

---

# v5.0 — Production RPG Platform

v5.0 is the production-readiness convergence milestone, not another independent feature bundle.

It should certify that the platform has:

- stable authoritative runtime behavior;
- end-to-end gameplay certification;
- deterministic replay guarantees;
- property/invariant coverage;
- hardened identity and authorization;
- production observability;
- benchmarked scale envelopes;
- a dedicated player experience;
- campaign portability and backup/restore;
- durable schema migration guarantees;
- protocol compatibility contracts;
- production multiplayer and reconnect behavior;
- validated SQLite/PostgreSQL deployment paths;
- multi-worker and persistent-world failure/recovery tests.

## v5.0 release gate

A v5.0 release should require a documented certification run covering:

```text
create campaign
→ install content
→ create actors
→ play complete scenario
→ persist
→ restart
→ reconnect
→ replay
→ migrate/export/import
→ multi-worker failover
→ verify final authoritative hashes
```

---

# Cross-cutting engineering initiatives

These initiatives support multiple milestones and should be scheduled alongside them rather than deferred to one version.

## Stronger CI gates

Recommended jobs/checks:

```text
ruff check
ruff format --check
mypy or pyright
pytest
coverage threshold
Hypothesis/property tests
pip-audit
bandit
package build
wheel install smoke test
Docker build
OpenAPI schema generation check
ContentPack/schema tests
migration tests
SQLite tests
PostgreSQL integration tests
WebSocket tests
replay/hash validation
deterministic repeated-run tests
```

Suggested job split:

```text
lint
typing
unit
integration
determinism
security
packaging
performance-smoke
```

Run the supported Python matrix on Linux, with PostgreSQL service-container integration where needed.

## API maintainability

Prevent API composition modules from becoming monoliths. Move toward explicit dependency/router/schema boundaries:

```text
api/
    dependencies/
        auth.py
        campaigns.py
        services.py

    routers/
        campaigns.py
        actors.py
        encounters.py
        scenes.py
        rules.py
        creator.py
        content.py
        knowledge.py
        multiplayer.py
        replay.py
        analytics.py
        admin.py

    schemas/
        campaign.py
        actor.py
        rules.py
        multiplayer.py

    app_factory.py
```

Keep application entrypoints focused on composition rather than business logic.

## Distributed-world rollout gate

Do not treat the v3.0 primitives as proof of production MMO operation. Validate deployment complexity in stages:

```text
single process
    ↓
multi-worker
    ↓
multi-worker failover
    ↓
multi-shard
    ↓
cross-shard recovery
```

Each step should have integration and failure-recovery tests before the next becomes a production claim.

---

# Priority

If only one milestone is implemented next, choose **v4.1 End-to-End Campaign Runtime + Campaign Certification Suite**.

The engine already has most individual capabilities. The highest-value improvement is proving that they form one coherent, deterministic, restartable, replayable, playable campaign runtime.