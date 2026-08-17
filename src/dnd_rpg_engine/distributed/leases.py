from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ZoneLease(BaseModel):
    campaign_id: str
    zone_id: str
    worker_id: str
    lease_until: datetime
    generation: int = Field(default=1, ge=1)

    @property
    def active(self) -> bool:
        return self.lease_until > utcnow()


class ZoneLeaseManager:
    """Single-owner zone leases for a distributed campaign.

    PostgreSQL uses one atomic UPSERT guarded by database time, so multiple
    processes cannot both acquire an unexpired zone. SQLite/dev mode falls back
    to a process-local lock plus persisted snapshots; that mode is deliberately
    not advertised as a multi-host coordination primitive.
    """

    namespace = "distributed.zone_lease"

    def __init__(self, store: Any) -> None:
        self.store = store
        self._lock = asyncio.Lock()
        self._local: dict[tuple[str, str], ZoneLease] = {}
        self._initialized = False

    @property
    def postgres(self) -> bool:
        return hasattr(self.store, "pool") and self.store.__class__.__name__ == "PostgreSQLStore"

    async def initialize(self) -> None:
        if self._initialized:
            return
        if self.postgres:
            await self.store.pool.execute(
                """
                CREATE TABLE IF NOT EXISTS zone_leases (
                    campaign_id TEXT NOT NULL,
                    zone_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    lease_until TIMESTAMPTZ NOT NULL,
                    generation BIGINT NOT NULL DEFAULT 1,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY(campaign_id, zone_id)
                );
                CREATE INDEX IF NOT EXISTS idx_zone_leases_worker
                    ON zone_leases(worker_id);
                CREATE INDEX IF NOT EXISTS idx_zone_leases_until
                    ON zone_leases(lease_until);
                """
            )
        else:
            stored = await self.store.list_json(self.namespace)
            for value in stored.values():
                lease = ZoneLease.model_validate(value)
                self._local[(lease.campaign_id, lease.zone_id)] = lease
        self._initialized = True

    async def acquire(
        self,
        campaign_id: str,
        zone_id: str,
        worker_id: str,
        *,
        ttl_seconds: float = 15.0,
    ) -> ZoneLease | None:
        if ttl_seconds <= 0:
            raise ValueError("lease ttl must be positive")
        await self.initialize()
        if self.postgres:
            row = await self.store.pool.fetchrow(
                """
                INSERT INTO zone_leases(campaign_id, zone_id, worker_id, lease_until, generation)
                VALUES($1, $2, $3, NOW() + ($4 * INTERVAL '1 second'), 1)
                ON CONFLICT(campaign_id, zone_id) DO UPDATE SET
                    worker_id=EXCLUDED.worker_id,
                    lease_until=EXCLUDED.lease_until,
                    generation=CASE
                        WHEN zone_leases.worker_id = EXCLUDED.worker_id THEN zone_leases.generation
                        ELSE zone_leases.generation + 1
                    END,
                    updated_at=NOW()
                WHERE zone_leases.lease_until <= NOW()
                   OR zone_leases.worker_id = EXCLUDED.worker_id
                RETURNING campaign_id, zone_id, worker_id, lease_until, generation
                """,
                campaign_id,
                zone_id,
                worker_id,
                ttl_seconds,
            )
            return None if row is None else ZoneLease.model_validate(dict(row))
        async with self._lock:
            key = (campaign_id, zone_id)
            existing = self._local.get(key)
            now = utcnow()
            if existing is not None and existing.lease_until > now and existing.worker_id != worker_id:
                return None
            generation = 1 if existing is None else existing.generation + int(existing.worker_id != worker_id)
            lease = ZoneLease(
                campaign_id=campaign_id,
                zone_id=zone_id,
                worker_id=worker_id,
                lease_until=now + timedelta(seconds=ttl_seconds),
                generation=generation,
            )
            self._local[key] = lease
            await self.store.put_json(self.namespace, self._key(campaign_id, zone_id), lease.model_dump(mode="json"))
            return lease

    async def renew(
        self,
        campaign_id: str,
        zone_id: str,
        worker_id: str,
        *,
        ttl_seconds: float = 15.0,
    ) -> ZoneLease | None:
        if ttl_seconds <= 0:
            raise ValueError("lease ttl must be positive")
        await self.initialize()
        if self.postgres:
            row = await self.store.pool.fetchrow(
                """
                UPDATE zone_leases
                SET lease_until=NOW() + ($4 * INTERVAL '1 second'), updated_at=NOW()
                WHERE campaign_id=$1 AND zone_id=$2 AND worker_id=$3 AND lease_until > NOW()
                RETURNING campaign_id, zone_id, worker_id, lease_until, generation
                """,
                campaign_id,
                zone_id,
                worker_id,
                ttl_seconds,
            )
            return None if row is None else ZoneLease.model_validate(dict(row))
        async with self._lock:
            key = (campaign_id, zone_id)
            existing = self._local.get(key)
            if existing is None or existing.worker_id != worker_id or not existing.active:
                return None
            existing.lease_until = utcnow() + timedelta(seconds=ttl_seconds)
            await self.store.put_json(self.namespace, self._key(campaign_id, zone_id), existing.model_dump(mode="json"))
            return existing.model_copy(deep=True)

    async def release(self, campaign_id: str, zone_id: str, worker_id: str) -> bool:
        await self.initialize()
        if self.postgres:
            result = await self.store.pool.execute(
                "DELETE FROM zone_leases WHERE campaign_id=$1 AND zone_id=$2 AND worker_id=$3",
                campaign_id,
                zone_id,
                worker_id,
            )
            return result.endswith("1")
        async with self._lock:
            key = (campaign_id, zone_id)
            existing = self._local.get(key)
            if existing is None or existing.worker_id != worker_id:
                return False
            self._local.pop(key, None)
            await self.store.delete_json(self.namespace, self._key(campaign_id, zone_id))
            return True

    async def list(self, campaign_id: str, *, active_only: bool = True) -> list[ZoneLease]:
        await self.initialize()
        if self.postgres:
            where = "AND lease_until > NOW()" if active_only else ""
            rows = await self.store.pool.fetch(
                f"""
                SELECT campaign_id, zone_id, worker_id, lease_until, generation
                FROM zone_leases WHERE campaign_id=$1 {where}
                ORDER BY zone_id
                """,
                campaign_id,
            )
            return [ZoneLease.model_validate(dict(row)) for row in rows]
        values = [
            value.model_copy(deep=True)
            for (stored_campaign, _), value in self._local.items()
            if stored_campaign == campaign_id and (not active_only or value.active)
        ]
        return sorted(values, key=lambda value: value.zone_id)

    async def claim_placement(
        self,
        campaign_id: str,
        placement: dict[str, str],
        worker_id: str,
        *,
        ttl_seconds: float = 15.0,
    ) -> list[ZoneLease]:
        claimed: list[ZoneLease] = []
        for zone_id in sorted(zone for zone, worker in placement.items() if worker == worker_id):
            lease = await self.acquire(campaign_id, zone_id, worker_id, ttl_seconds=ttl_seconds)
            if lease is not None:
                claimed.append(lease)
        return claimed

    @staticmethod
    def _key(campaign_id: str, zone_id: str) -> str:
        return f"{campaign_id}:{zone_id}"
