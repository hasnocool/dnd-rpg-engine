# Roadmap status

The implemented product roadmap now runs through **v4.0**.

- **Released package:** `3.9.0`
- **Implemented roadmap on `main`:** v0.1 → v4.0
- **v4.0 release status:** feature set implemented, package/version release intentionally still pending
- **Stable transport namespace:** `/api/v1`

The roadmap tracks product capability milestones, not only package tags. A milestone may therefore be implemented on `main` before a release commit advances package metadata.

## Historical foundation — complete

| Milestone | Status | Core capability |
| --- | --- | --- |
| v0.1 Core Simulation | complete | entities/components, commands/events, deterministic dice/checks, async SQLite persistence |
| v0.2 Tactical RPG | complete | combat, timeline actions, movement/path/LOS, initiative, conditions, items, delayed spells |
| v0.3 Adventure Engine | complete | graph maps, exploration, dialogue, quests, NPC profiles, shops |
| v0.4 Living World | complete | clocks, weather, factions/reputation, NPC schedules, economy, dynamic events |
| v0.5 Multiple Frontends | complete | CLI, live text, Textual TUI, REST, WebSocket, browser |
| v0.6 Visual Game Adapters | complete | Godot 2D/3D bindings and scene/asset schema |
| v0.7 AI Game Master | complete | narrator boundary, personalities, encounter/quest generation, bounded memory |
| v0.8 Multiplayer | complete | authoritative sessions, parties, spectators, actor ownership, campaign hosting |
| v0.9 Creator Platform | complete | templates/editors, validation, safe ZIP mod format, loader/SDK |
| v1.0 RPG Platform | complete | persistent hosted campaigns, registry/marketplace, packaged clients, versioned OpenAPI |
| v1.1 SRD 5.2.1 Foundation | complete | opt-in SRD catalogs/provenance, proficiency/spellcasting, armor/damage, death saves/conditions |
| v1.2 Rules Runtime + Effect Pipeline | complete | typed rules runtime, modifier traces, effects, reactions, action economy, capabilities |
| v1.3 Deterministic Event Sourcing | complete | canonical hashes, hash chain, replay/rewind/branches, command idempotency, verification |
| v1.4 Spatial Authority | complete | graph/grid/continuous spaces, occupancy/collision, pathfinding, LOS/cover, terrain budgets |
| v1.5 Intelligent Living Actors | complete | perception, goals, utility scoring, behavior trees, tactical planning, schedules, memories |
| v1.6 Character Lifecycle | complete | builder, multiclass progression, XP/milestones, resources, rests, equipment/attunement |
| v1.7 Production Campaign Hosting | complete | async PostgreSQL, migrations, workers, leases, placement, reconnect/resume |
| v1.8 Creator Studio | complete | persistent projects/revisions, visual maps, structured editors, validation/export/publish |
| v1.9 Executable Rules | complete | bounded deterministic rule graph/compiler/executor, hashes/provenance, visual graph editor |
| v2.0 Campaign Orchestrator | complete | typed scenes, authoritative scene lifecycle, persisted scene state, streaming sets |
| v2.1 Simulation Lab | complete | deterministic seed matrices, bounded concurrency, aggregate statistics, regression deltas |
| v2.2 Advanced AI Director | complete | campaign-scale ranked proposals with reasons/utility and proposal-only authority |
| v2.3 Perception + Knowledge Authority | complete | actor knowledge, remembered snapshots, facts/confidence, scoped owner/player/spectator views |
| v2.4 Visual Runtime SDK | complete | canonical/redacted snapshots, bindings, hash-verified deltas, transport-neutral sync |
| v2.5 Content Distribution Platform | complete | semver dependencies, compatibility, hashes/locks/signatures, persistent registry/API |

## v3.0 — Massively Persistent Worlds foundation — complete

- [x] world-shard registry with capacity/load/status/heartbeat state
- [x] stable SHA-256 rendezvous routing with explicit region affinity
- [x] shard expiration and deterministic region rebalance plans
- [x] Lamport-ordered cross-shard messages with idempotency keys
- [x] two-phase entity handoff: prepare → accept → commit/abort
- [x] canonical entity-state hashes and exactly-once committed-transfer guard
- [x] transfer payload verification and entity restoration
- [x] persistent shard, region-assignment, transfer, and cross-shard-message records
- [x] shared SQLite/PostgreSQL persistence contract for distributed metadata
- [x] compatibility with production worker/campaign lease infrastructure from v1.7

The v3.0 milestone establishes deterministic persistence, routing, handoff, and authority primitives required to scale into multiple simulation processes. Production deployments can layer transport, service discovery, observability, and infrastructure around these interfaces without changing campaign/rules/client contracts.

## v3.1 — Unified Campaign Workbench — complete

- [x] campaign library/launcher
- [x] separate GM and knowledge-scoped player surfaces
- [x] world-state and persisted event-history views
- [x] scene lifecycle controls
- [x] AI Director inspection
- [x] live WebSocket event integration without client-side authority

## v3.2 — Session Operations + Tactical Play — complete

- [x] dedicated tactical encounter workspace
- [x] authoritative actor/target selection and action palette
- [x] movement commands validated by SpatialAuthority
- [x] action/spell/item/executable-rule catalog
- [x] encounter start/end owner controls
- [x] action-economy/spatial summary
- [x] character lifecycle sheet, rests, equipment, resources, XP, and level-up controls

## v3.3 — Full Creator Workbench — complete

- [x] typed `SceneDefinition` ContentPack section
- [x] scene ZIP/hash/validation/runtime-install integration
- [x] scene-flow graph based on `next_scene_ids`
- [x] Creator Studio coverage for actions/conditions/items/dialogue/NPCs/shops/factions/schedules/events/personalities/encounters
- [x] Creator Studio coverage for rules data and assets
- [x] existing visual maps/rules/campaign editors retained
- [x] revision/validation/export/publish flow retained across all sections

## v3.4 — Advanced GM Intelligence — complete

- [x] dedicated AI Director proposal dashboard
- [x] proposal utility/reasons/payload display
- [x] owner Accept/Dismiss decision workflow
- [x] bounded pressure-metadata application preserving proposal authority boundary
- [x] persisted Director decision history
- [x] GM knowledge-authority matrix and fact/observation inspection

## v3.5 — Replay + Campaign Analytics — complete

- [x] persisted event aggregation and type/actor/target counts
- [x] numeric event totals and entity-health summary
- [x] rules-event inspection for explainability
- [x] event timeline scrubber
- [x] persisted EventSourcedEngine journal discovery
- [x] branch/rewind capability advertised only when event-source journal data exists

## v3.6 — Visual World Runtime — complete

- [x] canonical owner RuntimeSnapshot inspector
- [x] actor-scoped redacted RuntimeSnapshot inspector
- [x] snapshot sequence/hash/facts/bindings display
- [x] position-based browser renderer shared with tactical view
- [x] presentation-only grid/label controls
- [x] server remains authoritative for movement/visibility/rules

## v3.7 — Campaign Automation — complete

- [x] installed NPC schedule observability
- [x] installed dynamic-event observability
- [x] simulation/world clock context
- [x] active-scene context
- [x] authoring remains in typed Creator Studio
- [x] trigger evaluation remains server-side living-world behavior

## v3.8 — Multiplayer Experience — complete

- [x] session lobby
- [x] connected client/role/ownership visibility
- [x] party creation
- [x] party actor/user membership operations
- [x] scene readiness/session state display
- [x] sanitized player ownership and reconnect/resume boundaries retained

## v3.9 — Content Ecosystem — complete

- [x] installed content-pack inventory and section summaries
- [x] dependency manifest visibility
- [x] distribution release browser
- [x] dependency-lock inspection
- [x] interactive distribution resolver
- [x] Creator publication remains the package/release source
- [x] released package/API/browser version aligned at 3.9.0

## v4.0 — Hero & NPC Experience — feature complete on `main`

The v4.0 milestone turns player characters and NPCs into a first-class campaign-instance workflow. This is intentionally separate from Creator Studio, which remains the reusable content-authoring surface.

### Hero Creator

- [x] dedicated `/hero` Hero & NPC Workshop route
- [x] Workbench navigation and `Create Character / Hero` command-palette entry
- [x] campaign selection and owner identity workflow
- [x] lifecycle-backed hero creation
- [x] active class/equipment/rest/advancement catalog visibility
- [x] class, starting level, species/ancestry, background, owner, XP, six ability scores, tags, starting equipment, appearance, portrait, and presentation metadata
- [x] hero browse/filter workflow
- [x] safe character edits for identity/presentation/base-stat fields
- [x] class/level/XP/equipment/resource/rest authority remains in `CharacterLifecycle`

### NPC Manager

- [x] owner-only NPC list/create/read/update/delete APIs
- [x] campaign-instance NPC browse/filter workflow
- [x] `NPCProfile` ↔ live entity synchronization
- [x] name, role, AI profile, six ability scores, HP/resources, position/map, tags, appearance, portrait, and knowledge metadata
- [x] faction relationship
- [x] personality relationship
- [x] dialogue graph relationship
- [x] shop relationship
- [x] schedule relationship with server-side validation/assignment
- [x] create/update/remove authoritative NPC events and persistence

### Product boundary

- [x] `/creator` remains reusable ContentPack/template authoring
- [x] `/hero` owns campaign-instance actor creation/administration
- [x] `/` remains campaign operations and live play
- [x] browser surfaces never become authoritative rules/progression/AI engines

### Release follow-up

The v4.0 feature set is implemented, but the repository package metadata remains `3.9.0`. A future release change can intentionally advance package/changelog/version metadata to `4.0.0` after release validation; this documentation update does not perform that release bump.

## Next roadmap boundary

New feature planning should start at **v4.1**. The current milestone chain is therefore:

```text
v3.0 Persistent Worlds
  → v3.1 Unified Workbench
  → v3.2 Tactical Session
  → v3.3 Full Creator
  → v3.4 GM Intelligence
  → v3.5 Replay + Analytics
  → v3.6 Visual Runtime
  → v3.7 Campaign Automation
  → v3.8 Multiplayer UX
  → v3.9 Content Ecosystem
  → v4.0 Hero & NPC Experience
```
