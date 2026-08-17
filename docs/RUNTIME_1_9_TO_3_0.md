# Runtime architecture: v1.9 → v3.0

This document describes the world-platform layers introduced after the v1.8 Creator Studio milestone. The design keeps one invariant from the earliest engine releases: **authoritative game truth changes only through deterministic engine services and validated commands**.

## Layering

```text
Creator Studio / SRD catalog / ContentPack
                 │
                 ▼
       v1.9 RuleCompiler
                 │
        ExecutableRuleGraph
                 │
                 ▼
          RulesRuntime
      effects / rolls / reactions
                 │
                 ▼
        WorldPlatformEngine
   ┌─────────────┼──────────────────┐
   │             │                  │
Campaign      Knowledge          AI Director
Orchestrator  Authority          proposals
   │             │                  │
   └─────────────┼──────────────────┘
                 ▼
        RuntimeSynchronizer
       browser / Godot / remote
                 │
                 ▼
 SQLite / PostgreSQL / workers
                 │
                 ▼
     persistent shard metadata
```

`WorldPlatformEngine` subclasses `AdvancedGameEngine`. Existing `GameEngine` and `AdvancedGameEngine` consumers remain available; the normal v3 platform server selects the world profile while `advanced=False` selects the compatibility profile.

## v1.9: Executable Content Compiler + Rules Graph

### Why a compiler instead of scripts?

Creator-authored rules must be replayable, inspectable, safe to host, and deterministic across clients and workers. The engine therefore does **not** execute arbitrary Python, Lua, JavaScript, `eval`, or `exec` from content packs.

Authored content is represented as a bounded `ExecutableRuleGraph` made from known `RuleOp` values. The compiler rejects unsupported operations and unsafe state paths before the graph can execute.

### Core types

```text
RuleDocument.graph
  ↓
RuleCompiler
  ↓
ExecutableRuleGraph
├── id / name
├── entry
├── nodes
├── effects
├── capabilities
├── action_time_seconds
├── provenance
└── graph_hash
```

The graph hash is SHA-256 over canonical JSON with the hash field blanked. `RuleExecutor` recomputes and verifies that hash before every execution.

### Operation set

The initial IR exposes:

- `roll`
- `damage`
- `heal`
- `set`
- `increment`
- `consume_resource`
- `restore_resource`
- `apply_effect`
- `open_reaction`
- `if`
- `emit`
- `noop`
- `stop`

Each operation uses typed/validated arguments. State writes are limited to:

```text
state.flags.*
actor.components.*
target.components.*
```

Core engine objects, filesystem paths, process state, network access, imports, and arbitrary object attributes are not exposed to authored rules.

### Execution budgets

The default compiler limits a graph to 512 nodes and 128 effect definitions. Runtime execution stops after 2,048 deterministic node steps. These limits prevent malformed cyclic content from turning into unbounded server work.

### Provenance

Compiled graphs preserve:

- pack ID and version;
- source object ID;
- source revision;
- source document/page when supplied;
- compiler version;
- graph hash.

This metadata can be surfaced in replay/debugging tools and used to prove which rule revision produced an outcome.

### Creator Studio

The Rules section now includes an executable graph editor. It provides a visual SVG graph, entry-node selection, operation selection, success/failure/normal edges, typed key/value arguments, action time, capability tags, compile validation, and graph-hash feedback.

Saving the visual graph calls the actual `RuleCompiler`. Invalid graphs are rejected before the Studio revision is persisted.

## v2.0: Campaign Orchestrator

`CampaignOrchestrator` gives campaigns a single authoritative scene lifecycle instead of allowing combat, dialogue, travel, maps, and quests to independently decide what is currently active.

Scene kinds include exploration, encounter, dialogue, travel, downtime, settlement, dungeon, and custom.

Scene state transitions are explicit:

```text
UNLOADED → LOADING → ACTIVE → SUSPENDED
                     │          │
                     └────→ RESOLVED → ARCHIVED
```

Invalid transitions are rejected. Exclusive scene activation can suspend another active scene. Scene runtime state is mirrored into `CampaignState.metadata`, so saves, event-sourced snapshots, workers, and reconnects preserve it automatically.

The orchestrator also computes an entity streaming set from active scenes and their declared preload scenes. This is the first step toward large campaigns where inactive areas do not need to remain actively simulated or synchronized.

## v2.1: Simulation Lab

`SimulationLab` is a deterministic experiment runner rather than a second game engine. A scenario supplies an async `run_once(seed)` function that returns a `SimulationSample`.

The Lab supplies:

- deterministic seed matrices;
- bounded concurrency;
- outcome counts/rates;
- custom numeric metrics;
- aggregate event counts;
- min/max/mean/median/population-stdev;
- p10 and p90;
- report-to-report metric and outcome deltas.

This makes balance tests, encounter sweeps, AI-regression experiments, and content validation reproducible in CI or offline tooling.

## v2.2: AI Director

Individual v1.5 actors plan their own actions. `AIDirector` operates one level higher and observes campaign-scale pacing signals.

It produces ranked `DirectorProposal` objects for:

- encounter opportunities;
- recovery/downtime windows;
- pacing/decompression;
- quest hooks;
- faction motion;
- background world events.

A proposal includes its utility, payload, reasons, and tags. **The Director does not mutate authoritative state.** A host policy, GM, or future command layer must explicitly accept a proposal and translate it into ordinary content/state commands.

This boundary is intentional: generative providers may help with ideas or language later without becoming an authority over dice, inventory, movement, damage, or state.

## v2.3: Perception + Knowledge Authority

World truth and actor knowledge are separate concepts.

```text
CampaignState (truth)
       │
       ▼
PerceptionSystem
       │
       ▼
KnowledgeAuthority
       │
       ▼
KnowledgeView
       │
       ├── actor AI
       └── player/runtime client
```

Each actor can store:

- known entity IDs;
- last observation times;
- remembered entity snapshots;
- facts with value/confidence/source/tags/expiry.

A crucial rule is that **stale knowledge is a snapshot, not a live reference**. If an actor saw a creature at 10 HP and then lost sight of it, its knowledge view does not silently update when that hidden creature heals or moves.

Non-self observed entities expose only explicitly public component groups. Private components are removed from remembered snapshots.

### Network enforcement

In the v3 world profile, the old omniscient campaign GET, event-history GET, and WebSocket routes are replaced with knowledge-scoped versions.

- campaign owners retain full authoritative views;
- player clients receive the union of views for actors they own;
- unowned hidden entities do not appear;
- raw events are delivered only if their actor/target is known/owned or the event is explicitly marked public;
- spectators without owned actors receive a public campaign shell instead of full truth;
- missing client identity is rejected for these read streams.

The legacy compatibility server remains available separately.

## v2.4: Visual Runtime SDK

`RuntimeSynchronizer` provides a transport-neutral state protocol for browser, Godot, and remote clients.

A `RuntimeSnapshot` contains:

- sequence;
- campaign ID;
- simulation time;
- active map;
- entity projection;
- knowledge facts;
- optional visual bindings;
- canonical snapshot hash.

`VisualBinding` maps an entity to presentation resources such as scene, sprite, model, and animation-set identifiers without moving those presentation concerns into the simulation engine.

`RuntimeDelta` contains deterministic add/replace/remove operations plus base and target hashes. Applying a delta verifies both hashes, preventing a client from silently applying a delta to the wrong state version.

For player clients, snapshots should be created from `KnowledgeView`; owners/debug tools may create them from full `CampaignState`.

## v2.5: Content Distribution Platform

Content releases are independently versioned from engine releases.

`PackageRelease` records:

- package ID/version;
- content hash;
- engine-version requirement;
- package dependencies;
- optional signature;
- metadata.

`ContentDistributionIndex` resolves dependency graphs deterministically, rejects cycles, selects compatible versions, returns a topological install order, and computes a SHA-256 lock hash.

`ContentDistributionService` persists releases and dependency locks through the common JSON-store contract, so both SQLite and PostgreSQL deployments keep the same format.

Creator Studio projects can be published into both the marketplace and distribution registry. The distribution API can list releases, resolve dependencies, and persist named locks for campaigns or deployments.

The built-in HMAC-SHA256 signer is intended for private registries and deterministic tests. Public registries can implement an asymmetric signer behind the same sign/verify metadata shape.

## v3.0: Massively Persistent Worlds foundation

v3.0 establishes deterministic primitives for partitioning a world across simulation processes. It does not pretend a single Python process has become a planet-scale MMO server; transport, service discovery, operations, and capacity engineering remain deployment concerns.

### Shard directory

A `WorldShard` reports:

- ID;
- status;
- capacity/load;
- explicit region affinities;
- heartbeat timestamp;
- metadata.

`ShardDirectory.route(region)` uses explicit affinity when available and otherwise stable SHA-256 rendezvous hashing. Adding/removing shards therefore minimizes unnecessary reassignment compared with modulo hashing.

### Entity handoff

Cross-shard entity movement uses a two-phase handoff:

```text
PREPARED
   │ destination validates canonical state hash
   ▼
ACCEPTED
   │ source/destination commit handoff
   ▼
COMMITTED
```

A transfer can be aborted before commit. Once committed, the coordinator records an exactly-once entity transfer guard. Restoring an entity re-verifies the canonical payload hash.

### Cross-shard messages

`CrossShardMessage` carries a Lamport sequence and optional idempotency key. Receivers advance their Lamport clock and reject a duplicate idempotency key.

### Persistence

`PersistentWorldRegistry` stores:

- shard registrations/heartbeats;
- region assignments;
- entity transfers;
- cross-shard messages.

It uses `put_json/list_json`, which are implemented by both development SQLite and production PostgreSQL stores.

This works alongside the v1.7 worker registry, campaign leases, reconnect tickets, and PostgreSQL persistence. Campaign leases still protect single-campaign simulation ownership; world shards add a higher-level region/entity partitioning layer.

## Security and authority summary

The v3 platform uses these boundaries:

```text
Content author
   │ bounded graph only
   ▼
RuleCompiler
   │ verified IR
   ▼
RulesRuntime / WorldPlatformEngine
   │ authoritative truth
   ▼
Perception + Knowledge Authority
   │ redacted projection
   ▼
RuntimeSynchronizer
   │ hash-verified client state
   ▼
Browser / Godot / remote client
```

A client cannot become authoritative by editing its runtime snapshot. An authored content pack cannot gain server code execution by adding a rule. An AI Director cannot directly change campaign truth. A hidden entity is not exposed merely because the server knows it exists.

## Compatibility

- `GameEngine`: original compatibility-first engine.
- `AdvancedGameEngine`: v1.2-v1.8 integrated runtime.
- `WorldPlatformEngine`: v1.9-v3.0 integrated world profile.
- `/api/v1` remains the HTTP/WebSocket namespace.
- `engine_profile=advanced` remains stable in health responses; `platform_profile=world` identifies the v3 implementation.
- SQLite remains suitable for local/single-process development.
- PostgreSQL remains the production persistence/lease backend.
