# dnd-rpg-engine

A headless, deterministic fantasy RPG simulation platform that can power **turn-based, timed-turn, real-time, real-time-with-pause, hybrid, text, TUI, browser, 2D, 3D, and multiplayer games** from the same authoritative world state.

The repository intentionally separates rules/simulation from presentation. The generic engine does **not** bundle proprietary rulebooks or setting material. It now includes an **opt-in SRD 5.2.1 rules foundation** built from the Creative-Commons System Reference Document: structured mechanics and provenance are bundled, while long-form source prose remains in the official SRD. Content outside the SRD remains out of scope unless separately licensed.

See [`docs/SRD_5_2_1.md`](docs/SRD_5_2_1.md) and [`NOTICE-SRD-5.2.md`](NOTICE-SRD-5.2.md).

## What is implemented

The full v0.1 → v1.0 roadmap is represented as working modules and integration points:

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
| v0.9 Creator Platform | campaign templates, map/creature/rules JSON editors, pack validation, safe ZIP mod format, mod loader/SDK |
| v1.0 RPG Platform | persisted hosted campaigns, community pack registry, marketplace metadata/install flow, packaged CLI/TUI/browser clients, public OpenAPI |

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

Run the browser/API server:

```bash
rpg-engine serve --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/` for the browser client, `/creator` for the creator platform, or `/docs` for OpenAPI.

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

## Architecture

```text
CLI / TUI / Browser / Godot 2D / Godot 3D / remote clients
                           │
                   commands / events
                           │
                 Authoritative Engine
                           │
      ┌────────────────────┼─────────────────────┐
      │                    │                     │
 Timeline Scheduler   Tactical Systems     Living World
      │                    │                     │
 actor readiness       actions/checks       world clock
 decision windows      movement/effects     weather
 delayed actions       conditions/items     factions
 cooldowns             spells               economy
      │                    │                 schedules
      └────────────────────┼─────────────────────┘
                           │
                   Adventure Systems
                           │
               maps/dialogue/quests/NPCs
                           │
                     Event Stream
                           │
         SQLite persistence / WebSocket fan-out
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/TIMING.md`](docs/TIMING.md).

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
  -d '{"time_mode":"real_time","pause_when_player_ready":false}'
```

Start an encounter/initiative timeline:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/campaigns/CAMPAIGN_ID/encounters \
  -H 'content-type: application/json' \
  -d '{"participant_ids":["hero","rival"]}'
```

WebSocket clients connect to:

```text
ws://127.0.0.1:8000/api/v1/campaigns/{campaign_id}/ws
```

Clients send commands and consume events; they never calculate authoritative outcomes locally.

## Creator/mod SDK

A `ContentPack` contains a manifest plus optional campaign templates, creature templates, actions, conditions, items, spells, maps, dialogues, quests, rules, and asset bindings. The SDK validates cross-references, computes a deterministic SHA-256 content hash, and exports/imports a bounded ZIP format with path traversal checks.

The browser creator at `/creator` edits the major content sections as validated JSON. A campaign template can be instantiated directly through `POST /api/v1/creator/instantiate`.

## Godot

The adapters target the current stable Godot 4.7 line and are deliberately thin:

```text
adapters/godot2d/
adapters/godot3d/
adapters/bindings/
```

Godot owns rendering, animation, camera, audio, and local input. The Python server owns truth: timing, AI, checks, effects, state, and persistence.

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
