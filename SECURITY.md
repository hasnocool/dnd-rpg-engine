# Security

## Trust boundaries

The authoritative server treats commands, WebSocket messages, content packs, Creator Studio input, executable rule graphs, reconnect tickets, package metadata, and cross-shard messages as untrusted input.

Current protections include:

- Pydantic validation at API/content boundaries.
- explicit multiplayer client registration, owner-role checks, and actor ownership checks across REST and WebSocket command paths.
- optimistic campaign version checks for command callers that request them.
- bounded ZIP extraction with traversal-path rejection.
- bounded event fan-out queues so slow clients cannot stall simulation persistence.
- SQLite calls isolated from the event loop via worker threads and short-lived connections.
- PostgreSQL campaign leases preventing two production workers from authoritatively simulating the same campaign lease at once.
- reconnect/resume tokens generated as opaque values and persisted only by SHA-256 hash, with expiration, revocation, rotation, and event checkpoints.

## Executable content is declarative, not arbitrary code

Creator-authored executable rules use the bounded `ExecutableRuleGraph` IR. Content packs do not receive an arbitrary Python/Lua/JavaScript interpreter and the compiler does not call `eval` or `exec`.

The rule compiler/runtime enforce:

- a fixed allowlist of operations;
- bounded node/effect counts;
- cross-reference validation;
- canonical SHA-256 graph hashes that are verified at execution time;
- a deterministic maximum execution-step budget;
- restricted value references;
- state writes limited to `state.flags.*`, `actor.components.*`, and `target.components.*`;
- no filesystem, process, import, socket, environment, or generic Python-object access from authored graph data.

The visual Creator Studio graph editor validates through the same compiler used by runtime execution before it persists a requested compiled graph revision.

## Knowledge and visibility

`CampaignState` is authoritative truth. Player/AI knowledge is a separate projection.

The v3 world-profile read routes enforce that separation:

- only owners receive omniscient campaign/runtime state;
- players receive knowledge views for actors they own;
- remembered entities are stored as observation-time snapshots, not live references to hidden state;
- non-self observations strip non-public component groups;
- event history and WebSocket event delivery are filtered by owned/known actors unless an event is explicitly marked public;
- a missing/unknown campaign client identity is rejected for world-profile state/event/WebSocket reads;
- spectators with no owned actors receive a public campaign shell rather than full entity truth.

The legacy compatibility app remains available separately for deployments that deliberately need its older read semantics.

## Content distribution

Distribution releases carry content hashes, engine compatibility constraints, and deterministic dependency locks. The built-in HMAC-SHA256 signer is suitable for private registries and tests; public registries should use an asymmetric signer implemented behind the same signature metadata boundary.

A signature authenticates release metadata only when its key is independently trusted. Do not treat an unknown signing key as proof that a package is safe.

## Distributed-world messages and handoff

World-shard entity transfers use canonical entity-state hashes and a prepare/accept/commit protocol. The transfer coordinator rejects hash mismatches and prevents a second transfer from being committed for an entity already committed through another transfer record.

Cross-shard messages use Lamport ordering plus optional idempotency keys. This provides deterministic ordering/deduplication primitives, but production transports must still provide authenticated service identity, encrypted transport, appropriate authorization, retry limits, and operational monitoring.

## Internet deployment

For public Internet hosting, deploy behind an authentication/authorization layer and TLS reverse proxy. The built-in `user_id`/`client_id` model is an application authorization primitive, not an identity provider: callers still need an external system to prove that a claimed `user_id` belongs to them.

For a distributed deployment, also authenticate worker/shard processes separately from player identities, scope database credentials, rotate signing/service keys, and use network policies so simulation workers expose only the services they require.
