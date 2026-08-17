# src/dnd_rpg_engine/hosting/postgres.py
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dnd_rpg_engine.core.events import GameEvent
from dnd_rpg_engine.core.models import CampaignState
from dnd_rpg_engine.core.persistence import SQLiteStore


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        "base persistence",
        """
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            state_json JSONB NOT NULL,
            version BIGINT NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS events (
            campaign_id TEXT NOT NULL,
            sequence BIGINT NOT NULL,
            event_id TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            event_json JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (campaign_id, sequence)
        );
        CREATE INDEX IF NOT EXISTS idx_events_campaign_type ON events(campaign_id, type);
        CREATE TABLE IF NOT EXISTS snapshots (
            campaign_id TEXT NOT NULL,
            sequence BIGINT NOT NULL,
            state_json JSONB NOT NULL,
            dice_json JSONB NOT NULL,
            scheduler_json JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (campaign_id, sequence)
        );
        CREATE TABLE IF NOT EXISTS kv (
            namespace TEXT NOT NULL,
            key TEXT NOT NULL,
            value_json JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY(namespace, key)
        );
        CREATE TABLE IF NOT EXISTS hosted_campaigns (
            campaign_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            public BOOLEAN NOT NULL DEFAULT FALSE,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),
    Migration(
        2,
        "simulation worker leasing",
        """
        CREATE TABLE IF NOT EXISTS simulation_workers (
            worker_id TEXT PRIMARY KEY,
            capacity INTEGER NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_simulation_workers_heartbeat ON simulation_workers(heartbeat_at);
        CREATE TABLE IF NOT EXISTS campaign_leases (
            campaign_id TEXT PRIMARY KEY,
            worker_id TEXT NOT NULL,
            lease_until TIMESTAMPTZ NOT NULL,
            generation BIGINT NOT NULL DEFAULT 1,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_campaign_leases_worker ON campaign_leases(worker_id);
        CREATE INDEX IF NOT EXISTS idx_campaign_leases_until ON campaign_leases(lease_until);
        """,
    ),
    Migration(
        3,
        "resume ticket index",
        """
        CREATE INDEX IF NOT EXISTS idx_kv_resume_ticket
            ON kv(key) WHERE namespace = 'resume_ticket';
        """,
    ),
)


class PostgreSQLStore:
    """Async PostgreSQL implementation matching the SQLiteStore persistence API.

    ``asyncpg`` is imported lazily so installations that only use SQLite do not
    need the production hosting extra. Connections live in an async pool and no
    blocking database calls are made on the event loop.
    """

    def __init__(
        self,
        dsn: str,
        *,
        min_pool_size: int = 1,
        max_pool_size: int = 10,
        command_timeout: float = 30.0,
    ) -> None:
        self.dsn = dsn
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.command_timeout = command_timeout
        self._pool: Any | None = None
        self._asyncpg: Any | None = None

    @property
    def pool(self) -> Any:
        if self._pool is None:
            raise RuntimeError("PostgreSQLStore.initialize() has not been called")
        return self._pool

    async def initialize(self) -> None:
        if self._pool is not None:
            return
        try:
            self._asyncpg = importlib.import_module("asyncpg")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PostgreSQL hosting requires the optional 'hosting' extra: pip install 'dnd-rpg-engine[hosting]'"
            ) from exc
        self._pool = await self._asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self.min_pool_size,
            max_size=self.max_pool_size,
            command_timeout=self.command_timeout,
        )
        await self._run_migrations()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _run_migrations(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            rows = await conn.fetch("SELECT version FROM schema_migrations")
            applied = {int(row["version"]) for row in rows}
            for migration in sorted(MIGRATIONS, key=lambda item: item.version):
                if migration.version in applied:
                    continue
                async with conn.transaction():
                    await conn.execute(migration.sql)
                    await conn.execute(
                        "INSERT INTO schema_migrations(version, name) VALUES($1, $2)",
                        migration.version,
                        migration.name,
                    )

    async def migration_status(self) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        )
        return [dict(row) for row in rows]

    async def save_campaign(self, state: CampaignState, version: int) -> None:
        payload = state.model_dump(mode="json")
        await self.pool.execute(
            """
            INSERT INTO campaigns(id, name, state_json, version)
            VALUES($1, $2, $3::jsonb, $4)
            ON CONFLICT(id) DO UPDATE SET
              name=EXCLUDED.name,
              state_json=EXCLUDED.state_json,
              version=EXCLUDED.version,
              updated_at=NOW()
            """,
            state.id,
            state.name,
            _json(payload),
            version,
        )

    async def list_campaigns(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT id, name, version, updated_at FROM campaigns ORDER BY updated_at DESC LIMIT $1",
            limit,
        )
        return [dict(row) for row in rows]

    async def load_campaign(self, campaign_id: str) -> tuple[CampaignState, int] | None:
        row = await self.pool.fetchrow(
            "SELECT state_json, version FROM campaigns WHERE id=$1",
            campaign_id,
        )
        if row is None:
            return None
        return CampaignState.model_validate(_decode_json(row["state_json"])), int(row["version"])

    async def append_event(self, event: GameEvent) -> None:
        await self.pool.execute(
            """
            INSERT INTO events(campaign_id, sequence, event_id, type, event_json)
            VALUES($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT DO NOTHING
            """,
            event.campaign_id,
            event.sequence,
            event.id,
            event.type,
            _json(event.model_dump(mode="json")),
        )

    async def list_events(
        self,
        campaign_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> list[GameEvent]:
        rows = await self.pool.fetch(
            """
            SELECT event_json FROM events
            WHERE campaign_id=$1 AND sequence>$2
            ORDER BY sequence ASC LIMIT $3
            """,
            campaign_id,
            after_sequence,
            limit,
        )
        return [GameEvent.model_validate(_decode_json(row["event_json"])) for row in rows]

    async def save_snapshot(
        self,
        state: CampaignState,
        sequence: int,
        dice_counters: dict[str, int],
        scheduler: list[dict[str, Any]],
    ) -> None:
        await self.pool.execute(
            """
            INSERT INTO snapshots(campaign_id, sequence, state_json, dice_json, scheduler_json)
            VALUES($1, $2, $3::jsonb, $4::jsonb, $5::jsonb)
            ON CONFLICT(campaign_id, sequence) DO UPDATE SET
              state_json=EXCLUDED.state_json,
              dice_json=EXCLUDED.dice_json,
              scheduler_json=EXCLUDED.scheduler_json,
              created_at=NOW()
            """,
            state.id,
            sequence,
            _json(state.model_dump(mode="json")),
            _json(dice_counters),
            _json(scheduler),
        )

    async def latest_snapshot(self, campaign_id: str) -> dict[str, Any] | None:
        row = await self.pool.fetchrow(
            """
            SELECT sequence, state_json, dice_json, scheduler_json
            FROM snapshots WHERE campaign_id=$1
            ORDER BY sequence DESC LIMIT 1
            """,
            campaign_id,
        )
        if row is None:
            return None
        return {
            "sequence": int(row["sequence"]),
            "state": CampaignState.model_validate(_decode_json(row["state_json"])),
            "dice_counters": _decode_json(row["dice_json"]),
            "scheduler": _decode_json(row["scheduler_json"]),
        }

    async def put_json(self, namespace: str, key: str, value: Any) -> None:
        await self.pool.execute(
            """
            INSERT INTO kv(namespace, key, value_json) VALUES($1, $2, $3::jsonb)
            ON CONFLICT(namespace, key) DO UPDATE SET
              value_json=EXCLUDED.value_json,
              updated_at=NOW()
            """,
            namespace,
            key,
            _json(value),
        )

    async def get_json(self, namespace: str, key: str) -> Any | None:
        row = await self.pool.fetchrow(
            "SELECT value_json FROM kv WHERE namespace=$1 AND key=$2",
            namespace,
            key,
        )
        return None if row is None else _decode_json(row["value_json"])

    async def list_json(self, namespace: str) -> dict[str, Any]:
        rows = await self.pool.fetch(
            "SELECT key, value_json FROM kv WHERE namespace=$1 ORDER BY key",
            namespace,
        )
        return {str(row["key"]): _decode_json(row["value_json"]) for row in rows}

    async def delete_json(self, namespace: str, key: str) -> None:
        await self.pool.execute("DELETE FROM kv WHERE namespace=$1 AND key=$2", namespace, key)

    async def host_campaign(
        self,
        campaign_id: str,
        owner_id: str,
        *,
        public: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.pool.execute(
            """
            INSERT INTO hosted_campaigns(campaign_id, owner_id, public, metadata_json)
            VALUES($1, $2, $3, $4::jsonb)
            ON CONFLICT(campaign_id) DO UPDATE SET
              owner_id=EXCLUDED.owner_id,
              public=EXCLUDED.public,
              metadata_json=EXCLUDED.metadata_json,
              updated_at=NOW()
            """,
            campaign_id,
            owner_id,
            public,
            _json(metadata or {}),
        )
        await self.put_json(
            "hosted_campaign",
            campaign_id,
            {"owner_id": owner_id, "public": public, **(metadata or {})},
        )

    async def list_hosted_campaign_ids(self, limit: int = 10_000) -> list[str]:
        rows = await self.pool.fetch(
            "SELECT campaign_id FROM hosted_campaigns ORDER BY updated_at DESC LIMIT $1",
            limit,
        )
        if rows:
            return [str(row["campaign_id"]) for row in rows]
        fallback = await self.list_json("hosted_campaign")
        return sorted(fallback)

    async def register_worker(
        self,
        worker_id: str,
        *,
        capacity: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.pool.execute(
            """
            INSERT INTO simulation_workers(worker_id, capacity, metadata_json)
            VALUES($1, $2, $3::jsonb)
            ON CONFLICT(worker_id) DO UPDATE SET
              capacity=EXCLUDED.capacity,
              metadata_json=EXCLUDED.metadata_json,
              heartbeat_at=NOW()
            """,
            worker_id,
            capacity,
            _json(metadata or {}),
        )

    async def heartbeat_worker(self, worker_id: str) -> bool:
        result = await self.pool.execute(
            "UPDATE simulation_workers SET heartbeat_at=NOW() WHERE worker_id=$1",
            worker_id,
        )
        return result.endswith("1")

    async def unregister_worker(self, worker_id: str) -> None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM campaign_leases WHERE worker_id=$1", worker_id)
                await conn.execute("DELETE FROM simulation_workers WHERE worker_id=$1", worker_id)

    async def list_active_workers(self, *, max_age_seconds: float = 30.0) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            """
            SELECT worker_id, capacity, metadata_json, started_at, heartbeat_at
            FROM simulation_workers
            WHERE heartbeat_at > NOW() - ($1 * INTERVAL '1 second')
            ORDER BY worker_id
            """,
            max_age_seconds,
        )
        return [
            {
                "worker_id": str(row["worker_id"]),
                "capacity": int(row["capacity"]),
                "metadata": _decode_json(row["metadata_json"]),
                "started_at": row["started_at"],
                "heartbeat_at": row["heartbeat_at"],
            }
            for row in rows
        ]

    async def acquire_campaign_lease(
        self,
        campaign_id: str,
        worker_id: str,
        *,
        ttl_seconds: float,
    ) -> dict[str, Any] | None:
        row = await self.pool.fetchrow(
            """
            INSERT INTO campaign_leases(campaign_id, worker_id, lease_until, generation)
            VALUES($1, $2, NOW() + ($3 * INTERVAL '1 second'), 1)
            ON CONFLICT(campaign_id) DO UPDATE SET
              worker_id=EXCLUDED.worker_id,
              lease_until=EXCLUDED.lease_until,
              generation=CASE
                WHEN campaign_leases.worker_id = EXCLUDED.worker_id THEN campaign_leases.generation
                ELSE campaign_leases.generation + 1
              END,
              updated_at=NOW()
            WHERE campaign_leases.lease_until <= NOW()
               OR campaign_leases.worker_id = EXCLUDED.worker_id
            RETURNING campaign_id, worker_id, lease_until, generation
            """,
            campaign_id,
            worker_id,
            ttl_seconds,
        )
        return None if row is None else dict(row)

    async def renew_campaign_lease(
        self,
        campaign_id: str,
        worker_id: str,
        *,
        ttl_seconds: float,
    ) -> bool:
        result = await self.pool.execute(
            """
            UPDATE campaign_leases
            SET lease_until=NOW() + ($3 * INTERVAL '1 second'), updated_at=NOW()
            WHERE campaign_id=$1 AND worker_id=$2 AND lease_until > NOW()
            """,
            campaign_id,
            worker_id,
            ttl_seconds,
        )
        return result.endswith("1")

    async def release_campaign_lease(self, campaign_id: str, worker_id: str) -> None:
        await self.pool.execute(
            "DELETE FROM campaign_leases WHERE campaign_id=$1 AND worker_id=$2",
            campaign_id,
            worker_id,
        )

    async def hosting_status(self) -> dict[str, Any]:
        worker_count = await self.pool.fetchval(
            "SELECT COUNT(*) FROM simulation_workers WHERE heartbeat_at > NOW() - INTERVAL '30 seconds'"
        )
        lease_count = await self.pool.fetchval(
            "SELECT COUNT(*) FROM campaign_leases WHERE lease_until > NOW()"
        )
        campaign_count = await self.pool.fetchval("SELECT COUNT(*) FROM hosted_campaigns")
        migrations = await self.migration_status()
        return {
            "backend": "postgresql",
            "hosted_campaigns": int(campaign_count or 0),
            "active_workers": int(worker_count or 0),
            "active_leases": int(lease_count or 0),
            "schema_version": max((int(row["version"]) for row in migrations), default=0),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


def create_store(database_url: str | Path) -> SQLiteStore | PostgreSQLStore:
    """Select the storage backend without changing engine call sites."""

    value = str(database_url)
    if value.startswith(("postgres://", "postgresql://")):
        return PostgreSQLStore(value)
    if value.startswith("sqlite:///"):
        return SQLiteStore(value.removeprefix("sqlite:///"))
    return SQLiteStore(value)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"value is not JSON serializable: {type(value)!r}")


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value
