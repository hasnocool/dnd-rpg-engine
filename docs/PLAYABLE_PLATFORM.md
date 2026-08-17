# Playable RPG platform (v1.3 → v2.0)

Version 2.0 turns the generic simulation + SRD catalog into an end-to-end playable platform while retaining the existing command/event architecture.

## v1.3 — Character and rules execution runtime

`dnd_rpg_engine.characters` stores typed character state inside the existing `Entity.components` persistence envelope, so older saves/frontends remain compatible.

Character state includes:

- class, subclass, species, background, level and XP;
- class feature IDs and feat IDs;
- skill proficiencies and expertise;
- hit-die pools;
- typed limited-use feature resources with turn/round/short-rest/long-rest/manual recovery policies;
- known/prepared spells, spell slots and concentration state;
- a per-turn action economy ledger;
- advancement audit history.

The character builder derives HP, movement, AC baseline, background skills, origin feat, proficiency metadata, spellcasting ability and catalog-backed progression.

### Turn economy

The authoritative `TurnState` tracks:

- `action_available`
- `bonus_action_available`
- `reaction_available`
- `movement_max`
- `movement_remaining`
- `free_interactions`
- `round_index`

Movement no longer implicitly ends an SRD character turn. Primary and bonus actions consume their own resources, and `end_turn` closes the ledger. Generic non-character entities retain the legacy scheduler behavior.

`GET /api/v1/campaigns/{campaign_id}/characters/{actor_id}/actions` is the canonical answer to “what can this actor legally do now?” Clients should not reproduce these rules locally.

### Spellcasting

SRD characters use spellcasting state rather than the generic `energy` resource. A cast is legal only when the character has a spellcasting ability, the spell is known/prepared, a slot is available when required, and the corresponding action/bonus-action resource remains. Successful casts spend the slot and update concentration state.

### Rests and advancement

`rest` commands support short and long rests. Rest duration advances the living-world clock and therefore weather, schedules and dynamic events remain part of campaign time. Recovery policies restore the appropriate feature resources; long rests restore slots and HP while hit-die recovery is tracked explicitly.

XP awards and milestone level-ups update level, proficiency metadata, hit dice, max HP, class features and spell-slot progression. Every advancement appends an audit entry and emits authoritative events through API workflows.

## v1.4 — Campaign runner

`CampaignRunner` connects lower-level systems into a repeatable campaign loop:

```text
exploration → travel → location events → social/quest state
     ↑                                  ↓
 rest ← rewards/advancement ← encounter resolution
```

Party travel uses registered map edges, advances world time, moves the configured party, records exploration visits, and emits `location.visited` so quest objectives progress through the normal event pipeline.

When an offline SRD catalog is bound, the runner can construct XP-budgeted encounters, instantiate catalog monsters as authoritative entities, start initiative, finish encounters, calculate defeated XP and distribute advancement to the party.

## v1.5 — AI campaign director

`CampaignDirector` is a proposal boundary, not a mutation boundary. It can:

- recommend exploration/rest/encounter continuation based on authoritative state;
- request deterministic encounter candidates from the SRD catalog;
- derive NPC intent from registered NPC profiles plus social state;
- maintain small event-driven pressure/social-momentum counters.

All suggestions still require normal commands or campaign-runner calls to mutate state, preserving the AI Game Master safety boundary.

## v1.6 — Player UX

`/play` is a dedicated browser player surface. It can bootstrap a campaign, show the complete character state, display authoritative legal actions, issue end-turn/rest commands and follow the event log. The older dashboard remains available for low-level simulation inspection.

The Player UI intentionally consumes server APIs rather than implementing rules in JavaScript.

## v1.7 — Portable characters and campaigns

`CharacterPackage` and `CampaignPackage` provide JSON-portable save formats with canonical SHA-256 checksums. Sets and enums are canonicalized so hashes remain stable across JSON serialization and process boundaries.

API routes support campaign export/import and character export/import. Imported characters receive a fresh entity ID to avoid collisions while retaining their authoritative character state.

## v1.8 — Multiplayer continuity

Campaign sessions now track connection state separately from identity. A disconnect does not destroy the registered client identity. The same client/user pair can reconnect, retrieve a lobby snapshot, and replay authoritative events from a cursor. Parties remain server-owned collections of users and actor IDs.

## v1.9 — Creator Studio

`CreatorProject` provides a focused editing model over a `ContentPack`, covering:

- campaign templates;
- maps;
- encounter templates;
- NPC profiles;
- dialogues;
- quests;
- rule documents.

Studio inspect/apply endpoints reuse normal content validation and deterministic content hashes, so edits remain compatible with the existing mod/marketplace system.

## v2.0 — End-to-end bootstrap

`POST /api/v2/playable-campaigns` creates a playable campaign in one transaction:

1. create and persist the campaign;
2. bind the optional offline SRD catalog;
3. install the SRD foundation content pack;
4. activate SRD rules;
5. register simple compiled SRD spells when a catalog is configured;
6. build the first player character;
7. configure that character as the campaign party;
8. host the multiplayer session and owner client;
9. start realtime/broadcast services when the selected timing policy needs them;
10. return campaign state, character sheet and legal actions.

This endpoint is the reference integration path for future downloadable clients and richer Godot/browser frontends.
