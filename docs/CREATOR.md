# Creator platform and mod SDK

## Content pack

`ContentPack` is the portable extension unit. It contains:

- campaign templates
- creature templates
- actions
- conditions
- items
- spells
- maps
- dialogue graphs
- quests
- rule documents
- asset/scene binding strings

Each pack has a manifest with id, semantic version, engine compatibility, author, description, license, dependencies, and tags.

## Validation

The validator checks cross-references such as campaign start maps, creature actions, spell conditions, and map edges. ZIP import rejects unsafe paths and caps uncompressed size before parsing.

## Campaign templates

A campaign template contains an engine `GameConfig`, optional start map, initial entities, and initial flags. The public API can instantiate a validated template into a hosted campaign:

```text
POST /api/v1/creator/instantiate
```

## Browser creator

`/creator` exposes JSON editors for campaigns, creatures, maps, rules, spells, and quests, plus validation and publication to the community registry.

## Scene bindings

Logical content IDs remain independent from art assets. `adapters/bindings/scene-bindings.schema.json` maps engine entity/area/event IDs to local Godot scene paths or visual callbacks.
