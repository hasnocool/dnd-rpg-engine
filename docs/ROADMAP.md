# Roadmap status

## v0.1 Core Simulation — complete
- [x] entities/components
- [x] commands
- [x] events
- [x] deterministic dice streams
- [x] stats/checks
- [x] async SQLite persistence and snapshots

## v0.2 Tactical RPG — complete
- [x] combat resolution
- [x] timeline actions
- [x] movement/path/LOS helpers
- [x] deterministic initiative scheduling
- [x] conditions and periodic effects
- [x] items/inventory
- [x] delayed spell resolution

## v0.3 Adventure Engine — complete
- [x] graph maps
- [x] exploration/discoveries
- [x] dialogue graphs and requirements
- [x] event-driven quests
- [x] NPC profiles
- [x] shops

## v0.4 Living World — complete
- [x] simulation/world clocks
- [x] weather transitions
- [x] factions/reputation
- [x] NPC schedules
- [x] supply/demand economy
- [x] declarative dynamic events

## v0.5 Multiple Frontends — complete
- [x] CLI
- [x] live text client
- [x] Textual TUI
- [x] REST API
- [x] WebSocket events/commands
- [x] browser client

## v0.6 Visual Game Adapters — complete
- [x] Godot 2D bridge/binding
- [x] Godot 3D bridge/binding
- [x] scene/asset binding schema

## v0.7 AI Game Master — complete
- [x] authoritative-event narrator boundary
- [x] NPC personality models
- [x] procedural encounter generator
- [x] generated quest system
- [x] bounded memory/context

## v0.8 Multiplayer — complete
- [x] authoritative campaign sessions
- [x] parties
- [x] spectators
- [x] actor ownership
- [x] campaign hosting

## v0.9 Creator Platform — complete
- [x] campaign templates/editor
- [x] map editor data model
- [x] creature editor data model
- [x] safe rules editor knobs
- [x] mod SDK/validation/ZIP format
- [x] campaign instantiation from packs

## v1.0 RPG Platform — complete
- [x] persisted hosted campaigns
- [x] community content registry
- [x] marketplace metadata/install flow
- [x] packaged CLI/TUI/browser/Godot clients
- [x] public versioned engine API/OpenAPI

## v1.1 SRD 5.2.1 Foundation — complete
- [x] opt-in SRD 5.2.1 provenance/licensing boundary
- [x] skill/class/species/background/feat catalogs
- [x] proficiency and spellcasting helpers
- [x] advantage/disadvantage-aware attacks
- [x] armor and damage traits
- [x] temporary hit points and death-saving-throw state
- [x] structured conditions and six-second round mapping

## v1.2 Rules Runtime + Effect Pipeline — complete
- [x] typed `RulesRuntime`
- [x] typed roll/attack/damage contexts and outcomes
- [x] explainable modifier traces
- [x] deterministic effects and trigger hooks
- [x] reaction opportunities
- [x] per-actor action economy
- [x] ruleset capability declarations
- [x] `CombatSystem` runtime delegation
- [x] SRD-specific runtime specialization

## v1.3 Deterministic Event Sourcing — complete
- [x] deterministic state patches
- [x] canonical SHA-256 state hashes
- [x] hash-chained journal entries
- [x] replay and rewind
- [x] branching campaign journals
- [x] command-ID idempotency ledger
- [x] live-state verification
- [x] async persistence bridge for journal entries

## v1.4 Spatial Authority — complete
- [x] graph spaces with capacity and weighted routing
- [x] grid spaces with terrain and occupancy
- [x] continuous 2D/3D spaces
- [x] collision and bounds checks
- [x] authoritative movement budgets
- [x] A*/Dijkstra pathfinding
- [x] line-of-sight queries
- [x] cover queries
- [x] terrain movement costs

## v1.5 Intelligent Living Actors — complete
- [x] perception snapshots
- [x] actor goals
- [x] utility scoring
- [x] behavior-tree primitives
- [x] tactical planning to validated `GameCommand`s
- [x] schedule-aware intent
- [x] persistent component-backed memories
- [x] authoritative-state-only observation boundary

## v1.6 Character Lifecycle — complete
- [x] ruleset-neutral character builder
- [x] multiclass-compatible progression state
- [x] XP and milestone advancement tracks
- [x] level-up outcomes, hit-point growth, features, and ability-point grants
- [x] ruleset-owned class resources
- [x] short- and long-rest recovery profiles
- [x] equipment slots, displacement, attunement, and aggregate modifiers
- [x] lifecycle state stored in normal entity components for replay/save compatibility
- [x] SRD class-catalog adapter and lifecycle-aware proficiency
- [x] authoritative lifecycle commands/events and REST endpoints

## v1.7 Production Campaign Hosting — complete
- [x] async PostgreSQL persistence backend
- [x] ordered schema migrations
- [x] SQLite-compatible persistence contract
- [x] simulation-worker registry and heartbeats
- [x] PostgreSQL campaign leases preventing duplicate simulation ownership
- [x] rendezvous-hash campaign placement with stable scale-out behavior
- [x] capacity-aware campaign workers
- [x] opaque reconnect/resume tickets stored by hash
- [x] reconnect token rotation and event-sequence checkpoints
- [x] missed-event replay after reconnect
- [x] production host and worker CLI entrypoints

## v1.8 Creator Studio — complete
- [x] persistent typed Studio projects
- [x] immutable revision snapshots and restore-as-new-revision workflow
- [x] visual SVG world-map graph editor
- [x] draggable map nodes and typed edge creation
- [x] structured creature editor
- [x] structured spell editor
- [x] structured quest/objective editor
- [x] structured rules editor
- [x] structured campaign-template editor
- [x] direct validation through the runtime `ContentValidator`
- [x] validated export and marketplace publishing
- [x] v1.8 platform application factory and health/version reporting
- [x] main `rpg-engine serve` command launches the complete Studio-capable platform

## v1.9 Executable Content Compiler + Rules Graph — complete
- [x] bounded declarative executable-rule intermediate representation
- [x] deterministic `RuleCompiler` with node/effect budgets and cross-reference validation
- [x] canonical SHA-256 compiled graph hashes and provenance metadata
- [x] roll, damage, healing, resource, effect, reaction, condition-flow, state, emit, and stop operations
- [x] allowlisted state mutation paths; no `eval`, `exec`, Python, Lua, or arbitrary scripts
- [x] deterministic execution-step budget and graph-hash verification
- [x] RulesRuntime-backed execution and explainable per-node traces
- [x] `RuleDocument.graph` content-pack/ZIP/hash integration
- [x] authoritative `rule.execute` command integration in `WorldPlatformEngine`
- [x] Creator Studio compiler-validation endpoint
- [x] visual executable rule-graph editor with nodes, branches, arguments, entry point, capabilities, and compile/save feedback

## v2.0 Campaign Orchestrator — complete
- [x] typed exploration/encounter/dialogue/travel/downtime/settlement/dungeon/custom scenes
- [x] authoritative unloaded/loading/active/suspended/resolved/archived lifecycle
- [x] validated scene transitions and exclusive scene activation
- [x] scene state persisted into campaign metadata
- [x] active-scene and preload-driven entity streaming sets
- [x] next-scene candidates and streamed-state projections
- [x] scene registration/transition REST APIs

## v2.1 Simulation Lab — complete
- [x] deterministic seed matrices
- [x] bounded concurrent scenario execution
- [x] sample/outcome/event-count capture
- [x] mean/median/stdev/min/max/p10/p90 metric summaries
- [x] outcome rates and report comparison deltas
- [x] retained or aggregate-only run modes
- [x] regression tests proving stable aggregation

## v2.2 Advanced AI Director — complete
- [x] campaign-scale observation snapshot
- [x] deterministic ranked pacing/encounter/quest/faction/world/downtime proposals
- [x] explainable utility/reason output
- [x] resource- and pressure-aware recovery/decompression behavior
- [x] faction/world background motion proposals
- [x] proposal-only authority boundary; director never directly mutates game truth
- [x] owner-only director proposal API

## v2.3 Perception + Knowledge Authority — complete
- [x] per-actor known entities, observed-at timestamps, facts, confidence, sources, tags, and expiry
- [x] perception ingestion into persistent actor components
- [x] remembered entity snapshots rather than stale access to live hidden truth
- [x] public-component filtering for observed non-self entities
- [x] knowledge-scoped actor views
- [x] owner-only omniscient runtime views
- [x] player views limited to owned actors
- [x] knowledge-scoped campaign GET/event history/WebSocket replacement for the v3 world profile
- [x] spectator/public-shell behavior instead of omniscient state

## v2.4 Visual Runtime SDK — complete
- [x] deterministic full runtime snapshots
- [x] KnowledgeView-derived redacted snapshots
- [x] entity/scene/sprite/model/animation visual bindings
- [x] hash-verified runtime deltas and client sync cursors
- [x] deterministic add/replace/remove delta operations
- [x] delta replay with base/target hash validation
- [x] transport-neutral protocol suitable for browser, Godot, and remote clients

## v2.5 Content Distribution Platform — complete
- [x] semantic-version package metadata and version constraints
- [x] dependency graph resolution and cycle detection
- [x] engine-version compatibility checks
- [x] deterministic topological install order
- [x] package content hashes and dependency lock hashes
- [x] signed release metadata with built-in HMAC-SHA256 private-registry signer interface
- [x] upgrade planning
- [x] persistent release and lock registry over SQLite/PostgreSQL JSON storage
- [x] content distribution REST API
- [x] Creator Studio publish-to-marketplace-and-distribution flow

## v3.0 Massively Persistent Worlds — foundation complete
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

The v3.0 milestone establishes the deterministic persistence, routing, handoff, and authority primitives required to scale into multiple simulation processes. Production deployments can layer transport/service-discovery infrastructure around these interfaces without changing campaign, rules, or client contracts.
