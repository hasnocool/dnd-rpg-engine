# Unified Campaign Workbench — v3.0 to v3.9

The browser product is a thin presentation and orchestration layer over `WorldPlatformEngine`. It never becomes a second rules engine: combat, time, AI, movement, resources, inventory, visibility, scene lifecycle, and rules remain authoritative on the Python server.

## Product surfaces

```text
Campaign Library
      |
      +--> Creator Studio --------> ContentPack / release registry
      |
      +--> Session Lobby
                |
                +--> GM Console
                +--> Player View
                +--> Tactical Session
                +--> Character Workspace
                +--> Visual Runtime
                +--> Director / Knowledge
                +--> Automation
                +--> Analytics / Replay
                +--> Content Ecosystem
```

Creator projects and running campaign instances are intentionally separate. A Creator project is editable source; a validated `ContentPack` is distributable content; instantiation creates a persistent campaign instance.

## v3.x implementation map

### v3.0 — Persistent-world foundation

The existing v3.0 engine remains the foundation: shard registry, region routing, cross-shard messages, two-phase entity handoff, persistent distributed metadata, and the integrated `WorldPlatformEngine` profile.

### v3.1 — Unified Campaign Workbench

- Campaign Library and persistent campaign launcher.
- Separate GM and knowledge-scoped player experiences.
- World-state and event-history views.
- Scene lifecycle controls and AI Director inspection.
- WebSocket live events with server snapshots as canonical truth.

### v3.2 — Session Operations + Tactical Play

- Dedicated tactical workspace with an authoritative actor and target model.
- Coordinate/token visualization of returned entity positions.
- Server-submitted movement through normal `move` commands; SpatialAuthority validates the result.
- Registered action, spell, item, and executable-rule palettes sourced from the engine catalog.
- Encounter start/end controls for owners.
- Action-economy and spatial-space summaries where the active rules runtime exposes them.
- Character Workspace backed by character-lifecycle endpoints for progression, rests, equipment, and resources.

The map is a renderer. Grid placement and path previews are presentation only; trusted movement cost, occupancy, collision, terrain, and LOS remain server-owned.

### v3.3 — Full Creator Workbench

`ContentPack` now includes typed `SceneDefinition` objects. Creator Studio preserves the existing map/rules/campaign editors and adds an extended Full Pack editor for every previously unexposed content section:

- scenes and scene flow;
- actions, conditions, items;
- dialogue graphs;
- NPC profiles and personalities;
- encounters;
- shops and factions;
- NPC schedules and dynamic events;
- arbitrary `rules_data` catalogs;
- asset bindings/paths.

The scene editor visualizes `next_scene_ids` as a flow graph. Studio revisions, validation, export, ZIP round trips, and distribution publication continue to use the same typed server models.

### v3.4 — Advanced GM Intelligence

- Dedicated Director dashboard with utility, reasons, payload, campaign pressure, and decision history.
- Explicit Accept/Dismiss workflow.
- Accepted proposals are still bounded: the Director does not directly perform arbitrary world mutations. Safe proposal metadata such as `pressure_delta` may be applied, while concrete gameplay changes continue through ordinary authoritative commands.
- GM Knowledge Inspector compares world entity IDs with each player/human actor's remembered knowledge, facts, and observation timestamps.

### v3.5 — Replay + Campaign Analytics

- Server-side aggregation of persisted event counts, actor/target activity, common numeric totals, entity health, scene state, and Director pressure.
- Rules-related event inspection for explainability/debugging.
- Timeline scrubber over persisted authoritative campaign events.
- Event-sourcing journal discovery through the existing `event_source.entry` persistence namespace.
- State rewind/branch capability is advertised only when EventSourcedEngine journal entries actually exist; the UI does not pretend that ordinary event history is a state snapshot.

### v3.6 — Visual World Runtime

- Dedicated Runtime Snapshot view backed by `/runtime`.
- Owner canonical snapshots and player actor-scoped/redacted snapshots use the same renderer.
- Visual bindings, facts, sequence, active map, and snapshot hash are inspectable.
- The tactical/visual renderer can hide presentation grid/labels without changing game truth.
- Browser/Godot continue sharing the transport-neutral `RuntimeSnapshot` / `VisualBinding` contract.

### v3.7 — Campaign Automation

- Automation observability dashboard surfaces installed NPC schedules and dynamic-event definitions from campaign content packs.
- World/simulation clock and active-scene context are displayed alongside definitions.
- Authoring remains in Creator Studio, and trigger evaluation remains in the living-world engine. The browser does not execute schedule or dynamic-event predicates locally.

### v3.8 — Multiplayer Experience

- Session Lobby shows clients, server-resolved roles, actor ownership, scene readiness, and session time.
- Owner-controlled party creation and party membership operations expose the existing authoritative `CampaignSession` model.
- Player joins continue to sanitize requested ownership against server-owned entity `owner_id` values.
- Existing reconnect/resume infrastructure remains the persistence/reconnection layer.

### v3.9 — Content Ecosystem

- Installed content-pack inventory with manifest/dependency/section summaries.
- Distribution release browser.
- Dependency-lock inspection.
- Interactive dependency resolver using `/api/v1/distribution/resolve`.
- Creator publication remains the source of marketplace/distribution releases.

## New workbench API

The v3.x browser uses a small aggregation router under:

```text
/api/v1/campaigns/{campaign_id}/workbench/session
/api/v1/campaigns/{campaign_id}/workbench/parties
/api/v1/campaigns/{campaign_id}/workbench/catalog
/api/v1/campaigns/{campaign_id}/workbench/tactical
/api/v1/campaigns/{campaign_id}/workbench/analytics
/api/v1/campaigns/{campaign_id}/workbench/knowledge
/api/v1/campaigns/{campaign_id}/workbench/replay
/api/v1/campaigns/{campaign_id}/workbench/content
/api/v1/campaigns/{campaign_id}/workbench/director/{proposal_id}/accept
/api/v1/campaigns/{campaign_id}/workbench/director/{proposal_id}/dismiss
```

These endpoints aggregate existing engine services for presentation; they do not introduce a parallel state store.

## Authority boundaries

- Owners may request omniscient state and GM-only diagnostics.
- Players receive actor-owned / knowledge-scoped projections.
- Clients submit normal commands and lifecycle requests.
- The server resolves combat, movement, rules, resource costs, timing, visibility, AI, and scene state.
- WebSocket messages are notifications; a server snapshot is canonical after reconnect or disagreement.
- AI Director proposals are advisory until explicitly accepted by an owner or translated into an authoritative action.
- Replay UI never reconstructs hidden state from redacted player data.

## Campaign creation to play flow

```text
1. Creator Studio (optional)
   -> build maps/scenes/content/rules
   -> validate
   -> publish/export

2. Campaign Library
   -> create blank campaign
      OR instantiate a campaign template/content pack

3. Session Lobby
   -> GM joins as stored owner
   -> players join
   -> server resolves owned actors
   -> parties are assigned

4. Start / activate scene
   -> exploration / dialogue / travel / encounter / downtime / settlement / dungeon

5. Live play
   -> GM Console for orchestration
   -> Player View for knowledge-scoped play
   -> Tactical Workspace during encounters
   -> Character Workspace for lifecycle state

6. Operations
   -> Director / Knowledge diagnostics
   -> automation observability
   -> analytics / replay
   -> content/dependency management

7. End / continue
   -> authoritative campaign state + persisted events remain available
   -> reconnect/resume can restore clients without client-side simulation
```
