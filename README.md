# dnd-rpg-engine

A headless, deterministic fantasy RPG **world platform** that can power turn-based, timed-turn, real-time, real-time-with-pause, hybrid, text, TUI, browser, 2D, 3D, multiplayer, simulation-lab, and distributed-world experiences from the same authoritative state model.

The repository intentionally separates rules/simulation from presentation. The generic engine does **not** bundle proprietary rulebooks or setting material. It includes an opt-in SRD 5.2.1 foundation built from the Creative-Commons System Reference Document: compact structured mechanics and provenance are bundled while long-form source prose remains in the official SRD. Content outside the SRD remains out of scope unless separately licensed.

See [`docs/SRD_5_2_1.md`](docs/SRD_5_2_1.md) and [`NOTICE-SRD-5.2.md`](NOTICE-SRD-5.2.md).

## Current platform: package 3.9.0 · roadmap through v4.0

The released package remains `3.9.0`, while the implemented product roadmap on `main` now spans v0.1 through the **v4.0 actor-experience milestone**. The v4.0 feature set is documented as unreleased until the package metadata is intentionally advanced in a release change.

| Milestone | Key Features Implemented |
| --- | --- |
| **v0.1 Core Simulation** | entities/components, commands, events, deterministic dice, stats/checks, async SQLite persistence |
| **v0.2 Tactical RPG** | combat resolution, timeline actions, movement/path/LOS, initiative scheduling, conditions, items, delayed spells |
| **v0.3 Adventure Engine** | graph maps, exploration, dialogue graphs, event-driven quests, NPC profiles, shops |
| **v0.4 Living World** | simulation/world clocks, weather, factions/reputation, NPC schedules, supply/demand economy, dynamic events |
| **v0.5 Multiple Frontends** | CLI, live text, Textual TUI, REST API, WebSocket, browser client |
| **v0.6 Visual Adapters** | Godot 2D/3D bridges, actor bindings, scene/asset binding schema |
| **v0.7 AI Game Master** | authoritative-event narrator, NPC personalities, encounter/quest generators, memory/context store |
| **v0.8 Multiplayer** | authoritative campaign sessions, parties, spectators, actor ownership, campaign hosting |
| **v0.9 Creator Platform** | campaign templates, map/creature/rules editors, safe ZIP mod format, mod loader/SDK |
| **v1.0 RPG Platform** | persisted hosted campaigns, community pack registry, marketplace metadata/install, packaged clients, public OpenAPI |
| **v1.1 SRD 5.2.1 Foundation** | opt-in SRD provenance, class/skill/species/background catalogs, proficiency/spellcasting, advantage/disadvantage, armor/damage traits, death saves |
| **v1.2 Rules Runtime** | typed RulesRuntime, roll/attack/damage contexts, modifier traces, effects, reactions, action economy, capability declarations, SRD specialization |
| **v1.3 Event Sourcing** | deterministic patches, SHA-256 state hashes, hash-chained journal, replay/rewind/branching, command-ID idempotency, live-state verification |
| **v1.4 Spatial Authority** | graph/grid/continuous 2D/3D spaces, collision, occupancy, terrain, A*/Dijkstra, LOS, cover, movement budgets |
| **v1.5 Intelligent Actors** | perception snapshots, goals, utility scoring, behavior trees, tactical planning, schedule-aware intent, persistent memories |
| **v1.6 Character Lifecycle** | builder, multiclass progression, XP/milestones, level-up outcomes, class resources, rests, equipment/attunement, SRD adapter |
| **v1.7 Production Hosting** | async PostgreSQL, migrations, simulation workers, PostgreSQL leases, rendezvous-hash placement, reconnect/resume tickets |
| **v1.8 Creator Studio** | persistent projects, revision snapshots, SVG world-map editor, structured content editors, validation/export/publish |
| **v1.9 Executable Rules** | bounded rule IR, deterministic compiler, graph hashes/provenance, rolls/damage/healing/resources/effects/reactions/branching/emit/stop ops, no eval/exec, visual graph editor |
| **v2.0 Campaign Orchestrator** | typed scenes (exploration/encounter/dialogue/travel/downtime/settlement/dungeon), lifecycle (unloaded/loading/active/suspended/resolved/archived), scene-driven entity streaming |
| **v2.1 Simulation Lab** | deterministic seed matrices, bounded concurrent execution, outcome rates, mean/median/stdev/min/max/p10/p90, regression deltas |
| **v2.2 AI Director** | campaign-scale observation, ranked pacing/encounter/quest/faction/world/downtime proposals, proposal-only authority, owner-only API |
| **v2.3 Knowledge Authority** | per-actor known entities/timestamps/facts/confidence, remembered snapshots (no stale hidden truth), knowledge-scoped views, player/owner/spectator visibility |
| **v2.4 Visual Runtime SDK** | canonical/redacted snapshots, visual bindings (scene/sprite/model/animation), hash-verified deltas with base/target validation, transport-neutral |
| **v2.5 Content Distribution** | semver metadata, dependency resolution/cycle detection, engine-version checks, topological install, content/lock hashes, signed releases, persistent registry, REST API |
| **v3.0 Persistent Worlds** | shard registry with capacity/load/heartbeats, rendezvous-hash routing with region affinity, Lamport-ordered cross-shard messages, two-phase entity handoff (prepare/accept/commit/abort), canonical entity hashes, persistent distributed metadata |
| **v3.1 Unified Workbench** | campaign library, GM console, knowledge-scoped player view, world/event inspection |
| **v3.2 Tactical Session** | tactical renderer, authoritative action palette, encounter controls, character lifecycle workspace |
| **v3.3 Full Creator** | typed scene content, scene-flow graph, all ContentPack sections exposed through Studio revisions/validation |
| **v3.4 GM Intelligence** | Director decision workflow, pressure/decision history, knowledge-authority matrix |
| **v3.5 Replay + Analytics** | event aggregation, health/activity summaries, rule-event inspection, timeline scrubber, event-source journal discovery |
| **v3.6 Visual Runtime** | canonical/redacted runtime snapshot inspector, binding/hash visibility, shared tactical projection |
| **v3.7 Campaign Automation** | schedules/dynamic-event observability tied to installed content and world clocks |
| **v3.8 Multiplayer UX** | session lobby, roles/ownership visibility, party creation/membership operations |
| **v3.9 Content Ecosystem** | installed-pack inventory, release browser, locks, dependency resolver, Creator/distribution workflow |
| **v4.0 Hero & NPC Experience** | dedicated `/hero` workshop, lifecycle-backed hero creation/editing, character catalog/listing, owner-only NPC CRUD, NPC profile/entity synchronization, faction/personality/dialogue/shop/schedule wiring, Workbench navigation/command-palette integration |

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

The Director is intentionally proposal-first. The v3.4 Workbench lets the owner explicitly accept/dismiss a proposal, records that decision, and applies only bounded safe proposal metadata such as pacing-pressure deltas. Concrete gameplay changes still flow through normal authoritative actions.

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

## Campaign Workbench

The browser root is a complete campaign operations surface. It provides campaign/session management, GM/player views, tactical play, character lifecycle controls, visual-runtime inspection, AI/knowledge diagnostics, automation observability, analytics/replay, and content/dependency management. See [`docs/WORKBENCH.md`](docs/WORKBENCH.md) for the v3.0–v4.0 product flow and authority model.

Creator Studio at `/creator` is the reusable content-authoring surface: visual maps, executable rule graphs, typed scenes, scene flow, and the complete `ContentPack` schema.

## Hero & NPC Workshop

The v4.0 actor-experience milestone adds `/hero` as a dedicated campaign-instance actor workspace rather than forcing heroes and NPCs through generic entity tools.

For player characters it provides lifecycle-backed creation using the active class/equipment/rest/advancement catalog, safe editing of identity/presentation/base-stat fields, browsing/filtering, and direct links back into the normal authoritative lifecycle operations for XP, level-up, rests, resources, and equipment.

For NPCs it provides owner-only create/read/update/delete operations over first-class `NPCProfile` data. Profile updates synchronize the live entity and can connect the NPC to factions, personalities, dialogue graphs, shops, schedules, AI profiles, positions, appearance, and knowledge tags.

Creator Studio and the Hero & NPC Workshop intentionally serve different scopes:

- `/creator` authors reusable pack content and templates;
- `/hero` manages actors inside a running campaign instance;
- `/` operates and plays the campaign.

See [`docs/ACTORS_4_0.md`](docs/ACTORS_4_0.md) for the authority model and end-to-end actor workflow.

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

- `http://127.0.0.1:8000/` — Campaign Workbench;
- `/hero` — Hero & NPC Workshop for campaign-instance actors;
- `/creator` — Creator Studio, scene flow, full-pack editing, and visual rule graphs;
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

The package release is `3.9.0`; the public transport namespace remains `/api/v1`. The v4.0 milestone is currently an implemented, unreleased product milestone and does not change that namespace.

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
/api/v1/campaigns/{campaign_id}/characters/catalog
/api/v1/campaigns/{campaign_id}/npcs
/api/v1/campaigns/{campaign_id}/rules/compile
/api/v1/campaigns/{campaign_id}/scenes
/api/v1/campaigns/{campaign_id}/director/proposals
/api/v1/campaigns/{campaign_id}/runtime
/api/v1/campaigns/{campaign_id}/workbench/*
/api/v1/studio
/api/v1/distribution
```

Clients submit commands and consume authoritative results; they never calculate trusted outcomes locally.

## Documentation

- [`docs/API.md`](docs/API.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/CREATOR.md`](docs/CREATOR.md)
- [`docs/TIMING.md`](docs/TIMING.md)
- [`docs/RUNTIME_1_2_TO_1_5.md`](docs/RUNTIME_1_2_TO_1_5.md)
- [`docs/RUNTIME_1_6_TO_1_8.md`](docs/RUNTIME_1_6_TO_1_8.md)
- [`docs/RUNTIME_1_9_TO_3_0.md`](docs/RUNTIME_1_9_TO_3_0.md)
- [`docs/WORKBENCH.md`](docs/WORKBENCH.md)
- [`docs/ACTORS_4_0.md`](docs/ACTORS_4_0.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/SRD_5_2_1.md`](docs/SRD_5_2_1.md)

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
