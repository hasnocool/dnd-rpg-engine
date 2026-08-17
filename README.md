# dnd-rpg-engine

A headless, deterministic fantasy RPG **world platform** that can power turn-based, timed-turn, real-time, real-time-with-pause, hybrid, text, TUI, browser, 2D, 3D, multiplayer, simulation-lab, and distributed-world experiences from the same authoritative state model.

The repository intentionally separates rules/simulation from presentation. The generic engine does **not** bundle proprietary rulebooks or setting material. It includes an opt-in SRD 5.2.1 foundation built from the Creative-Commons System Reference Document: compact structured mechanics and provenance are bundled while long-form source prose remains in the official SRD. Content outside the SRD remains out of scope unless separately licensed.

See [`docs/SRD_5_2_1.md`](docs/SRD_5_2_1.md) and [`NOTICE-SRD-5.2.md`](NOTICE-SRD-5.2.md).

## Current platform: 3.0.0

The implemented roadmap now runs from the original simulation kernel through executable authored rules and persistent-world foundations.

| Milestone | Implemented |
| --- | --- |
| v1.2 Rules Runtime | typed outcomes, modifiers, effects, triggers, reactions, action economy |
| v1.3 Event Sourcing | deterministic patches, hash-chain journal, replay, rewind, branching, idempotency |
| v1.4 Spatial Authority | graph/grid/continuous spaces, collision, occupancy, terrain, pathfinding, LOS, cover |
| v1.5 Intelligent Actors | perception, goals, utility AI, behavior trees, tactical planning, schedules, persistent memories |
| v1.6 Character Lifecycle | builder, multiclass progression, XP/milestones, resources, rests, equipment |
| v1.7 Production Hosting | PostgreSQL, migrations, workers, leases, rendezvous routing, reconnect/resume |
| v1.8 Creator Studio | persistent projects, revisions, visual maps, typed content editors, validation/export/publish |
| **v1.9 Executable Rules** | bounded rule compiler, executable graphs, provenance, traces, visual graph editor |
| **v2.0 Campaign Orchestrator** | authoritative scene lifecycle and active-world streaming sets |
| **v2.1 Simulation Lab** | deterministic seed matrices, outcome statistics, balance/regression comparisons |
| **v2.2 AI Director** | campaign-scale pacing/encounter/quest/faction proposals without direct mutation |
| **v2.3 Knowledge Authority** | per-actor memory/facts, stale snapshots, knowledge-scoped HTTP/WebSocket views |
| **v2.4 Visual Runtime SDK** | canonical snapshots, visual bindings, hash-verified client deltas |
| **v2.5 Content Distribution** | versions, dependencies, engine constraints, signatures, locks, persistent registry |
| **v3.0 Persistent Worlds** | shards, region routing, two-phase entity handoff, Lamport messages, persistent metadata |

The earlier v0.1-v1.1 milestones—core simulation, tactical/adventure/living-world systems, frontends, Godot adapters, AI GM, multiplayer, creator platform, hosted campaigns, and SRD foundation—remain intact. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the complete checklist.

## Three engine profiles

```text
GameEngine
  compatibility-first simulation
       │
       ▼
AdvancedGameEngine
  rules runtime + event sourcing + spatial authority
  + intelligent actors + character lifecycle
       │
       ▼
WorldPlatformEngine
  executable content + campaign orchestration
  + knowledge authority + AI Director + runtime sync
```

`rpg-engine serve` and `rpg-engine-host` use `WorldPlatformEngine` by default. The compatibility profile is still available to callers that need the older behavior.

## Executable rules without arbitrary scripting

Creator-authored rules compile into an `ExecutableRuleGraph` instead of running embedded Python/Lua/JavaScript.

```text
Creator Studio / ContentPack / structured catalog
                      │
                      ▼
                  RuleCompiler
                      │
              validated graph hash
                      │
                      ▼
                  RuleExecutor
                      │
                      ▼
                  RulesRuntime
               rolls/effects/reactions
                      │
                      ▼
              authoritative state
```

The initial rule IR supports bounded operations for rolls, damage, healing, resources, safe state fields, effects, reactions, branching, emitted domain information, and termination. The compiler enforces node/effect limits, cross-reference validation, an allowlist of writable paths, and a deterministic execution-step budget. There is no content-level `eval`, `exec`, filesystem, process, import, or network escape hatch.

Every compiled graph carries source provenance and a canonical SHA-256 graph hash. Runtime execution produces node-by-node traces suitable for debugging, replay, explanations, and Creator Studio validation.

The Rules editor at `/creator` includes a visual executable graph canvas with entry nodes, operation nodes, normal/success/failure links, typed arguments, capability tags, action duration, compile validation, and graph-hash feedback.

## Campaign orchestration

`CampaignOrchestrator` coordinates exploration, encounters, dialogue, travel, downtime, settlements, dungeons, and custom scenes through one lifecycle:

```text
UNLOADED → LOADING → ACTIVE → SUSPENDED
                     │          │
                     └────→ RESOLVED → ARCHIVED
```

Scene state lives in campaign metadata so snapshots, replay, workers, and reconnects preserve it. Active scenes plus declared preload scenes determine which entities belong in the current streamed world projection.

## Simulation Lab

The deterministic architecture can run the same scenario over a seed matrix and compare outcomes rather than relying only on manual playtesting.

`SimulationLab` provides bounded concurrent execution, outcome rates, event counts, min/max/mean/median/population standard deviation, p10/p90, retained samples, and report-to-report deltas.

Typical uses include encounter balance, AI policy regression, resource depletion, rule edge cases, economy tuning, and content validation.

## AI authority model

There are three distinct AI roles:

- individual actors perceive and emit ordinary validated `GameCommand`s;
- the AI Game Master narrates authoritative events but cannot mutate truth directly;
- `AIDirector` observes campaign-scale pacing and returns ranked proposals for encounters, recovery, quests, factions, world events, and decompression.

The Director is intentionally proposal-only. A host policy or GM must translate an accepted proposal into ordinary authoritative actions.

## Knowledge and client visibility

World truth is not the same thing as actor knowledge.

```text
CampaignState truth
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
      ▼
RuntimeSynchronizer / client
```

Actors retain known entities, observation timestamps, remembered snapshots, and facts with confidence/source/tags/expiry. Losing sight of an entity does **not** leave a live reference to its current hidden HP/location; stale knowledge returns the remembered snapshot.

In the v3 world profile, campaign reads, event history, and WebSocket streams are knowledge-scoped:

- owners can request authoritative/omniscient state;
- players see the union of knowledge for actors they own;
- hidden entities and private components are omitted;
- events are delivered when their actor/target is known/owned or explicitly public;
- spectators without owned actors receive a public shell rather than hidden truth.

## Visual Runtime SDK

`RuntimeSynchronizer` creates canonical state frames for browser, Godot, or other clients. Frames can originate from full owner state or a redacted `KnowledgeView`.

`VisualBinding` maps entity IDs to presentation resources such as a scene, sprite, model, or animation set. `RuntimeDelta` carries deterministic add/replace/remove operations plus base and target hashes; applying a delta verifies both hashes.

Rendering remains presentation-owned. The Python server remains authoritative for time, AI, movement, rules, resources, inventory, state, and visibility.

## Content distribution

Content packages can evolve independently from the engine.

The distribution layer provides:

- semantic-version release metadata and constraints;
- engine-version requirements;
- dependency graph resolution and cycle detection;
- deterministic topological install order;
- content hashes and dependency lock hashes;
- signed release metadata (built-in HMAC-SHA256 for private registries/tests; asymmetric signers can use the same metadata shape);
- update planning;
- persistent releases/locks in SQLite or PostgreSQL;
- REST endpoints under `/api/v1/distribution`;
- Creator Studio publication into both marketplace and distribution registry.

## Persistent-world foundations

v3.0 adds deterministic primitives for partitioning a large world across simulation processes.

A `ShardDirectory` tracks shard status, capacity/load, heartbeats, and region affinity. Routing uses stable SHA-256 rendezvous hashing so adding/removing shards minimizes unnecessary reassignment.

Entity movement between shards uses a hash-verified two-phase handoff:

```text
PREPARED → ACCEPTED → COMMITTED
    └──────────────→ ABORTED
```

Cross-shard messages carry Lamport ordering and idempotency keys. `PersistentWorldRegistry` stores shards, region assignments, transfers, and messages through the same JSON persistence interface supported by SQLite and PostgreSQL.

This is a **distributed-world foundation**, not a claim that one process automatically becomes an MMO cluster. Production transport, service discovery, observability, infrastructure capacity, and operations still belong to the deployment environment. The engine now supplies the deterministic routing/authority/persistence contracts those systems can build around.

## Time is first-class

The scheduler supports:

- `turn_based`;
- `timed_turn_based`;
- `real_time`;
- `real_time_with_pause`;
- `hybrid`.

The same timeline handles actor readiness, delayed actions, spell completion, condition ticks, world events, NPC schedules, reaction windows, and idle pressure.

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[all,dev]'
pytest
rpg-engine serve --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000/` — browser client;
- `/creator` — Creator Studio and visual rule graphs;
- `/docs` — OpenAPI.

Other local clients:

```bash
rpg-engine demo --mode hybrid --seconds 20 --timeout 5
rpg-engine play --mode hybrid --timeout 10
rpg-engine-tui
```

SRD provenance/local reference cache:

```bash
rpg-engine srd-info
rpg-engine fetch-srd --output .cache/srd/SRD_CC_v5.2.1.pdf
```

## Production hosting

```bash
pip install -e '.[hosting]'

RPG_DATABASE_URL='postgresql://user:pass@db.example/rpg' rpg-engine-host

RPG_DATABASE_URL='postgresql://user:pass@db.example/rpg' \
RPG_WORKER_CAPACITY=32 \
rpg-engine-worker
```

Workers use stable preferred placement plus PostgreSQL leases as the authoritative single-campaign simulator guard. Reconnect tickets are opaque, stored by hash, rotate on successful resume, and carry event checkpoints for missed-event replay.

## API notes

The package release is `3.0.0`; the public transport namespace remains `/api/v1`.

Create a campaign:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/campaigns \
  -H 'content-type: application/json' \
  -d '{"name":"My Campaign","owner_id":"local","seed":42,"time_mode":"hybrid"}'
```

Authenticated world-profile reads use `X-RPG-Client-ID`. WebSocket clients connect with the same campaign client identity:

```text
ws://127.0.0.1:8000/api/v1/campaigns/{campaign_id}/ws?client_id=CLIENT_ID
```

Additional APIs include:

```text
/api/v1/campaigns/{campaign_id}/characters
/api/v1/campaigns/{campaign_id}/rules/compile
/api/v1/campaigns/{campaign_id}/scenes
/api/v1/campaigns/{campaign_id}/director/proposals
/api/v1/campaigns/{campaign_id}/runtime
/api/v1/studio
/api/v1/distribution
```

Clients submit commands and consume authoritative results; they never calculate trusted outcomes locally.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/TIMING.md`](docs/TIMING.md)
- [`docs/RUNTIME_1_2_TO_1_5.md`](docs/RUNTIME_1_2_TO_1_5.md)
- [`docs/RUNTIME_1_6_TO_1_8.md`](docs/RUNTIME_1_6_TO_1_8.md)
- [`docs/RUNTIME_1_9_TO_3_0.md`](docs/RUNTIME_1_9_TO_3_0.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Development

```bash
make test
make coverage
make demo
make serve
```

CI tests Python 3.12, 3.13, and 3.14, compiles the package, and runs the full test suite.

## License

Engine code is MIT licensed. Third-party campaigns/rules can carry their own license through mod manifests. The bundled SRD 5.2.1 integration is separately attributed under CC BY 4.0; see `NOTICE-SRD-5.2.md`.
