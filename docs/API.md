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

For multiplayer, submit `client_id` with command requests to enforce actor ownership through the campaign session. WebSocket transport can also carry commands and emits authoritative events to connected clients.
