# v1.2–v1.5 architecture

This document describes the architectural layers introduced after the SRD 5.2.1 foundation. They are deliberately additive: existing CLI, browser, TUI, Godot, multiplayer, persistence, and content-pack callers can keep using the existing `GameEngine` command/event surface while newer integrations opt into the typed runtime, event-sourced journal, spatial authority, and intelligent-actor APIs.

## Design goals

The four milestones share the same invariants:

1. The authoritative server is the only source of simulation truth.
2. Rulesets interpret mechanics without presentation code knowing the active ruleset.
3. AI emits normal validated commands instead of mutating state directly.
4. Spatial decisions are validated by server-side geometry/navigation state.
5. Event-sourcing metadata is deterministic and never blocks the asyncio event loop.
6. Existing command/event and renderer contracts remain compatible while the internals become more modular.

## v1.2 — Rules Runtime + Effect Pipeline

`dnd_rpg_engine.rules.runtime.RulesRuntime` is the rules interpretation boundary. `CombatSystem` remains the compatibility facade used by `GameEngine`, but attack, defense, and damage calculations are delegated to the active runtime.

A rules runtime provides:

- typed `ResolutionContext`, `RollRequest`, `RollOutcome`, `AttackOutcome`, `DamagePacket`, and `DamageOutcome` models;
- explainable `ModifierTrace` data;
- ruleset capability declarations through `RuleCapability`;
- deterministic effect processing through `EffectPipeline`;
- reaction opportunities with optional timeout windows;
- per-actor `ActionEconomy` state;
- overridable proficiency, defense, damage, attack, zero-HP, rest, and other rules behavior.

Rulesets register runtime factories by ruleset ID. When `CombatSystem.rules` changes, the facade creates the matching runtime while preserving current effect, action-economy, and reaction state.

### Effects and modifiers

`EffectPipeline` separates reusable effect definitions from active effect instances. Definitions declare trigger points, modifiers, operations, stack limits, durations, and tags. Instances carry source/target identity, stack count, expiry time, and metadata.

Supported modifier kinds are:

- flat addition/subtraction;
- multiplier;
- minimum clamp;
- maximum clamp;
- advantage source;
- disadvantage source.

Advantage and disadvantage sources are retained in the trace even when they cancel. That gives frontends and narrators an explanation of *why* a normal roll occurred.

### SRD runtime specialization

`dnd_rpg_engine.rulesets.srd_5_2_1.runtime.SRD521RulesRuntime` owns SRD-specific mechanics that should not become assumptions in the generic runtime. The first specialization moves proficiency behavior and typed zero-HP/death-save transitions behind that boundary. Existing engine compatibility behavior remains available while callers migrate incrementally.

## v1.3 — Deterministic Event Sourcing

`dnd_rpg_engine.core.event_sourcing` adds a deterministic journal around the existing engine rather than replacing it abruptly.

The journal uses canonical JSON and deterministic JSON-pointer patches. Each journal entry records:

- monotonically increasing sequence;
- command ID;
- state patch;
- resulting authoritative state hash;
- previous journal-entry hash;
- its own SHA-256 entry hash.

This creates a verifiable hash chain.

`EventJournal` supports:

- replay to the head or an arbitrary sequence;
- rewind to an earlier state;
- creation of a child branch from any sequence;
- complete journal verification;
- state-hash verification after every replayed patch.

`EventSourcedEngine` wraps normal asynchronous `GameEngine.dispatch()` calls. It captures the before/after authoritative state, appends a journal entry, records command receipts, and persists journal entries through the existing async `SQLiteStore.put_json()` boundary when storage is configured.

### Command idempotency

Every `GameCommand` already carries `command_id`. `CommandLedger` records the authoritative receipt for each processed ID. Re-delivery of the same command ID returns the previous receipt as a duplicate rather than mutating state again.

This is useful for reconnecting clients, retrying HTTP/WebSocket sends, and eventually implementing replicated or queued command delivery.

### State verification

The state hash intentionally ignores `command_ledger` and `event_source_head` metadata. Those fields describe the journal itself; including them would make recording an entry alter the gameplay-state hash that the entry is intended to verify.

## v1.4 — Spatial Authority

`dnd_rpg_engine.spatial.SpatialAuthority` provides one registry for several spatial models.

### Graph spaces

`GraphSpace` supports:

- named nodes;
- weighted directed/bidirectional edges;
- optional node capacity;
- authoritative occupancy;
- Dijkstra routing;
- movement-budget validation.

This is suitable for text adventures, world maps, room graphs, travel networks, and strategic maps.

### Grid spaces

`GridSpace` supports:

- bounded square grids;
- cardinal and optional diagonal movement;
- corner-cut prevention;
- per-cell movement cost;
- blocked movement and blocked line-of-sight flags;
- entity occupancy;
- A* routing;
- movement-budget validation;
- Bresenham line-of-sight;
- cover classification.

This is suitable for tactical maps and deterministic server-side combat boards.

### Continuous 2D/3D spaces

`ContinuousSpace` supports:

- 2D or 3D bounds;
- entity collision radii;
- axis-aligned obstacle volumes;
- authoritative destination collision checks;
- movement-segment obstruction checks;
- line-of-sight using segment/AABB intersection;
- cover classification;
- maximum-distance validation.

Godot or another renderer can continue to interpolate presentation locally while the server decides whether the requested movement is legal.

## v1.5 — Intelligent Living Actors

`dnd_rpg_engine.ai.intelligence` adds a deterministic AI decision layer that operates only on authoritative observations and produces ordinary `GameCommand` objects.

The flow is:

```text
Campaign state
    ↓
PerceptionSystem
    ↓
PerceptionSnapshot
    ↓
Goals + personality + schedule + memories
    ↓
TacticalPlanner / UtilityScorer
    ↓
ActionCandidate ranking
    ↓
validated GameCommand
    ↓
normal GameEngine dispatch
```

### Perception

`PerceptionSystem` builds bounded snapshots containing visible nearby entities, distance, hostility, health fraction, nearby ally/hostile counts, schedule context, and recalled memories. A caller can provide an authoritative line-of-sight function from the spatial layer.

### Goals and utility AI

`Goal` objects assign weights and optional targets/tags. `UtilityScorer` combines candidate factors, matching goals, and personality tag biases. `TacticalPlanner` currently generates deterministic candidates for attacking, advancing, fleeing, following schedule intent, and waiting.

The output includes reasons and per-factor scores so AI decisions can be inspected in a UI or log.

### Behavior trees

The module includes small composable behavior-tree primitives:

- `ConditionNode`;
- `ActionNode`;
- `SequenceNode`;
- `SelectorNode`;
- `BehaviorStatus` and `BehaviorContext`.

These can gate or orchestrate utility planning without giving scripts direct access to authoritative mutation.

### Persistent memories

`PersistentActorMemory` stores bounded memory records in the entity's `agent_memory` component. That means existing campaign persistence, state snapshots, multiplayer state transfer, and event-sourced state patches naturally carry the memories without a second database connection or blocking I/O path.

## Layering

The intended dependency direction is:

```text
clients / renderers
        │
        ▼
GameCommand / GameEvent
        │
        ▼
GameEngine orchestration
        │
        ├── RulesRuntime / EffectPipeline
        ├── EventSourcedEngine / EventJournal
        ├── SpatialAuthority
        └── IntelligentActorController
                 │
                 └── emits GameCommand only
```

The new layers are usable independently. A lightweight text game can use rules + event sourcing without continuous geometry. A Godot game can use spatial authority without intelligent actors. A custom ruleset can register a runtime without changing the browser, TUI, multiplayer, or persistence layers.

## Testing

The repository includes dedicated regression suites for:

- runtime modifier/effect/reaction behavior and SRD runtime selection;
- deterministic patch replay, rewind, branching, command idempotency, and live-state verification;
- graph/grid/continuous spatial authority;
- perception, utility decisions, survival behavior, and persistent actor memories.

CI compiles the package and runs the full suite on Python 3.12, 3.13, and 3.14.
