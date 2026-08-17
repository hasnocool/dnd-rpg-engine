# src/dnd_rpg_engine/hosting/workers.py
from __future__ import annotations

import asyncio
import hashlib
import socket
from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.hosting.postgres import PostgreSQLStore


class WorkerConfig(BaseModel):
    worker_id: str = Field(default_factory=lambda: f"{socket.gethostname()}-{uuid4().hex[:8]}")
    capacity: int = Field(default=16, ge=1, le=10_000)
    lease_ttl_seconds: float = Field(default=30.0, gt=3.0)
    heartbeat_seconds: float = Field(default=5.0, gt=0.25)
    reconcile_seconds: float = Field(default=3.0, gt=0.25)
    metadata: dict[str, str] = Field(default_factory=dict)


class RendezvousRouter:
    """Stable campaign-to-worker placement with minimal movement on scale events."""

    @staticmethod
    def score(campaign_id: str, worker_id: str) -> int:
        digest = hashlib.sha256(f"{campaign_id}\0{worker_id}".encode("utf-8")).digest()
        return int.from_bytes(digest[:16], "big")

    def choose(self, campaign_id: str, worker_ids: Iterable[str]) -> str | None:
        candidates = sorted(set(worker_ids))
        if not candidates:
            return None
        return max(candidates, key=lambda worker_id: (self.score(campaign_id, worker_id), worker_id))


@dataclass(slots=True)
class _CampaignTask:
    campaign_id: str
    stop: asyncio.Event
    task: asyncio.Task[None]


class SimulationWorker:
    """Lease-backed production simulation worker.

    Every worker observes the same hosted-campaign set. Rendezvous hashing picks
    a preferred worker, while PostgreSQL leases remain the final authority that
    prevents two processes from simulating the same campaign concurrently.
    """

    def __init__(
        self,
        store: PostgreSQLStore,
        config: WorkerConfig | None = None,
        *,
        router: RendezvousRouter | None = None,
    ) -> None:
        self.store = store
        self.config = config or WorkerConfig()
        self.router = router or RendezvousRouter()
        self._campaigns: dict[str, _CampaignTask] = {}

    @property
    def running_campaign_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._campaigns))

    async def run(self, stop: asyncio.Event) -> None:
        await self.store.initialize()
        await self.store.register_worker(
            self.config.worker_id,
            capacity=self.config.capacity,
            metadata=self.config.metadata,
        )
        try:
            while not stop.is_set():
                await self._reconcile()
                try:
                    await asyncio.wait_for(stop.wait(), timeout=self.config.reconcile_seconds)
                except TimeoutError:
                    pass
        finally:
            await self._stop_all()
            await self.store.unregister_worker(self.config.worker_id)

    async def _reconcile(self) -> None:
        await self.store.heartbeat_worker(self.config.worker_id)
        active_workers = await self.store.list_active_workers(
            max_age_seconds=max(self.config.lease_ttl_seconds, self.config.heartbeat_seconds * 3)
        )
        worker_ids = [str(row["worker_id"]) for row in active_workers]
        if self.config.worker_id not in worker_ids:
            worker_ids.append(self.config.worker_id)
        campaigns = await self.store.list_hosted_campaign_ids()
        preferred = [
            campaign_id
            for campaign_id in campaigns
            if self.router.choose(campaign_id, worker_ids) == self.config.worker_id
        ]
        preferred.sort(key=lambda campaign_id: self.router.score(campaign_id, self.config.worker_id), reverse=True)
        desired = set(preferred[: self.config.capacity])

        for campaign_id in list(self._campaigns):
            if campaign_id not in desired:
                await self._stop_campaign(campaign_id)
                continue
            renewed = await self.store.renew_campaign_lease(
                campaign_id,
                self.config.worker_id,
                ttl_seconds=self.config.lease_ttl_seconds,
            )
            if not renewed:
                await self._stop_campaign(campaign_id, release=False)

        for campaign_id in sorted(desired):
            if campaign_id in self._campaigns:
                continue
            lease = await self.store.acquire_campaign_lease(
                campaign_id,
                self.config.worker_id,
                ttl_seconds=self.config.lease_ttl_seconds,
            )
            if lease is not None:
                self._start_campaign(campaign_id)

    def _start_campaign(self, campaign_id: str) -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(
            self._serve_campaign(campaign_id, stop),
            name=f"rpg-campaign:{campaign_id}",
        )
        self._campaigns[campaign_id] = _CampaignTask(campaign_id=campaign_id, stop=stop, task=task)

    async def _serve_campaign(self, campaign_id: str, stop: asyncio.Event) -> None:
        try:
            engine = await AdvancedGameEngine.load(campaign_id, store=self.store)
            if engine.config.realtime_enabled:
                await engine.run_realtime(stop)
            else:
                await stop.wait()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.store.put_json(
                "worker_error",
                f"{self.config.worker_id}:{campaign_id}",
                {
                    "worker_id": self.config.worker_id,
                    "campaign_id": campaign_id,
                    "error": type(exc).__name__,
                    "detail": str(exc),
                },
            )

    async def _stop_campaign(self, campaign_id: str, *, release: bool = True) -> None:
        running = self._campaigns.pop(campaign_id, None)
        if running is not None:
            running.stop.set()
            running.task.cancel()
            try:
                await running.task
            except asyncio.CancelledError:
                pass
        if release:
            await self.store.release_campaign_lease(campaign_id, self.config.worker_id)

    async def _stop_all(self) -> None:
        for campaign_id in list(self._campaigns):
            await self._stop_campaign(campaign_id)
