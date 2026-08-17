# dnd-rpg-engine

A headless, deterministic fantasy RPG application platform that can power **turn-based, timed-turn, real-time, real-time-with-pause, hybrid, text, TUI, browser, 2D, 3D, multiplayer, and distributed-world games** from the same authoritative simulation model.

The repository intentionally separates rules/simulation from presentation. The generic engine does **not** bundle proprietary rulebooks or setting material. It includes an **opt-in SRD 5.2.1 rules foundation** built from the Creative-Commons System Reference Document: structured mechanics and provenance are bundled, while long-form source prose remains in the official SRD. Content outside the SRD remains out of scope unless separately licensed.

See [`docs/SRD_5_2_1.md`](docs/SRD_5_2_1.md) and [`NOTICE-SRD-5.2.md`](NOTICE-SRD-5.2.md).

## What is implemented

The v0.1 → v2.5 roadmap is represented as working modules, APIs, tests, and integration points:

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
| v1.7 Production Hosting | PostgreSQL, migrations, simulation workers, campaign leases, rendezvous routing, reconnect/resume, missed-event replay |
| v1.8 Creator Studio | persistent typed projects, revision history, visual SVG maps, structured editors, validation/export/publish |
| v1.9 Identity + Multi-Tenancy | signed sessions, organizations/workspaces, RBAC, campaign/project ownership, actor authorization, audit records |
| v2.0 Distributed Worlds | zone partitions, rendezvous placement, PostgreSQL zone leases, two-phase verified entity handoff |
| v2.1 Content Package Graph | semver constraints, dependencies, deterministic lockfiles, compatibility checks, migration/upgrade planning |
| v2.2 Simulation Lab | deterministic batch simulations, balance metrics/findings, variant comparisons, rules-backed campaign duels |
| v2.3 Reliable Multiplayer | command sequences/acks, retry idempotency, rate limits, presence, subscriptions, reliable authenticated WebSocket |
| v2.4 Campaign Director | persistent story/tension planner, structured proposals, governed command approval through normal authority paths |
| v2.5 Client SDKs | Python async SDK, TypeScript fetch/WebSocket SDK, Godot reliable client helper, end-to-end platform integration |

## Core authority model

Presentation, AI, creator tools, and clients do not own game truth:

```text
Browser / Godot / Python / TypeScript / TUI / CLI
                         │
                 authenticated commands
                         ▼
              campaign authorization
                         ▼
                 CampaignSession
                         ▼
                 RulesRuntime
                         ▼
              authoritative events
                         ▼
             deterministic state
```

The Campaign Director follows the same rule: it proposes intent; approved commands still pass through the authenticated campaign session and normal rules engine.

## Time is a first-class subsystem

The engine is fundamentally **timeline-driven**. Turn-based behavior is a policy over that timeline, not a separate combat implementation.

Supported modes:

- `turn_based` — simulation time waits indefinitely at a human decision point.
- `timed_turn_based` — the player receives a configurable decision window; after it expires the timeline continues.
- `real_time` — the timeline continuously advances; AI actors continue acting while a player is idle.
- `real_time_with_pause` — a bounded decision pause is granted when a player becomes ready.
- `hybrid` — real-time world simulation with bounded tactical decision pauses.

The same scheduler handles actor readiness, delayed actions, spell completion, effects, conditions, world events, NPC schedules, and idle pressure.

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[all,dev]'
pytest
```

Run the complete local platform in compatibility mode:

```bash
rpg-engine serve --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000/` — browser client;
- `/creator` — visual Creator Studio;
- `/docs` — OpenAPI.

Run other packaged clients/tools:

```bash
rpg-engine demo --mode hybrid --seconds 20 --timeout 5
rpg-engine play --mode hybrid --timeout 10
rpg-engine-tui
rpg-engine srd-info
```

## Authenticated production mode

Install the production hosting extra if needed:

```bash
pip install -e '.[hosting]'
```

Use PostgreSQL plus separate high-entropy authentication/provisioning secrets:

```bash
export RPG_DATABASE_URL='postgresql://user:pass@db.example/rpg'
export RPG_AUTH_REQUIRED=1
export RPG_AUTH_SECRET='<random 32+ byte signing secret from a secret manager>'
export RPG_BOOTSTRAP_KEY='<separate random server-side provisioning secret>'

rpg-engine-host
```

The values above are placeholders. Do not commit real credentials or expose the bootstrap key to browser/game clients. Public deployments should terminate HTTPS/WSS at a trusted ingress or reverse proxy.

Authenticated mode changes the trust model:

- users authenticate to persistent server sessions;
- effective roles remain server-side, so membership changes are immediate;
- campaign clients are bound to the same bearer session that created/joined them;
- callers cannot choose campaign ownership by submitting an `owner_id`;
- legacy caller-asserted create/join/command/publish mutations are disabled;
- the legacy unauthenticated campaign WebSocket is removed;
- the reliable authenticated transport becomes the multiplayer command path.

See [`SECURITY.md`](SECURITY.md).

## Secure campaign example

Controlled provisioning:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/bootstrap \
  -H 'content-type: application/json' \
  -H 'X-RPG-Bootstrap-Key: <server-side bootstrap key>' \
  -d '{"user_id":"local-user","display_name":"Local User"}'
```

Use the returned bearer token to create an authenticated campaign:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/secure/campaigns \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <access token>' \
  -d '{"name":"My Campaign","seed":42,"time_mode":"hybrid"}'
```

Reliable commands use:

```text
POST /api/v1/reliable/campaigns/{campaign_id}/commands
WS   /api/v1/reliable/campaigns/{campaign_id}/ws
```

Each campaign client has an exact monotonically increasing command sequence. Retrying the same sequence with the same command returns the previous acknowledgement without re-executing the command.

## Production workers and distributed worlds

Start whole-campaign workers against PostgreSQL:

```bash
RPG_DATABASE_URL="$RPG_DATABASE_URL" \
RPG_WORKER_CAPACITY=32 \
rpg-engine-worker
```

v2.0 adds finer-grained world zones:

```text
World
├─ west-wilderness → worker A
├─ east-wilderness → worker B
├─ capital         → worker C
└─ dungeon         → worker D
```

Rendezvous hashing selects preferred placement, while **PostgreSQL zone leases** are the authoritative single-writer guard. Cross-zone entities move through hash-verified two-phase handoffs. SQLite's lease fallback is process-local and intended for development/testing, not multi-host ownership coordination.

Distributed APIs live under `/api/v1/distributed`.

## Content packages and reproducible campaigns

v2.1 adds a deterministic package graph:

```text
campaign.lock
engine=2.5.0
campaign==3.0.0#<content hash>
monsters==2.0.0#<content hash>
rules==1.1.0#<content hash>
```

The resolver supports semantic-version constraints, dependency conflict detection, engine compatibility, content hashes, and migration-aware upgrade planning.

Package APIs live under `/api/v1/packages`.

## Simulation Lab

The deterministic engine can run large batches without mutating the live campaign. Reports include win rates, median/p95 durations, knockout rate, resource utilization, custom metric means, findings, and a deterministic digest.

The campaign duel endpoint clones two live actor snapshots and resolves combat through the normal `CombatSystem` and active rules:

```text
POST /api/v1/simulation/campaigns/{campaign_id}/duel
```

## Campaign Director

The persistent Director observes authoritative events and tracks tension, open story threads, scene repetition, and faction pressure. It emits structured proposals such as advancing a thread, introducing pressure, adding a social/recovery beat, or applying a faction consequence.

```text
Events → Director → Proposal → approval → CampaignSession → RulesRuntime → Events
```

External AI/provider context excludes writable engine/service objects. Candidate commands are parsed before they can be attached to proposals.

Director APIs live under `/api/v1/director`.

## Creator Studio and multi-tenancy

The browser Creator Studio at `/creator` edits the same typed `ContentPack` models used at runtime. It includes persistent revision history, a draggable SVG map editor, structured creature/spell/quest/rules/campaign forms, validation, export, and publishing.

In authenticated mode, Studio projects have explicit owner/organization/workspace ancestry and exact read/write/publish permissions. A user cannot take ownership of a legacy project simply by knowing its ID.

Studio APIs live under `/api/v1/studio`.

## Client SDKs

### Python

```python
from dnd_rpg_engine import RPGClient

client = RPGClient()
await client.bootstrap(
    user_id="local-user",
    display_name="Local User",
    bootstrap_key=bootstrap_key,
)
campaign = await client.create_campaign("Example", seed=42)
await client.command(
    campaign.campaign_id,
    {"type": "wait", "actor_id": "hero"},
)
```

### TypeScript

See `sdk/typescript/`. It contains a buildable package with fetch-based authenticated APIs and a reliable WebSocket helper.

### Godot

`adapters/godot/common/RPGClient.gd` provides a thin reliable WebSocket client with command-ack and game-event signals. Godot owns rendering/input; the server owns game truth.

## Architecture

```text
              Browser / Godot / Python / TypeScript
                            │ HTTPS/WSS
                            ▼
                   Platform API / RBAC
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
 reliable multiplayer   Creator Studio     Campaign Director
       │                    │                    │
       └─────────────── CampaignSession ─────────┘
                            │
                       RulesRuntime
                            │
      ┌─────────────────────┼──────────────────────┐
      │                     │                      │
 character lifecycle   spatial authority   intelligent actors
      │                     │                      │
      └──────────────── deterministic state ──────┘
                            │
                    events / event sourcing
                            │
                    persistence contract
                  ┌─────────┴──────────┐
                  ▼                    ▼
               SQLite             PostgreSQL
             local/dev       production/shared
                                      │
                     campaign leases + zone leases
                                      │
                           distributed workers
```

Detailed architecture:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/TIMING.md`](docs/TIMING.md)
- [`docs/RUNTIME_1_2_TO_1_5.md`](docs/RUNTIME_1_2_TO_1_5.md)
- [`docs/RUNTIME_1_6_TO_1_8.md`](docs/RUNTIME_1_6_TO_1_8.md)
- [`docs/RUNTIME_1_9_TO_2_5.md`](docs/RUNTIME_1_9_TO_2_5.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Development

```bash
make test
make coverage
make demo
make serve
```

CI compiles the package and runs the full suite on Python 3.12, 3.13, and 3.14.

## License

Engine code is MIT licensed. Third-party campaign/rules content can carry its own license through each mod manifest. The bundled SRD 5.2.1 integration is separately attributed under CC BY 4.0; see `NOTICE-SRD-5.2.md`.
