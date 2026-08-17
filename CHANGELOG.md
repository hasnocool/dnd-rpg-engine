# Changelog

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
- Typed `RulesRuntime` boundary with ruleset capabilities, typed roll/attack/damage contexts and outcomes, explainable modifier traces, effect triggers, reaction opportunities, and per-actor action economy.
- Deterministic effect pipeline supporting stacked timed effects, flat/multiplicative/min/max modifiers, advantage/disadvantage sources, and trigger-scoped operations.
- Rules-runtime registry and compatibility routing through `CombatSystem`, allowing rulesets to replace mechanics without changing engine/front-end contracts.
- SRD 5.2.1 runtime specialization for proficiency, zero-HP transitions, and death-saving throws while retaining the generic engine compatibility path.
- Deterministic event-sourcing journal with canonical state hashing, SHA-256 hash chaining, replay, rewind, branch creation, command-ID idempotency, and live-state verification.
- `EventSourcedEngine` compatibility wrapper that can journal the existing `GameEngine` without changing its async command/event interface.
- Authoritative spatial subsystem with graph, grid, continuous 2D, and continuous 3D spaces; weighted pathfinding, occupancy/capacity, collision, terrain costs, movement budgets, line-of-sight, and cover queries.
- Intelligent living-actor subsystem with authoritative perception snapshots, goals, utility scoring, tactical action planning, behavior-tree primitives, schedule-aware intent, and persistent component-backed memories.
- Regression suites for rules/effects, event sourcing, spatial authority, and intelligent actor planning across the supported Python matrix.

### Changed
- Tactical combat now delegates rules interpretation to the active `RulesRuntime` while preserving the existing `CombatSystem` public surface.
- Action/damage resolution can expose machine-readable explanation traces for UI, narration, analytics, replay, and debugging consumers.
- `pytest-asyncio` is part of the development test dependencies and asyncio tests run in strict mode.

## 1.2.0 - 2026-08-16

### Added
- Compile-once SRD 5.2.1 pipeline that produces an offline normalized SQLite catalog from the official PDF.
- Typed catalogs for spells, class features/progressions, subclasses, feats, non-weapon magic-item metadata, monster stat data, travel/environment rules, and encounter budgets.
- `SRDCatalogStore` with non-blocking SQLite access, bounded search, section counts, and persisted compilation provenance.
- Runtime adapters that register mechanically simple compiled spells and instantiate monster stat records as normal engine entities.
- SRD travel/terrain/environment helpers and deterministic encounter XP budget/candidate tooling.
- Read-only SRD REST endpoints and CLI commands for compilation, catalog inspection/search, and encounter budgets.
- Compiler/store/runtime/toolbox/API regression coverage.

### Changed
- `SpellDefinition` now carries level, school, class, save ability, Concentration, Ritual, and component metadata.
- The SRD pack advertises the external compiled-catalog schema rather than embedding the large catalog into every campaign save.
- Long-form source prose stays out of the runtime catalog; generated records retain source-page/hash provenance for auditability.

### Deliberate exclusions
- This build does not compile weapon-specific equipment/mastery records, monster action/gear prose, detailed hazardous-substance content, or long-form SRD descriptive text.

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
