# v4.0 Hero & NPC Experience

The v4.0 product milestone makes heroes and NPCs first-class **campaign-instance actors** in the browser workflow.

The package version is still `3.9.0`; v4.0 is an implemented roadmap milestone on `main` pending a deliberate release/version bump.

## Why a separate actor workshop?

Before v4.0, the engine already had a deep `CharacterLifecycle`, reusable NPC content models, Creator Studio, and campaign Workbench surfaces. What was missing was a dedicated workflow for a GM to create and maintain the actual actors used by a running campaign.

The three browser surfaces now have distinct responsibilities:

```text
/creator   reusable source content
     │     ContentPack / templates / maps / scenes / rules / NPC definitions
     ▼
/          campaign operations and live play
     │
     └──── /hero   campaign-instance heroes and NPCs
```

A campaign actor is not automatically reusable content, and editing a reusable NPC definition should not silently rewrite a live NPC in an existing campaign.

## Hero Creator

`/hero` exposes a dedicated Hero Creator backed by `CharacterLifecycle`.

### Creation workflow

1. Select a hosted campaign.
2. Authenticate with the campaign owner client identity.
3. Load the active lifecycle catalog.
4. Choose the character build data.
5. Submit the build to the authoritative character creation API.
6. The engine constructs the character and persists campaign state.

The build/workshop supports the active lifecycle data for:

- name and owner;
- class and starting level;
- species/ancestry;
- background;
- XP;
- six ability scores;
- tags;
- starting equipment;
- appearance and portrait/presentation metadata.

The visible catalog comes from the active engine lifecycle rather than a hard-coded browser ruleset. The browser can therefore present classes, equipment, rest profiles, and advancement data exposed by the campaign's active lifecycle implementation.

### Existing heroes

The Workshop can browse and filter existing lifecycle-backed characters and open them for inspection/editing.

Safe character editing is deliberately narrower than character progression. The profile edit API can change fields such as:

- name;
- species/ancestry identifier;
- background identifier;
- base ability scores;
- tags;
- appearance/presentation metadata.

It does **not** provide a direct browser shortcut for trusted progression state.

### Progression authority

These remain authoritative lifecycle operations:

```text
XP award
level-up
rest
resource spend/restore
equip/unequip
class-resource behavior
action-economy reset/recovery
```

The client submits lifecycle requests; `CharacterLifecycle`, the campaign session, and the active rules runtime resolve the results.

## NPC Manager

The v4.0 NPC Manager uses owner-only APIs over first-class `NPCProfile` data.

### Supported workflow

- list/browse/filter live campaign NPCs;
- create an NPC;
- inspect one NPC;
- edit an NPC;
- remove an NPC.

A managed NPC can include:

- identity/name and role;
- controller/AI profile;
- six ability scores;
- HP/resources;
- map/position;
- tags;
- appearance and portrait metadata;
- knowledge tags/metadata;
- faction ID;
- personality ID;
- dialogue graph ID;
- shop ID;
- schedule ID.

### Profile/entity synchronization

NPC state exists in two useful representations:

```text
NPCProfile
   │ authored/relationship-oriented NPC data
   │
   └──── synchronized by API mutations ────► live Entity
                                             stats/resources/position/components/tags
```

Create/update/delete operations keep the registered profile and live NPC entity aligned. Profile relationships are reflected into live entity components where appropriate.

Schedule changes are also synchronized with the living-world schedule service. An unknown schedule is rejected rather than leaving a dangling assignment.

### NPC authority

NPC CRUD requires the campaign owner. The browser does not directly edit engine memory structures.

The API emits authoritative NPC lifecycle events (`npc.created`, `npc.updated`, `npc.removed`) and persists the resulting campaign state.

## API surface

### Character lifecycle

```text
GET    /api/v1/campaigns/{campaign_id}/characters/catalog
GET    /api/v1/campaigns/{campaign_id}/characters
POST   /api/v1/campaigns/{campaign_id}/characters
GET    /api/v1/campaigns/{campaign_id}/characters/{actor_id}
PATCH  /api/v1/campaigns/{campaign_id}/characters/{actor_id}
POST   /api/v1/campaigns/{campaign_id}/characters/{actor_id}/xp
POST   /api/v1/campaigns/{campaign_id}/characters/{actor_id}/level-up
POST   /api/v1/campaigns/{campaign_id}/characters/{actor_id}/rest
POST   /api/v1/campaigns/{campaign_id}/characters/{actor_id}/equip
POST   /api/v1/campaigns/{campaign_id}/characters/{actor_id}/unequip
POST   /api/v1/campaigns/{campaign_id}/characters/{actor_id}/resources/spend
POST   /api/v1/campaigns/{campaign_id}/characters/{actor_id}/resources/restore
```

### NPC management

```text
GET    /api/v1/campaigns/{campaign_id}/npcs
POST   /api/v1/campaigns/{campaign_id}/npcs
GET    /api/v1/campaigns/{campaign_id}/npcs/{actor_id}
PATCH  /api/v1/campaigns/{campaign_id}/npcs/{actor_id}
DELETE /api/v1/campaigns/{campaign_id}/npcs/{actor_id}
```

## Workbench integration

The Campaign Workbench exposes Hero Creator navigation and a `Create Character / Hero` command-palette action. The actor Workshop remains a separate focused page so campaign operations, content authoring, and actor administration do not collapse into one overloaded interface.

Recommended workflow:

```text
1. /creator
   author reusable campaign/content/NPC definitions

2. /
   create or instantiate campaign

3. /hero
   create player heroes
   add or customize campaign-instance NPCs

4. /
   assign ownership/parties
   activate scenes
   play through GM/player/tactical surfaces

5. /hero as needed
   owner-managed actor administration
```

## Security and authority summary

- `/hero` is a presentation/orchestration client.
- Hero creation delegates to `CharacterLifecycle`.
- Character profile edits cannot directly rewrite level/XP/equipment/resource authority.
- NPC mutations are owner-only.
- NPC schedules are validated server-side.
- NPC profile/entity synchronization happens on the authoritative engine.
- Combat, movement, visibility, AI, timing, progression, resources, and rules remain server-owned.
- Creator Studio remains the reusable content source; the actor Workshop manages campaign instances.

## Related documentation

- `WORKBENCH.md` — campaign creation, session operations, and live play.
- `CREATOR.md` — reusable content and Studio project workflow.
- `API.md` — public route groups and identity/authority rules.
- `ROADMAP.md` — milestone status through v4.0.
- `ARCHITECTURE.md` — engine profiles and authoritative state flow.
