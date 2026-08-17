# Changelog

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
