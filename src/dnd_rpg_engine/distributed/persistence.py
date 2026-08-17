from __future__ import annotations

from typing import Any, Protocol

from dnd_rpg_engine.distributed.world import CrossShardMessage, EntityTransfer, ShardDirectory, TransferCoordinator, WorldShard


class JSONStore(Protocol):
    async def put_json(self, namespace: str, key: str, value: Any) -> None: ...
    async def list_json(self, namespace: str) -> dict[str, Any]: ...


class PersistentWorldRegistry:
    """Persist sharding metadata through the engine's generic JSON store API.

    Both SQLiteStore and PostgreSQLStore expose this contract, so development
    and production use the same serialized shard/transfer/message records.
    """

    shard_namespace = "world.shard"
    transfer_namespace = "world.transfer"
    message_namespace = "world.message"
    assignment_namespace = "world.assignment"

    def __init__(self, store: JSONStore) -> None:
        self.store = store

    async def save_shard(self, shard: WorldShard) -> None:
        await self.store.put_json(self.shard_namespace, shard.id, shard.model_dump(mode="json"))

    async def load_directory(self) -> ShardDirectory:
        directory = ShardDirectory()
        rows = await self.store.list_json(self.shard_namespace)
        for shard_id, payload in sorted(rows.items()):
            shard = WorldShard.model_validate(payload)
            if shard.id != shard_id:
                shard.id = shard_id
            directory.register(shard)
        return directory

    async def save_transfer(self, transfer: EntityTransfer) -> None:
        await self.store.put_json(self.transfer_namespace, transfer.id, transfer.model_dump(mode="json"))

    async def load_transfers(self) -> TransferCoordinator:
        coordinator = TransferCoordinator()
        rows = await self.store.list_json(self.transfer_namespace)
        for transfer_id, payload in sorted(rows.items()):
            transfer = EntityTransfer.model_validate(payload)
            coordinator.transfers[transfer_id] = transfer
            if transfer.status.value == "committed":
                coordinator.committed_entities[transfer.entity_id] = transfer.id
        return coordinator

    async def save_message(self, message: CrossShardMessage) -> None:
        await self.store.put_json(self.message_namespace, message.id, message.model_dump(mode="json"))

    async def messages_for(self, shard_id: str, *, after_lamport: int = 0) -> list[CrossShardMessage]:
        rows = await self.store.list_json(self.message_namespace)
        messages = [
            CrossShardMessage.model_validate(payload)
            for payload in rows.values()
            if str(payload.get("target_shard")) == shard_id and int(payload.get("lamport", 0)) > after_lamport
        ]
        return sorted(messages, key=lambda value: (value.lamport, value.id))

    async def save_assignment(self, region: str, shard_id: str) -> None:
        await self.store.put_json(self.assignment_namespace, region, {"region": region, "shard_id": shard_id})

    async def assignments(self) -> dict[str, str]:
        rows = await self.store.list_json(self.assignment_namespace)
        return {
            region: str(payload["shard_id"])
            for region, payload in sorted(rows.items())
            if isinstance(payload, dict) and payload.get("shard_id")
        }

    async def reconcile_assignments(self, regions: list[str], directory: ShardDirectory) -> dict[str, str]:
        current = await self.assignments()
        changes = directory.rebalance_plan(regions, current)
        for region, shard_id in sorted(changes.items()):
            await self.save_assignment(region, shard_id)
        return changes
