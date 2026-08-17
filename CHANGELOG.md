# Changelog

## Unreleased — v4.0 Hero & NPC Experience

### Added
- Dedicated `/hero` Hero & NPC Workshop for first-class campaign-instance actor administration.
- Lifecycle-backed Hero Creator with campaign selection, active class/equipment/rest/advancement catalog, character creation, browse/filter, and safe profile editing.
- Owner-only NPC CRUD API and browser workflow with `NPCProfile`/live-entity synchronization.
- NPC relationship editing for factions, personalities, dialogue graphs, shops, schedules, AI profiles, position, appearance, and knowledge metadata.
- Workbench Hero Creator navigation and `Create Character / Hero` command-palette entry.
- `docs/ACTORS_4_0.md` and refreshed README/API/architecture/Creator/Workbench/roadmap documentation through v4.0.

### Changed
- Documentation now distinguishes the released package version (`3.9.0`) from the implemented v4.0 roadmap milestone; this documentation pass does not perform a package release bump.
- Creator Studio is documented as the reusable content-authoring surface, while `/hero` owns campaign-instance actor administration and `/` owns campaign operations/live play.

## 3.9.0 - 2026-08-17

### Added
- Unified Campaign Workbench v3.1-v3.9 covering campaign library, Session Lobby, GM/player operations, tactical play, character lifecycle, visual runtime, Director/knowledge diagnostics, automation observability, analytics/replay, and content/dependency management.
- Campaign Workbench aggregation API for owner session state, parties, tactical/catalog projections, analytics, knowledge inspection, replay metadata, installed content, and Director decisions.
- Typed `SceneDefinition` content-pack section with ZIP round trips, validation, runtime registration, and Creator Studio editing.
- Full Creator Studio coverage for actions, conditions, items, dialogue, NPCs, shops, factions, schedules, dynamic events, personalities, encounters, rules data, assets, and a visual scene-flow graph.
- Explicit owner Accept/Dismiss workflow for AI Director proposals with bounded pressure metadata updates and persisted decision history.
- Regression coverage for v3.x browser views, workbench APIs, player knowledge scoping, full-pack Creator editing, and scene-link validation.

### Changed
- Package version advances to `3.9.0`; the stable HTTP/WebSocket namespace remains `/api/v1`.
- `WorldPlatformEngine` now exposes bounded Director decision methods while preserving the proposal/advisory authority boundary for concrete gameplay mutations.
- Creator Studio section typing now covers the complete `ContentPack` schema.

## 3.0.1 - 2026-08-17

### Changed
- Maintenance release.

## 3.0.0 - 2026-08-16

### Added
- `WorldPlatformEngine`, the integrated v1.9-v3.0 profile layered over `AdvancedGameEngine` without removing the compatibility-first engine surfaces.
- Persistent world-shard directory with capacity/load/heartbeat state, explicit region affinity, stable SHA-256 rendezvous routing, expiration, and rebalance plans.
- Two-phase cross-shard entity transfers with canonical state hashes, prepare/accept/commit/abort states, payload verification, and exactly-once commit guards.
- Lamport-ordered cross-shard messages with idempotency keys.
- `PersistentWorldRegistry` for shard, region-assignment, transfer, and message metadata over the existing SQLite/PostgreSQL JSON-store contract.

### Changed
- Package version advances to `3.0.0`; `/api/v1` remains the stable HTTP/WebSocket namespace.
- The default advanced platform server now boots `WorldPlatformEngine` while reporting the established `engine_profile=advanced` compatibility value plus `platform_profile=world`.
- World-profile campaign reads, event history, and WebSockets are knowledge-scoped so non-owner clients do not receive omniscient state.

## 2.5.0 - 2026-08-16

### Added
- Deterministic content distribution index with semantic-version requirements, dependency resolution, engine compatibility, cycle detection, topological install order, update planning, content hashes, and dependency lock hashes.
- Package signature metadata and built-in HMAC-SHA256 signer suitable for private registries and deterministic tests.
- Persistent release/lock service using the common JSON-store contract.
- Distribution REST endpoints plus Creator Studio publish-to-marketplace-and-distribution flow.

## 2.4.0 - 2026-08-16

### Added
- Transport-neutral visual runtime SDK with canonical state snapshots, redacted KnowledgeView snapshots, visual bindings, client cursors, and hash-verified add/replace/remove deltas.
- Deterministic delta apply/verification suitable for browser, Godot, and remote clients.

## 2.3.0 - 2026-08-16

### Added
- Per-actor Knowledge Authority with known entities, observation timestamps, remembered entity snapshots, facts, confidence, sources, tags, and expiry.
- Perception ingestion into persistent entity components.
- Public-component filtering for non-self observations and stale-snapshot semantics preventing hidden live state from leaking after line of sight is lost.
- Knowledge-scoped campaign GET/event/WebSocket routes for the v3 world profile.

## 2.2.0 - 2026-08-16

### Added
- Campaign-scale AI Director producing deterministic, explainable pacing, encounter, quest, faction, world-event, and downtime proposals.
- Pressure/resource-aware recovery and decompression suggestions while preserving a proposal-only authority boundary.

## 2.1.0 - 2026-08-16

### Added
- Deterministic Simulation Lab with seed matrices, bounded async concurrency, outcome/event capture, statistical summaries, percentile metrics, and report comparisons.

## 2.0.0 - 2026-08-16

### Added
- Authoritative Campaign Orchestrator with typed scenes, validated lifecycle transitions, exclusive activation, persisted scene runtime state, next-scene candidates, and active/preload entity streaming sets.
- Scene registration and transition APIs.

## 1.9.0 - 2026-08-16

### Added
- Bounded declarative `RuleCompiler`, `ExecutableRuleGraph`, and `RuleExecutor` connected directly to the typed `RulesRuntime`.
- Canonical graph hashes, source provenance, deterministic execution budgets, and node-by-node execution traces.
- Allowlisted roll, damage, healing, resource, state, effect, reaction, flow, emit, and stop operations with no arbitrary script execution.
- `RuleDocument.graph` support through Creator Studio, content-pack hashing, and ZIP import/export.
- Authoritative `rule.execute` command support in `WorldPlatformEngine`.
- Visual Creator Studio rule graph editor and compiler validation endpoint.

## 1.8.0 - 2026-08-16

### Added
- Persistent typed Creator Studio projects with revision snapshots, restore-as-new-revision history, validation, export, and marketplace publishing.
- Visual SVG world-map editor with draggable nodes, typed connections, node inspection, layout controls, and pack-health feedback.
- Structured browser editors for creatures, spells, quests/objectives, rules documents, and campaign templates instead of raw JSON-only editing.
- `/api/v1/studio` endpoints backed by the same `ContentPack` models and `ContentValidator` used by runtime content loading.
- v1.8 platform application factory combining existing REST/WebSocket routes with lifecycle, hosting, reconnect, and Creator Studio APIs.
- `rpg-engine-host` production platform command; the existing `rpg-engine serve` command now starts the full Studio-capable v1.8 platform as well.

### Changed
- Package version is now `1.8.0` while the stable public HTTP namespace remains `/api/v1`.
- Public package exports include `CharacterLifecycle` and the integrated `AdvancedGameEngine` profile.

## 1.7.0 - 2026-08-16

### Added
- Async PostgreSQL persistence backend implementing the existing campaign/event/snapshot/JSON-store contract.
- Ordered PostgreSQL schema migrations for campaigns, events, snapshots, hosted campaigns, workers, leases, and reconnect-ticket indexes.
- Production simulation-worker registry with heartbeat health, capacity limits, stable rendezvous-hash placement, and authoritative PostgreSQL campaign leases.
- `rpg-engine-worker` process entrypoint for horizontally scalable campaign simulation workers.
- Opaque reconnect/resume tickets stored by SHA-256 token hash, including expiration, revocation, rotation, event-sequence checkpoints, and missed-event replay.
- Hosting status and reconnect/resume HTTP endpoints.
- Optional `hosting` dependency group for `asyncpg`, keeping SQLite-only installations lightweight.

### Changed
- Storage backend selection can use a PostgreSQL URL without changing normal engine persistence call sites.
- SQLite remains the zero-setup local/development backend.

## 1.6.0 - 2026-08-16

### Added
- Ruleset-neutral character lifecycle service covering character construction, multiclass-compatible progression, XP/milestone advancement, level-up outcomes, class resources, rests, equipment slots, and attunement.
- Persistent lifecycle state stored in normal entity components so advancement participates naturally in snapshots, replay, event sourcing, multiplayer, and saves.
- Generic equipment aggregation and class-resource recovery hooks suitable for custom rulesets.
- SRD lifecycle adapter generated from the existing compact class catalog.
- Character lifecycle commands/events integrated into `AdvancedGameEngine` plus REST endpoints for character creation, XP, level-up, rests, equipment, and resource management.

### Changed
- SRD proficiency now prefers the new multiclass-aware lifecycle level while retaining the legacy `progression.level` fallback.
- Rest completion resets the active rules runtime's turn/action economy through the typed runtime interface.

## 1.5.0 - 2026-08-16

### Added
- Typed `RulesRuntime` boundary with ruleset capabilities, typed roll/attack/damage contexts and outcomes with explainable modifier traces.
- Deterministic effect pipeline supporting stacked timed effects, flat/multiplicative/min/max modifiers, advantage/disadvantage sources, reaction opportunities, and per-actor action economy.
- Deterministic event-sourcing journal with canonical state hashing, SHA-256 hash chaining, replay, rewind, branching, command-ID idempotency, and live-state verification.
- Authoritative spatial subsystem with graph, grid, continuous 2D, and continuous 3D spaces; weighted pathfinding, occupancy/capacity, collision, terrain costs, movement budgets, line-of-sight, and cover queries.
- Intelligent living-actor subsystem with authoritative perception snapshots, goals, utility scoring, tactical action planning, behavior-tree primitives, schedule-aware intent, and persistent component-backed memories.
- Regression suites for rules/effects, event sourcing, spatial authority, and intelligent actor planning across the supported Python matrix.

### Changed
- Tactical combat now delegates rules interpretation to the active `RulesRuntime` while preserving the existing `CombatSystem` public surface.
- Action/damage resolution can expose machine-readable explanation traces for UI, narration, analytics, replay, and debugging consumers.
- `pytest-asyncio` is part of the development test dependencies and asyncio tests run in strict mode.

## 1.1.0 - 2026-08-16

### Added
- Opt-in SRD 5.2.1 rules foundation with official-source provenance and CC BY 4.0 attribution.
- Typed catalogs for skills, classes, species, backgrounds, and SRD feat identifiers.
- Official-source allowlist and asynchronous `fetch-srd` CLI command.
- Advantage/disadvantage-aware attacks, configurable armor calculation, damage traits, temporary hit points, and SRD-style death-saving-throw state.
- Structured SRD condition definitions and six-second round mapping that works with all engine timing modes.
- `rules_data` support in creator content packs for structured rules catalogs and deterministic ZIP round-trips.

### Changed
- Content pack hashing now canonicalizes sets and enums deterministically.
- README now distinguishes the generic engine from the separately licensed SRD integration.

## 1.0.0 - 2026-08-16

- Initial headless deterministic RPG platform release covering the v0.1 through v1.0 roadmap.
