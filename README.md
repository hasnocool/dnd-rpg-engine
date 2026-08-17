# dnd-rpg-engine

A headless, deterministic fantasy RPG simulation platform that can power **turn-based, timed-turn, real-time, real-time-with-pause, hybrid, text, TUI, browser, 2D, 3D, and multiplayer games** from the same authoritative world state.

The repository intentionally separates rules/simulation from presentation. The generic engine does **not** bundle proprietary rulebooks or setting material. It includes an **opt-in SRD 5.2.1 rules foundation** built from the Creative-Commons System Reference Document: structured mechanics and provenance are bundled, while long-form source prose remains in the official SRD. Content outside the SRD remains out of scope unless separately licensed.

See [`docs/SRD_5_2_1.md`](docs/SRD_5_2_1.md) and [`NOTICE-SRD-5.2.md`](NOTICE-SRD-5.2.md).

## What is implemented

The v0.1 → v1.8 roadmap is represented as working modules and integration points:

| Milestone | Implemented |
| --- | --- |
| v0.1 Core Simulation | entities, components, commands, events, deterministic dice streams, stats/checks, async SQLite persistence, snapshots |
| v0.2 Tactical RPG | timeline actions, combat resolution, A* movement helpers, initiative, conditions, items, delayed spells/effects |
| v0.3 Adventure Engine | graph maps, exploration state, dialogue graphs, event-driven quests, NPC profiles, shops |
| v0.4 Living World | simulation/world clocks, weather, factions/reputation, NPC schedules, supply/demand economy, declarative dynamic events |
| v0.5 Multiple Frontends | CLI, live text mode, Textual TUI, REST API, WebSocket event stream, browser client |
| v0.6 Visual Adapters | Godot 4.7.x 2D/3D bridges, actor bindings, scene/asset binding schema |
| v0.7 AI Game Master | authoritative-event narrator, NPC personality model, encounter generator, dynamic quest generator, memory/context store |
| v0.8 Multiplayer | authoritative per-campaign command serialization, parties, spectators, client ownership, live campaign hosting |
| v0.9 Creator Platform | campaign templates, map/creature/rules data models, pack validation, safe ZIP mod format, mod loader/SDK |
| v1.0 RPG Platform | persisted hosted campaigns, community pack registry, marketplace metadata/install flow, packaged clients, public OpenAPI |
| v1.1 SRD 5.2.1 Foundation | opt-in SRD provenance, class/skill/species/background catalogs, fifth-edition-compatible combat hooks |
| v1.2 Rules Runtime | typed resolution contexts/outcomes, modifiers, effects, triggers, reactions, action economy, ruleset capabilities |
| v1.3 Event Sourcing | deterministic patches, hash-chain journal, replay, rewind, branching, command idempotency, verification |
| v1.4 Spatial Authority | graph/grid/continuous spaces, occupancy, collision, terrain, A*/Dijkstra, LOS, cover |
| v1.5 Intelligent Actors | perception, goals, utility AI, behavior-tree primitives, tactical planning, schedules, persistent memories |
| v1.6 Character Lifecycle | character builder, multiclass-compatible progression, XP/milestones, resources, rests, equipment, SRD adapter |
| v1.7 Production Hosting | PostgreSQL, migrations, simulation workers, leases, rendezvous routing, reconnect/resume, missed-event replay |
| v1.8 Creator Studio | persistent typed projects, revision history, visual SVG maps, structured editors, validation/export/publish |

## Time is a first-class subsystem

The engine is fundamentally **timeline-driven**. Turn-based behavior is a policy over that timeline, not a separate combat implementation.

Supported modes:

- `turn_based` — simulation time waits indefinitely at a human decision point.
- `timed_turn_based` — the player receives a configurable decision window; after it expires the timeline continues.
- `real_time` — the timeline continuously advances; AI actors continue acting while a player is idle.
- `real_time_with_pause` — a bounded decision pause is granted when a player becomes ready.
- `hybrid` — real-time world simulation with bounded tactical decision pauses.

This means the same scheduler handles actor readiness, delayed actions, spell completion, conditions, world events, NPC schedules, and idle pressure.

```json
{
  "time_mode": "hybrid",
  "ticks_per_second": 20,
  "time_scale": 1.0,
  "player_decision_timeout_seconds": 10.0,
  "pause_when_player_ready": true,
  "enemies_continue_while_player_idle": true
}
```

In timed/live modes, a human can remain ready without acting. After any configured pause expires, AI readiness tasks continue to resolve and repeat according to their action time. Strict `turn_based` is the only mode where wall-clock time does not advance the simulation.

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[all,dev]'
pytest
```

Run the complete local platform:

```bash
rpg-engine serve --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000/` — browser game client;
- `/creator` — visual Creator Studio;
- `/docs` — OpenAPI.

`rpg-engine serve` uses `AdvancedGameEngine` by default and accepts either a local SQLite path or a PostgreSQL URL through `--database`.

Run a timeline demo:

```bash
rpg-engine demo --mode hybrid --seconds 20 --timeout 5
rpg-engine demo --mode real-time --seconds 20
rpg-engine demo --mode turn-based
```

Run the text client:

```bash
rpg-engine play --mode hybrid --timeout 10
```

Run the Textual client:

```bash
rpg-engine-tui
```

Inspect the bundled SRD source metadata or cache the exact official SRD 5.2.1 PDF locally:

```bash
rpg-engine srd-info
rpg-engine fetch-srd --output .cache/srd/SRD_CC_v5.2.1.pdf
```

## Production hosting

Install the PostgreSQL extra if you did not install `all`:

```bash
pip install -e '.[hosting]'
```

Start the platform against PostgreSQL:

```bash
RPG_DATABASE_URL='postgresql://user:pass@db.example/rpg' rpg-engine-host
```

Start simulation workers against the same database:

```bash
RPG_DATABASE_URL='postgresql://user:pass@db.example/rpg' \
RPG_WORKER_CAPACITY=32 \
rpg-engine-worker
```

Workers use stable rendezvous hashing for preferred campaign placement and PostgreSQL leases as the authoritative single-owner guard. Reconnect tickets are opaque, stored only by hash, rotate on successful resume, and carry an event checkpoint so clients can replay what they missed.

## Architecture

```text
CLI / TUI / Browser / Creator Studio / Godot / remote clients
                              │
                      commands / events
                              │
                    AdvancedGameEngine
                              │
      ┌───────────────┬───────┼───────────────┬────────────────┐
      │               │       │               │                │
 RulesRuntime   Character   Spatial      Intelligent        Living
 + effects      lifecycle   authority      actors            world
      │               │       │               │                │
      └───────────────┴───────┴───────────────┴────────────────┘
                              │
                    deterministic state
                              │
                event journal / snapshots
                              │
                  persistence contract
                    ┌─────────┴─────────┐
                    ▼                   ▼
                 SQLite            PostgreSQL
               local/dev       production/shared
                                        │
                              workers + leases + resume
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/TIMING.md`](docs/TIMING.md), [`docs/RUNTIME_1_2_TO_1_5.md`](docs/RUNTIME_1_2_TO_1_5.md), and [`docs/RUNTIME_1_6_TO_1_8.md`](docs/RUNTIME_1_6_TO_1_8.md).

## Public API examples

Create a campaign:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/campaigns \
  -H 'content-type: application/json' \
  -d '{"name":"My Campaign","owner_id":"local","seed":42,"time_mode":"hybrid","player_decision_timeout_seconds":10}'
```

Change timing at runtime:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/campaigns/CAMPAIGN_ID/timing \
  -H 'content-type: application/json' \
  -H 'X-RPG-Client-ID: OWNER_CLIENT_ID' \
  -d '{"time_mode":"real_time","pause_when_player_ready":false}'
```

WebSocket clients connect to:

```text
ws://127.0.0.1:8000/api/v1/campaigns/{campaign_id}/ws
```

Clients send commands and consume events; they never calculate authoritative outcomes locally.

Character lifecycle endpoints live below:

```text
/api/v1/campaigns/{campaign_id}/characters
```

Reconnect and hosting status endpoints are exposed through the same stable `/api/v1` namespace.

## Creator Studio / mod SDK

A `ContentPack` contains a manifest plus optional campaign templates, creature templates, actions, conditions, items, spells, maps, dialogues, quests, rules, and asset bindings. The SDK validates cross-references, computes a deterministic SHA-256 content hash, and exports/imports a bounded ZIP format with path traversal checks.

The browser Creator Studio at `/creator` now edits the actual typed `ContentPack` models instead of maintaining a separate raw-JSON-only format. It includes:

- persistent Studio projects;
- revision snapshots and restore;
- a draggable SVG world-map graph editor;
- structured creature, spell, quest, rules, and campaign forms;
- validation through the runtime `ContentValidator`;
- validated export;
- marketplace publication.

Studio APIs live under `/api/v1/studio`.

## Godot

The adapters target the current stable Godot 4.7 line and are deliberately thin:

```text
adapters/godot2d/
adapters/godot3d/
adapters/bindings/
```

Godot owns rendering, animation, camera, audio, and local input. The Python server owns truth: timing, AI, checks, effects, state, character advancement, and persistence.

## AI Game Master boundary

The narrator consumes authoritative events and memory context. Narration cannot directly mutate world state. Procedural encounter/quest generators return structured engine data; external model providers can be implemented behind the `NarrativeProvider` protocol without giving them write access to simulation internals.

## Development

```bash
make test
make coverage
make demo
make serve
```

CI tests Python 3.12, 3.13, and 3.14, compiles the package, and runs the full test suite.

## License

Engine code is MIT licensed. Third-party campaign/rules content can carry its own license through each mod manifest. The bundled SRD 5.2.1 integration is separately attributed under CC BY 4.0; see `NOTICE-SRD-5.2.md`.
