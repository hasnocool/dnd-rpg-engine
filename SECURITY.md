# Security

## Trust boundaries

The authoritative server treats commands, WebSocket messages, content packs, and creator input as untrusted.

Current protections include:

- Pydantic validation at API/content boundaries.
- explicit multiplayer client registration, owner-role checks, and actor ownership checks across REST and WebSocket command paths.
- optimistic campaign version checks for command callers that request them.
- no arbitrary expression execution from creator rule documents.
- bounded ZIP extraction with traversal-path rejection.
- bounded event fan-out queues so slow clients cannot stall simulation persistence.
- SQLite calls isolated from the event loop via worker threads and short-lived connections.

For public Internet hosting, deploy behind an authentication/authorization layer and TLS reverse proxy. The built-in `user_id`/`client_id` model is an application authorization primitive, not an identity provider: callers still need an external system to prove that a claimed `user_id` belongs to them.
