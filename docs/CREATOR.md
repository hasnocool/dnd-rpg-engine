# Creator Studio and content platform

Creator Studio is the reusable **source-authoring** surface for the RPG platform. It is intentionally separate from the v4.0 Hero & NPC Workshop: Studio edits distributable content and templates, while `/hero` edits actors that already exist inside a running campaign.

## ContentPack

`ContentPack` is the portable extension unit. The current Studio exposes the full typed pack surface, including:

- campaign templates;
- creatures;
- actions;
- conditions;
- items;
- spells;
- maps;
- typed scenes and scene-flow links;
- dialogue graphs;
- quests/objectives;
- NPC profiles;
- personalities;
- encounters;
- shops;
- factions;
- NPC schedules;
- dynamic events;
- executable rule documents/graphs;
- structured `rules_data` catalogs;
- asset and scene binding paths.

Each pack has a manifest with ID, semantic version, engine compatibility, author, description, license, dependencies, and tags.

## Studio projects and revisions

Studio projects are persistent editable sources. Saving creates revision snapshots so authors can inspect history and restore an older revision as a new revision without rewriting history.

The standard flow is:

```text
project source
   ↓ edit
revision snapshot
   ↓ validate
ContentValidator
   ↓ export/publish
ContentPack / ZIP / marketplace / distribution registry
```

A running campaign is not itself a Studio project. Instantiating a validated campaign template or installing a pack creates campaign-instance state that is subsequently operated through the Workbench and actor tools.

## Visual authoring

The browser Studio at `/creator` includes:

- SVG world-map editing with draggable nodes and typed connections;
- typed scene editing and a visual scene-flow graph based on `next_scene_ids`;
- executable rule-graph authoring with compiler validation and graph-hash feedback;
- structured editors for creatures, spells, quests, campaigns, and the rest of the `ContentPack` sections;
- validation, revision, export, and publication workflows.

Executable rules compile to the bounded deterministic rule IR. Studio content cannot introduce arbitrary Python, Lua, JavaScript, `eval`, `exec`, filesystem, process, import, or network access.

## Validation

The validator checks cross-references across the pack, including campaign start maps, creature actions, spell conditions, map edges, scene links, and other typed references. ZIP import rejects unsafe paths and caps uncompressed size before parsing.

Validation is shared with runtime content loading, so a pack cannot bypass runtime checks simply because it was authored through the browser.

## Campaign templates

A campaign template contains an engine `GameConfig`, optional start map, initial entities, and initial flags. The public API can instantiate a validated template into a hosted campaign:

```text
POST /api/v1/creator/instantiate
```

After instantiation, the campaign is managed through the Campaign Workbench and authoritative campaign APIs.

## Hero & NPC Workshop boundary

`/hero` is the campaign-instance actor surface introduced by the v4.0 milestone.

Use Creator Studio when you want to define reusable NPC templates, personalities, dialogue, factions, schedules, encounters, equipment, spells, rules, or campaign templates. Use the Hero & NPC Workshop when you want to create or edit a specific hero or NPC in a particular running campaign.

```text
Creator Studio (/creator)
      ↓ validate/publish
ContentPack / campaign template
      ↓ instantiate/install
Running campaign
      ├── Campaign Workbench (/)
      └── Hero & NPC Workshop (/hero)
```

The Hero Creator uses `CharacterLifecycle` for construction and advancement. The NPC Manager uses owner-only NPC APIs and synchronizes `NPCProfile` changes with live entities. Neither browser surface is a second rules engine.

## Distribution

Creator publication can register content in both the marketplace-facing registry and the semantic-version content-distribution index. Distribution metadata can include engine-version constraints, dependencies, content hashes, lock hashes, and signatures.

## Scene bindings

Logical content IDs remain independent from art assets. `adapters/bindings/scene-bindings.schema.json` maps engine entity/area/event IDs to local Godot scene paths or visual callbacks. Runtime synchronization can expose visual bindings without moving presentation authority into the simulation core.
