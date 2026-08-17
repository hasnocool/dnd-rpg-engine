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


## Post-1.0 platform milestones

- **v1.3 Character Runtime** — implemented: character builder, advancement, resources, turn economy, rests, spellcasting state, legal-action API.
- **v1.4 Campaign Runner** — implemented: party travel, living-world advancement, event-connected exploration/quests, catalog encounters, XP distribution.
- **v1.5 AI GM Orchestration** — implemented: mutation-free director suggestions, encounter proposals, NPC intent, adaptation counters.
- **v1.6 Player UX** — implemented: dedicated browser player/character sheet and authoritative action console.
- **v1.7 Portability** — implemented: checksum-verified character/campaign export and import.
- **v1.8 Multiplayer Continuity** — implemented: lobby state, reconnect, replay cursor, parties.
- **v1.9 Creator Studio** — implemented: campaign/map/encounter/NPC/dialogue/quest/rule project editing model and validation APIs.
- **v2.0 Playable Platform** — implemented: one-transaction playable campaign bootstrap integrating SRD rules, characters, party hosting and legal actions.
