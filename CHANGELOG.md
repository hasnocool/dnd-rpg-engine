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
