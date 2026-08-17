# Public API

FastAPI publishes interactive OpenAPI at `/docs` and the raw schema at `/openapi.json`.

Major endpoints:

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
POST   /api/v1/creator/validate
POST   /api/v1/creator/instantiate
POST   /api/v1/marketplace/publish
GET    /api/v1/marketplace
POST   /api/v1/marketplace/{item_id}/install
```

Campaign creation returns an `owner_client_id`. Send that value in the `X-RPG-Client-ID` header for owner-only campaign mutations such as entity creation, encounter/timing control, and manual ticks. Command requests may use that header or the request body's `client_id`; commands are always dispatched through the campaign session authorization layer.

`POST /join` creates a session client for another user. Non-owner clients can only control entities whose `owner_id` matches their claimed `user_id`; callers cannot self-promote to owner or claim arbitrary actor IDs. WebSocket event streams may be observed without a client ID, but WebSocket commands require `?client_id=<id>` and pass through the same session authorization checks as REST.

The built-in `user_id`/`client_id` mechanism is an application authorization primitive, not an Internet identity provider. Public deployments should authenticate users externally and map the proven identity to `user_id`.


## Character and playable-platform APIs

- `POST /api/v2/playable-campaigns` — create a hosted SRD campaign plus first character.
- `POST /api/v1/campaigns/{id}/characters` — build a typed character.
- `GET /api/v1/campaigns/{id}/characters/{actor}` — character sheet plus legal actions.
- `GET /api/v1/campaigns/{id}/characters/{actor}/actions` — authoritative legal-action query.
- `POST /api/v1/campaigns/{id}/characters/{actor}/level-up` and `/xp` — advancement.
- `GET .../characters/{actor}/export` and `POST .../characters/import` — portable character packages.
- `POST /api/v1/campaigns/{id}/party` and `/travel` — campaign-runner party/travel control.
- `POST /api/v1/campaigns/{id}/encounters/budgeted` and `/encounters/finish` — catalog-backed encounters and rewards.
- `GET /api/v1/campaigns/{id}/director` — mutation-free AI campaign suggestion.
- `GET /api/v1/campaigns/{id}/export` and `POST /api/v1/campaigns/import` — portable campaign packages.
- `GET /api/v1/campaigns/{id}/lobby`, `POST .../reconnect`, `GET .../replay` — multiplayer continuity.
- `POST /api/v1/creator/studio/inspect` and `/apply` — Creator Studio project round-trip.
