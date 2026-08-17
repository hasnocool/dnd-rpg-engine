# Changelog

## 2.5.0 - 2026-08-16

### Added
- Async Python client SDK with authenticated provisioning, campaign handles, reliable command sequencing, event cursors, and HTTP transport abstraction.
- Buildable TypeScript client package with authenticated REST helpers and reliable WebSocket support.
- Godot `RPGClient.gd` reliable WebSocket helper for command acknowledgements and authoritative game events.
- v2.5 platform health/capability reporting while retaining the stable `/api/v1` wire namespace.
- End-to-end authenticated platform coverage spanning tenancy, campaign membership, character ownership, reliable retries, transport binding, and private Studio projects.

### Changed
- Package version advanced to `2.5.0`.
- Production host help/documentation now describes the complete v1.2-v2.5 advanced profile and authentication environment.

## 2.4.0 - 2026-08-16

### Added
- Persistent Campaign Director state for tension, unresolved story threads, scene repetition, faction pressure, and relationship-pressure hooks.
- Deterministic structured Director proposals with a bounded persistent proposal ledger.
- Governed proposal command attachment, approval, rejection, event observation, and management API.

### Security
- Director provider context deliberately omits writable engine/service objects.
- Candidate commands are parsed before storage and approved commands still execute through authenticated `CampaignSession.dispatch`, normal rules validation, and authoritative events.

## 2.3.0 - 2026-08-16

### Added
- Reliable multiplayer gateway with exact per-client sequences, command fingerprints, idempotent retry acknowledgements, gap detection, bounded receipt history, and command rate limiting.
- Presence/heartbeat state, event subscriptions, bounded backpressure primitives, and state coalescing.
- Authenticated reliable REST and WebSocket command channels.

### Security
- Reliable transports verify that a campaign client belongs to the same authenticated user/session as the bearer token.
- Authenticated production mode removes the legacy unauthenticated campaign WebSocket.

## 2.2.0 - 2026-08-16

### Added
- Deterministic Simulation Lab with independently derived seeds, bounded async concurrency, reproducible digests, aggregate metrics, and balance findings.
- Multi-variant comparison support.
- Campaign duel simulations that clone live actor snapshots and resolve combat through the normal `CombatSystem`/`RuleSet` without mutating the source campaign.
- Authorized simulation API.

## 2.1.0 - 2026-08-16

### Added
- Semantic-version constraints, package release metadata, deterministic dependency resolution, engine compatibility constraints, and content hashes.
- Deterministic package lockfiles and dependency-conflict reporting.
- Declared migration compatibility plus current/target upgrade planning.
- Tenant-aware package publication, resolution, release listing, and upgrade-plan APIs.

## 2.0.0 - 2026-08-16

### Added
- Distributed world partitions with explicit zones, adjacency/capacity constraints, and stable rendezvous worker placement.
- Two-phase, SHA-256-verified entity handoffs from source zone to destination zone.
- Atomic PostgreSQL zone ownership leases using database time, renewal/release, and placement claiming.
- Process-local SQLite lease fallback for development/testing.
- Distributed world, placement, lease, and handoff APIs.

### Changed
- Worker placement is now only a preference; an active lease is the single-writer authority for a distributed zone.

## 1.9.0 - 2026-08-16

### Added
- Authenticated user/session domain separated from transport client IDs.
- Organization/workspace/campaign/project tenant scopes with persistent resource ownership and ancestry.
- Resource-scoped RBAC for owners, admins, game masters, players, spectators, creators, and moderators.
- Signed expiring sessions, server-side revocation, session refresh/logout, and persistent security audit records.
- Authenticated secure campaign create/list/join APIs and campaign client-to-session binding.
- Project-scoped Creator Studio ownership/collaboration and tenant-aware publishing.

### Security
- Authenticated mode disables caller-asserted legacy campaign create/join/command/publish mutations.
- `X-RPG-Client-ID` is verified against the authenticated bearer session.
- Role/membership changes take effect without reissuing bearer tokens because effective permissions remain server-side.
- Bootstrap provisioning uses a separate server-side key and is documented as controlled provisioning rather than a public login mechanism.

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
