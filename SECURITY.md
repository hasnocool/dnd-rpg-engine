# Security

## Trust boundaries

The authoritative server treats commands, WebSocket messages, content packs, Creator Studio input, AI/Director proposals, reconnect tokens, and client identifiers as untrusted.

The v2.5 platform supports two deployment profiles:

- **compatibility/local mode** — authentication is optional and the legacy API remains available for trusted local development;
- **authenticated mode** — set `RPG_AUTH_REQUIRED=1`; caller-asserted legacy campaign create/join/command/publish paths are disabled and the identity/RBAC + reliable transport becomes the authority boundary.

Authenticated mode requires a signing secret of at least 32 bytes:

```text
RPG_AUTH_REQUIRED=1
RPG_AUTH_SECRET=<random secret from your secret manager>
RPG_BOOTSTRAP_KEY=<separate random provisioning secret>
```

Do not commit either secret to the repository. Rotate deployment secrets through the platform or secret manager used by your hosting environment.

## Identity and sessions

`SessionTokenService` issues HMAC-SHA256 signed session assertions containing a user ID, session ID, issue time, and expiration time. Effective roles are **not** embedded in tokens. Authorization is resolved from current server-side memberships on every protected operation, so membership changes take effect without waiting for token expiry.

A session is valid only while both the token signature/time claims and the persistent server-side session record are valid. Revoking a session invalidates subsequent API authorization and the campaign policy callbacks reject bound clients whose underlying session has become inactive.

The built-in `/api/v1/auth/bootstrap` endpoint is a controlled provisioning mechanism, not a public password/OIDC implementation. It requires `X-RPG-Bootstrap-Key`. Never expose the bootstrap key to browser/game clients. For an Internet service, place user onboarding/login in the deployment's identity layer and use bootstrap/provisioning only from a trusted backend or replace that provisioning flow with the deployment's identity integration.

## Authorization and multi-tenancy

The security model separates **authenticated user identity** from **transport client identity**.

Tenant scopes are:

```text
Organization
  └─ Workspace
      ├─ Campaign
      └─ Creator Studio Project
```

Roles include owner, admin, game master, player, spectator, creator, and moderator. Permissions are resource-specific (`campaign.read`, `campaign.control`, `campaign.manage`, `character.control`, `studio.write`, `studio.publish`, `distributed.manage`, `simulation.run`, `director.manage`, and others).

Campaign and Studio resources persist their owner plus organization/workspace ancestry. A user cannot gain ownership by supplying another `owner_id`, organization ID, workspace ID, campaign client ID, or project ID.

Players receive character control either through explicit privileged campaign roles or by matching the authoritative entity `owner_id`. Game masters/admins are authorized through policy callbacks; the server does not fake an OWNER transport role to grant them authority.

## Transport security

In authenticated mode:

- legacy caller-asserted campaign create/list/join/command mutations are disabled;
- `X-RPG-Client-ID` is checked against the bearer user's bound authenticated session;
- the legacy unauthenticated campaign WebSocket is removed;
- clients use `/api/v1/reliable/campaigns/{campaign_id}/ws` or the reliable command REST endpoint;
- client command sequences are exact and retry-safe;
- reusing a sequence for a different command is rejected;
- command rate limiting and bounded retry ledgers reduce abuse/resource growth;
- reconnect tickets are opaque, expiring, revocable, rotating, and stored by hash rather than plaintext.

Always terminate public traffic with HTTPS/WSS. The application token layer does not replace transport encryption.

## Distributed simulation

PostgreSQL is the coordination backend for real multi-host deployment. Campaign workers use leases, and v2.0 zone workers use atomic database-time zone leases. Stable rendezvous placement determines the preferred worker, but **the lease is the single-writer authority**.

Entity handoffs are two-phase and hash verified:

```text
PREPARED -> SOURCE_COMMITTED -> ACCEPTED
```

The destination refuses a transfer whose entity hash/transfer hash does not verify. SQLite's zone-lease fallback uses only a process-local lock and is intended for development/testing, not multi-host coordination.

## AI boundary

Narrators, intelligent actors, and the Campaign Director cannot directly mutate authoritative state. Director output is a proposal. Attached commands are parsed before storage and approval still dispatches through the authenticated `CampaignSession`, normal command validation, active `RulesRuntime`, and event stream.

## Content and Creator Studio

Current content protections include:

- Pydantic validation at API/content boundaries;
- no arbitrary expression execution from rule documents;
- bounded ZIP extraction with traversal-path rejection;
- deterministic content hashes and version lockfiles;
- package dependency/engine constraints before resolution;
- project-scoped Studio read/write/publish permissions;
- validation before Studio export/publishing;
- audit records for security-sensitive tenant/platform mutations.

## Operational recommendations

For public hosting:

1. use PostgreSQL for production persistence/coordination;
2. require authentication;
3. terminate TLS at a trusted ingress/reverse proxy;
4. generate signing/bootstrap values with a cryptographically secure secret generator and store them in a secret manager;
5. do not expose the bootstrap key to end-user clients;
6. restrict database/network access to the minimum required services;
7. monitor worker/zone leases, auth denials, reconnect behavior, and audit records;
8. back up PostgreSQL and test event-sourced restore/replay procedures;
9. apply rate limits at the edge in addition to application command limits;
10. review third-party content package licenses and provenance before marketplace publication.
