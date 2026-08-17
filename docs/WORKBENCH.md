# Unified Campaign Workbench

The browser client is organized around three user journeys rather than one development dashboard:

1. **Campaign Library** — find, create, and launch persistent campaigns.
2. **Creator Studio** — author campaign templates, maps, creatures, rules, spells, quests, and distributable content packs.
3. **Live Session** — run a campaign through separate GM and player experiences backed by the authoritative engine.

## Implemented browser views

### Campaign Library

The root route (`/`) opens the campaign library. It reads `/api/v1/campaigns`, shows persisted campaigns, surfaces the local marketplace registry, and provides a campaign creation flow.

Campaign creation collects the campaign name, owner identity, deterministic seed, time mode, decision timeout, and time scale. Creation uses the existing campaign API and then applies the requested time scale through the timing endpoint.

### GM Console

The GM console is an omniscient operational view for an authenticated campaign owner. It provides:

- authoritative campaign/world time and weather;
- active map and streamed actors;
- actor readiness/timeline state;
- campaign-orchestrator scene runtime and scene transitions;
- actor/scene inspection;
- basic command dispatch and manual clock advancement;
- AI Director proposal inspection;
- live authoritative WebSocket events;
- persisted event history.

Opening an existing campaign asks for the stored owner identity. The multiplayer session layer remains the authorization boundary and only promotes the stored owner to the owner role.

### Player View

The player view joins with a player identity and relies on the engine to resolve actor ownership. It requests per-actor runtime snapshots and uses the knowledge-scoped campaign, event, and WebSocket routes supplied by the world-platform profile.

The browser does not attempt to reconstruct hidden state locally. It renders only entities contained in the server response and sends player commands back to the authoritative server.

### World State

The world-state explorer exposes the currently returned entity projection and campaign metadata for debugging and GM inspection.

### Event History

The campaign journal reads persisted events from the campaign event API. Under the world-platform profile, the same route remains knowledge-scoped for non-owner clients.

## Campaign-to-play flow

```text
Campaign Library
      |
      +--> New campaign -----------------------------+
      |                                              |
      +--> Existing campaign                         |
                                                     v
                                              Join campaign
                                               /          \
                                              /            \
                                             v              v
                                      GM Console        Player View
                                             |              |
                                             +------+-------+
                                                    |
                                                    v
                                             authoritative
                                               commands
                                                    |
                                                    v
                                            WorldPlatformEngine
                                                    |
                              +---------------------+------------------+
                              |                     |                  |
                              v                     v                  v
                         event journal       knowledge views     scene runtime
                              |                     |                  |
                              +---------------------+------------------+
                                                    |
                                                    v
                                               browser sync
```

## Creator-to-campaign flow

Creator Studio remains the source-authoring surface. A Studio project produces a validated `ContentPack`; campaign templates inside the pack can then be instantiated into persistent campaign instances. Editing a Creator project therefore remains separate from mutating a running campaign.

Recommended authoring progression:

```text
Project metadata
      -> world/maps
      -> campaign template
      -> creatures / spells / quests / executable rules
      -> validation
      -> export or publish
      -> instantiate campaign
      -> join live session
```

## Authority rules

The Workbench intentionally keeps presentation logic thin:

- clients never calculate trusted combat/rule outcomes;
- clients submit `GameCommand` payloads;
- the server controls time, actions, AI, movement, resources, inventory, and rules;
- owners may receive omniscient state;
- players receive knowledge-scoped state and events;
- WebSocket events are treated as notifications, while server snapshots remain canonical.

## Follow-up UI expansion

The Workbench shell is designed to add dedicated panes for the remaining platform systems without changing the authority model: character lifecycle, encounter builder, dialogue/quest graphs, faction/economy controls, simulation lab reports, replay/branching, and content distribution management.
