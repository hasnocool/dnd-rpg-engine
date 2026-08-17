# Public API

FastAPI publishes interactive OpenAPI at `/docs` and the raw schema at `/openapi.json`. The package is currently `3.9.0`; the public transport namespace remains `/api/v1` while the product roadmap is documented through the unreleased v4.0 actor-experience milestone.

The OpenAPI schema is the canonical route reference. This page groups the major application surfaces and explains their authority model.

## Campaign and session core

```text
GET    /health
GET    /api/v1/campaigns
POST   /api/v1/campaigns
GET    /api/v1/campaigns/{campaign_id}
PATCH  /api/v1/campaigns/{campaign_id}/timing
POST   /api/v1/campaigns/{campaign_id}/entities
POST   /api/v1/campaigns/{campaign_id}/commands
POST   /api/v1/campaigns/{campaign_id}/tick
GET    /api/v1/campaigns/{campaign_id}/events
POST   /api/v1/campaigns/{campaign_id}/encounters
DELETE /api/v1/campaigns/{campaign_id}/encounters/{encounter_id}
POST   /api/v1/campaigns/{campaign_id}/join
WS     /api/v1/campaigns/{campaign_id}/ws
```

Campaign creation returns an `owner_client_id`. Send that value in the `X-RPG-Client-ID` header for owner-only mutations. Commands may use the header or request `client_id`, but they always pass through the campaign-session authorization layer.

`POST /join` creates a session client for another user. Non-owner clients can control only actors the server resolves as belonging to their user identity. Callers cannot self-promote to owner or claim arbitrary actor IDs.

In the world profile, campaign reads, event history, runtime snapshots, and WebSocket streams are knowledge-scoped. Owners can request authoritative views; players receive projections based on owned actors and remembered knowledge; spectators receive only public information.

## Character lifecycle and Hero Creator

The `/hero` browser page uses the authoritative character-lifecycle routes rather than mutating character state directly.

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

Character creation and safe profile editing are owner operations. Advancement, equipment, rests, and resources remain lifecycle operations dispatched through the authoritative engine. The safe edit route is intentionally limited to identity/presentation/base-character fields; it does not provide a shortcut around level, XP, equipment, resource, timing, or rules validation.

## NPC management

The v4.0 actor workflow adds first-class owner-only NPC management:

```text
GET    /api/v1/campaigns/{campaign_id}/npcs
POST   /api/v1/campaigns/{campaign_id}/npcs
GET    /api/v1/campaigns/{campaign_id}/npcs/{actor_id}
PATCH  /api/v1/campaigns/{campaign_id}/npcs/{actor_id}
DELETE /api/v1/campaigns/{campaign_id}/npcs/{actor_id}
```

NPC updates synchronize the registered `NPCProfile` and live NPC entity. Profiles can reference faction, personality, dialogue, shop, schedule, AI profile, position, stats/resources, tags, appearance, and knowledge metadata. Schedule assignment is validated by the server.

## World-platform services

```text
/api/v1/campaigns/{campaign_id}/rules/compile
/api/v1/campaigns/{campaign_id}/scenes
/api/v1/campaigns/{campaign_id}/director/proposals
/api/v1/campaigns/{campaign_id}/runtime
/api/v1/campaigns/{campaign_id}/workbench/*
```

The Workbench aggregation routes expose presentation-ready session, party, tactical, analytics, knowledge, replay, content, and Director-decision data. They aggregate existing authoritative engine services; they do not maintain a separate browser-owned state store.

AI Director proposals remain advisory until an owner explicitly accepts or dismisses them. Acceptance may apply only bounded safe proposal metadata; concrete gameplay changes continue through ordinary authoritative actions.

## Creator Studio and content distribution

```text
/api/v1/studio
/api/v1/distribution
/api/v1/creator/validate
/api/v1/creator/instantiate
/api/v1/marketplace
```

Creator Studio owns editable reusable source content. Validation/export/publication uses the same typed `ContentPack` model consumed by runtime loading. Distribution resolves semantic-version dependencies, engine compatibility, package hashes, and lock state.

The Hero & NPC Workshop is deliberately separate from Creator Studio: `/creator` authors reusable content/templates, while `/hero` manages actors inside a running campaign instance.

## Browser surfaces

```text
/          Campaign Workbench
/hero      Hero & NPC Workshop
/creator   Creator Studio
/docs      OpenAPI UI
```

These browser clients are presentation/orchestration layers. They submit requests and render returned state; they do not calculate trusted combat, movement, visibility, resources, progression, timing, AI, or rules outcomes locally.

## Identity boundary

The built-in `user_id` / `client_id` mechanism is an application authorization primitive, not an Internet identity provider. Public deployments should authenticate users externally and map the proven identity to `user_id`.
