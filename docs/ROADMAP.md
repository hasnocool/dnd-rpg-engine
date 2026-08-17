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
