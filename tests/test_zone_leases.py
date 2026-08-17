from __future__ import annotations

import pytest

from dnd_rpg_engine.distributed import ZoneLeaseManager


class MemoryStore:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    async def list_json(self, namespace: str):
        return dict(self.rows.get(namespace, {}))

    async def put_json(self, namespace: str, key: str, value: object) -> None:
        self.rows.setdefault(namespace, {})[key] = value

    async def delete_json(self, namespace: str, key: str) -> None:
        self.rows.setdefault(namespace, {}).pop(key, None)


@pytest.mark.asyncio
async def test_zone_lease_has_single_owner_and_stable_generation() -> None:
    manager = ZoneLeaseManager(MemoryStore())
    first = await manager.acquire("campaign", "north", "worker-a", ttl_seconds=60)
    assert first is not None and first.generation == 1
    assert await manager.acquire("campaign", "north", "worker-b", ttl_seconds=60) is None
    renewed = await manager.renew("campaign", "north", "worker-a", ttl_seconds=60)
    assert renewed is not None and renewed.generation == 1
    assert await manager.release("campaign", "north", "worker-a") is True
    second = await manager.acquire("campaign", "north", "worker-b", ttl_seconds=60)
    assert second is not None
    # Released rows are deleted in local mode, so reacquisition starts a new
    # lease lineage. PostgreSQL increments generation only for ownership
    # replacement of an existing row.
    assert second.generation == 1


@pytest.mark.asyncio
async def test_claim_placement_only_claims_assigned_zones() -> None:
    manager = ZoneLeaseManager(MemoryStore())
    placement = {"a": "worker-a", "b": "worker-b", "c": "worker-a"}
    claimed = await manager.claim_placement("campaign", placement, "worker-a", ttl_seconds=30)
    assert [value.zone_id for value in claimed] == ["a", "c"]
