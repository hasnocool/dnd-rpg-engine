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

## v1.9 Identity, RBAC + Multi-Tenancy — complete
- [x] authenticated users separated from transport clients
- [x] signed expiring server-side sessions with revocation
- [x] organizations and workspaces
- [x] organization/workspace/campaign/project memberships
- [x] owner/admin/game-master/player/spectator/creator/moderator roles
- [x] resource-scoped permission policy engine
- [x] persistent campaign/project tenant ancestry
- [x] character ownership authorization
- [x] authenticated secure campaign create/list/join APIs
- [x] authenticated client-to-session binding
- [x] Creator Studio project collaboration boundaries
- [x] audit records for security-sensitive operations
- [x] authenticated mode closes legacy caller-asserted command/join/publish paths

## v2.0 Distributed World Runtime — complete
- [x] world partitions and authoritative zone definitions
- [x] stable rendezvous-hash zone placement
- [x] PostgreSQL-backed atomic zone ownership leases
- [x] SQLite process-local development lease fallback
- [x] two-phase entity handoff (`PREPARED -> SOURCE_COMMITTED -> ACCEPTED`)
- [x] canonical entity/transfer hashes and verification
- [x] zone adjacency and capacity validation
- [x] persisted handoff records
- [x] distributed world/placement/lease/handoff APIs

## v2.1 Content Package Graph + Versioning — complete
- [x] semantic-version parser and constraints
- [x] package release metadata and content hashes
- [x] deterministic dependency resolver
- [x] engine compatibility constraints
- [x] deterministic package lockfiles
- [x] dependency-conflict detection
- [x] declared migration compatibility
- [x] upgrade planning
- [x] tenant-aware package publication and package APIs

## v2.2 Simulation Lab + Automated Balancing — complete
- [x] deterministic derived experiment seeds
- [x] async bounded-concurrency experiment runner
- [x] win-rate, duration, knockout, resource, and metric aggregation
- [x] reproducible experiment digests
- [x] configurable balance findings
- [x] multi-variant comparisons
- [x] rules-runtime-backed campaign duel simulation
- [x] campaign simulation authorization/API

## v2.3 Advanced Multiplayer Runtime — complete
- [x] exact per-client command sequences
- [x] retry-safe command acknowledgements/idempotency
- [x] command fingerprint mismatch protection
- [x] bounded retry receipt ledgers
- [x] application command rate limiting
- [x] presence/heartbeat tracking
- [x] event subscriptions
- [x] bounded backpressure buffers and state coalescing primitives
- [x] authenticated reliable REST command API
- [x] authenticated reliable WebSocket channel
- [x] production authenticated mode removes legacy unauthenticated WebSocket

## v2.4 AI Director / Campaign Brain — complete
- [x] persistent campaign-level Director state
- [x] unresolved story-thread tracking
- [x] tension, repetition, faction-pressure observations
- [x] deterministic structured proposals
- [x] bounded persistent proposal ledger
- [x] provider context without writable engine objects
- [x] command validation before proposal attachment
- [x] approval/rejection workflow
- [x] approved actions still dispatch through authenticated `CampaignSession`
- [x] Director management API and audit trail

## v2.5 Full Game Client SDK — complete
- [x] Python async client SDK
- [x] authenticated session bootstrap support
- [x] campaign create/join handles
- [x] automatic reliable command sequencing
- [x] event cursor tracking
- [x] TypeScript fetch/WebSocket SDK
- [x] buildable TypeScript package metadata/configuration
- [x] Godot reliable WebSocket client helper
- [x] stable `/api/v1` server namespace retained across package generation change
- [x] v2.5 platform health/capability reporting
- [x] end-to-end authenticated platform regression coverage
