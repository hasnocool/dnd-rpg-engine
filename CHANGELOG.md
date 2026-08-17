# Changelog

## 2.0.0 - 2026-08-16

### Added
- Typed SRD player-character runtime with builder, class/species/background validation, HP/hit dice, proficiency state, features, feats, spellcasting state, and advancement audit logs.
- Authoritative action economy with action, bonus action, reaction, movement, free interaction, explicit end-turn commands, scheduler-backed reaction windows, and legal-action queries.
- Stateful spellcasting that uses known/prepared spell sets, spell slots, concentration state, and SRD character resources instead of the generic energy pool.
- Short/long rest engine that advances living-world time and restores hit dice, spell slots, feature resources, HP, and death-save state according to recovery policy.
- XP and milestone level advancement with automatic HP/proficiency/progression updates and catalog-backed class feature/slot progression.
- Campaign runner connecting party configuration, map travel, living-world time, quest visit events, SRD encounter budgets, monster instantiation, encounter completion, and XP distribution.
- Campaign director boundary for deterministic campaign suggestions, encounter candidate proposals, NPC intent, and event-driven adaptation without direct world mutation.
- Portable checksum-verified character and campaign packages for save/export/import workflows.
- Multiplayer lobby snapshots, disconnect/reconnect state, event replay cursors, and party management.
- Creator Studio project model covering campaign templates, maps, encounters, NPCs, dialogues, quests, and rule documents.
- Dedicated browser Player UI backed by authoritative character-sheet/legal-action APIs.
- v2 playable-campaign bootstrap endpoint that creates a hosted SRD campaign, activates rules, builds the first character, configures the party, and returns its legal action state.

### Changed
- SRD characters can perform movement plus action/bonus-action work within one readiness turn; generic entities keep legacy one-command-per-readiness behavior.
- Campaign/package hashing canonicalizes sets and enums for stable cross-process checksums.
- API metadata/version is now 2.0.0.

## 1.0.0 - 2026-08-16

- Implemented deterministic command/event simulation core and async SQLite persistence.
- Added unified timeline scheduler supporting strict turn, timed turn, real time, real-time-with-pause, and hybrid modes.
- Added tactical actions, initiative, movement helpers, conditions, items, delayed spells/effects, and combat state.
- Added maps, exploration, dialogue, quests, NPC metadata, shops, living-world time, weather, factions, schedules, economy, and dynamic events.
- Added CLI, live text client, Textual TUI, REST API, WebSocket event stream, and browser client.
- Added Godot 4.7.x 2D/3D adapters and scene-binding schema.
- Added AI narrator boundary, memory/context, NPC personalities, encounter generation, and dynamic quest generation.
- Added authoritative multiplayer sessions, parties, spectators, client ownership, and campaign hosting.
- Added creator/mod SDK, content-pack validation/ZIP format, campaign templates, browser creator, community registry, marketplace metadata/install path, and campaign instantiation.
- Added tests, CI, Docker packaging, architecture documentation, and sample content.
