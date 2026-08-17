# v1.9 → v2.5 platform architecture

This document describes the generation of the platform that follows the v1.8 Creator Studio milestone. The core design rule remains unchanged: **the server owns truth**. Authentication, distributed placement, AI planning, client SDKs, and creator tools may propose or transport changes, but only authoritative commands/rules/events mutate campaign state.

## Milestone map

```text
v1.9  Identity / RBAC / Multi-Tenancy
        ↓
v2.0  Distributed World Runtime
        ↓
v2.1  Content Package Graph + Lockfiles
        ↓
v2.2  Simulation Lab
        ↓
v2.3  Reliable Multiplayer Runtime
        ↓
v2.4  Campaign Director
        ↓
v2.5  Python / TypeScript / Godot Client SDKs
```

The Python package version is `2.5.0`. The external HTTP/WebSocket namespace remains `/api/v1` so application release numbering is not coupled to a forced wire-protocol rename.

---

## v1.9 — Identity, RBAC and multi-tenancy

### Identity is not a campaign client

The platform now separates:

```text
Authenticated User / Session
          ↓
RBAC + Resource Membership
          ↓
Campaign transport client
          ↓
Actor ownership / command authorization
          ↓
CampaignSession
          ↓
RulesRuntime / GameEngine
```

`ClientIdentity.client_id` is a transport/session handle. It is not proof of who a user is.

### Tenant hierarchy

```text
Organization
  └─ Workspace
      ├─ Campaign
      └─ Creator Studio Project
```

Campaign/project resources persist the owner plus organization/workspace ancestry. Memberships can therefore be evaluated against an exact resource scope while organization/workspace roles inherit downward through the resource scope chain.

### Roles and permissions

Roles:

- owner
- admin
- game master
- player
- spectator
- creator
- moderator

The policy engine grants explicit permissions such as:

- `campaign.create`
- `campaign.read`
- `campaign.control`
- `campaign.manage`
- `character.control`
- `studio.read`
- `studio.write`
- `studio.publish`
- `distributed.manage`
- `simulation.run`
- `director.manage`
- `audit.read`

Character owners receive `character.control` for their authoritative entity even without broad campaign-control permission.

### Sessions

`SessionTokenService` creates signed, expiring HMAC-SHA256 session assertions. Effective roles are intentionally not stored in tokens; server-side membership is checked when authorization occurs. Sessions also have persistent records and can be revoked immediately.

For authenticated deployments:

```text
RPG_AUTH_REQUIRED=1
RPG_AUTH_SECRET=<32+ byte random signing secret>
RPG_BOOTSTRAP_KEY=<separate random provisioning secret>
```

The bootstrap endpoint is a controlled provisioning mechanism and should not be exposed as a public browser login. Keep its key server-side.

### Authenticated campaign flow

```text
POST /api/v1/auth/bootstrap
POST /api/v1/secure/organizations
POST /api/v1/secure/organizations/{org}/workspaces
POST /api/v1/secure/campaigns
POST /api/v1/secure/memberships
POST /api/v1/secure/campaigns/{campaign}/join
```

A secure campaign derives `owner_id` from the authenticated principal rather than accepting it from a request payload.

### Legacy compatibility

When authentication is not required, the existing local APIs remain usable. When authentication is required, caller-asserted legacy campaign create/join/command/publish paths are disabled and the old unauthenticated campaign WebSocket is removed.

---

## v2.0 — Distributed world runtime

The v1.7 worker model assigns an entire campaign to a single simulator. v2.0 adds world partitioning so a large campaign can be divided into zones.

```text
Campaign / World
├─ wilderness-west   → worker A
├─ wilderness-east   → worker B
├─ capital-city      → worker C
└─ dungeon-instance  → worker D
```

### Placement vs ownership

Rendezvous hashing chooses the **preferred** worker for each zone. It does not by itself grant authority.

PostgreSQL zone leases are the single-writer guard:

```text
placement preference
      ↓
atomic zone lease
      ↓
worker may simulate zone
```

Acquisition/renewal use database time and an atomic conflict update so two hosts cannot both acquire an unexpired zone. SQLite's fallback uses a process-local lock and exists only for development/testing.

### Entity handoff

Cross-zone entity transfer is a two-phase operation:

```text
PREPARED
   ↓ verify entity unchanged
SOURCE_COMMITTED
   ↓ verify payload + transfer hashes
ACCEPTED
```

The prepared handoff contains a canonical SHA-256 entity hash and transfer hash. The source refuses to commit if the entity changes after preparation; the target refuses invalid/conflicting payloads.

Relevant API group:

```text
/api/v1/distributed/campaigns/{campaign}/world
/api/v1/distributed/campaigns/{campaign}/placement
/api/v1/distributed/campaigns/{campaign}/leases/...
/api/v1/distributed/campaigns/{campaign}/handoffs/...
```

---

## v2.1 — Content package graph and lockfiles

Creator content can now be treated as a package graph instead of unrelated ZIP blobs.

A release records:

```text
package id
version
content hash
engine constraint
dependencies
ruleset constraints
migration compatibility
```

The deterministic resolver supports exact versions, comparison ranges, caret ranges, tilde ranges, and wildcards. Resolution chooses compatible releases and produces a lock:

```text
engine=2.5.0
campaign==3.0.0#...
monsters==2.0.0#...
rules==1.1.0#...
```

Re-running resolution against the same repository and requirements yields the same canonical lock ordering.

Upgrade planning compares current/target locks and reports whether the target release declares migration compatibility from the installed version.

Relevant API group:

```text
/api/v1/packages/releases
/api/v1/packages/resolve
/api/v1/packages/upgrade-plan
```

---

## v2.2 — Simulation Lab and automated balancing

The deterministic engine can run repeated simulations without touching the source campaign.

`SimulationLab` derives an independent deterministic seed for every iteration, executes cases with bounded async concurrency, preserves iteration ordering, and computes:

- winner counts/rates
- median duration
- p95 duration
- player-knockout rate
- mean resource utilization
- arbitrary metric means
- deterministic report digest
- automated balance findings

The campaign duel case clones two authoritative actor snapshots and resolves attacks using the normal `CombatSystem`, `RuleSet`, damage traits, and action time costs.

Example API:

```text
POST /api/v1/simulation/campaigns/{campaign}/duel
```

A creator can therefore benchmark builds/encounters repeatedly without mutating the live campaign.

---

## v2.3 — Reliable multiplayer runtime

The reliable layer adds command delivery semantics above the existing authoritative `CampaignSession`.

### Client sequencing

Each authenticated campaign client sends:

```text
client_id
client_sequence
command
request_id
```

Rules:

1. sequence must equal the next expected sequence;
2. retrying the same sequence with the same command fingerprint returns the original acknowledgement without re-executing it;
3. reusing a sequence for a different command is rejected;
4. sequence gaps are rejected;
5. a bounded receipt ledger limits memory growth.

### Presence and subscriptions

The gateway tracks heartbeat/presence state and can filter event subscriptions by event type or actor ID. Backpressure primitives bound queued output and coalesce superseded state snapshots.

### Production socket

```text
/api/v1/reliable/campaigns/{campaign}/ws
```

The socket authenticates the bearer session and verifies that `client_id` belongs to that same authenticated session. It transports commands, acknowledgements, events, heartbeat/presence, state requests, and subscription updates.

---

## v2.4 — Campaign Director

The Campaign Director is not an omnipotent LLM. It is a persistent planner that observes authoritative events and emits proposals.

It tracks:

- dramatic tension
- unresolved story threads
- recent scene repetition
- faction pressure
- relationship pressure hooks
- bounded persistent proposal history

Typical proposal kinds include:

- advance story thread
- introduce encounter
- social beat
- faction consequence
- recovery beat
- world event

The important boundary is:

```text
Events
  ↓
Director observations
  ↓
Proposal
  ↓ optional provider/tool adds a candidate command
parse/validate command
  ↓
GM/admin approval
  ↓
CampaignSession.dispatch(...)
  ↓
RulesRuntime / authoritative events
```

The Director never receives a writable engine object in provider context and never directly edits authoritative state.

Relevant API group:

```text
/api/v1/director/campaigns/{campaign}/...
```

---

## v2.5 — Client SDKs

### Python

```python
from dnd_rpg_engine import RPGClient

client = RPGClient()
await client.bootstrap(
    user_id="local-user",
    display_name="Local User",
    bootstrap_key=bootstrap_key,
)
campaign = await client.create_campaign("Example", seed=42)
await client.command(
    campaign.campaign_id,
    {"type": "wait", "actor_id": "hero"},
)
```

The Python SDK tracks reliable client sequence and event cursors.

### TypeScript

A buildable package exists in `sdk/typescript/` with `package.json`, `tsconfig.json`, fetch helpers, and a reliable WebSocket helper.

### Godot

`adapters/godot/common/RPGClient.gd` supplies a thin Godot-side reliable WebSocket bridge with command acknowledgement and game-event signals. Godot remains responsible for presentation; the Python server remains authoritative.

---

## Production topology

A typical production deployment now looks like:

```text
Browser / Godot / Python / TypeScript clients
                 │ HTTPS/WSS
                 ▼
          ingress / TLS proxy
                 │
                 ▼
       v2.5 Platform API hosts
        │       │          │
     identity  Studio   reliable gateway
        │       │          │
        └───────┴────┬─────┘
                     ▼
                 PostgreSQL
              events / snapshots
              tenant resources
              sessions / audit
              workers / leases
              zone leases
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
  simulation workers       zone workers
          │                     │
          └──── authoritative ──┘
                 state/events
```

Use PostgreSQL for real multi-host coordination. SQLite remains useful for local development, tests, and single-process deployments.

## Validation strategy

The branch carries unit/integration coverage for:

- RBAC, tenancy, revocation and persistent resource ancestry
- authenticated platform create/join/control boundaries
- distributed placement/handoff and zone leases
- deterministic package resolution/conflict planning
- deterministic simulation reports and rule-backed duel simulation
- reliable command retry/idempotency and backpressure behavior
- Director proposal/approval boundaries
- Python SDK reliable sequence/event cursor behavior
- existing v0.1→v1.8 compatibility tests

CI compiles the package and runs the complete suite on Python 3.12, 3.13, and 3.14.
