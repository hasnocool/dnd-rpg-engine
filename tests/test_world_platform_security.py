from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dnd_rpg_engine.api.platform import create_platform_app
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.core.persistence import SQLiteStore
from dnd_rpg_engine.distributed.persistence import PersistentWorldRegistry
from dnd_rpg_engine.distributed.world import ShardStatus, TransferCoordinator, WorldShard
from dnd_rpg_engine.distribution.service import ContentDistributionService
from dnd_rpg_engine.creator.content import ContentPack, ModManifest


def test_world_platform_http_and_websocket_reads_are_knowledge_scoped(tmp_path) -> None:
    app = create_platform_app(str(tmp_path / "world.sqlite3"), advanced=True)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/campaigns",
            json={"name": "Secrets", "owner_id": "owner", "seed": 9, "time_mode": "turn_based"},
        )
        assert created.status_code == 200
        campaign_id = created.json()["campaign_id"]
        owner_client_id = created.json()["owner_client_id"]
        owner_headers = {"X-RPG-Client-ID": owner_client_id}

        for entity_id, owner_id in (("hero", "player"), ("hidden_foe", None)):
            response = client.post(
                f"/api/v1/campaigns/{campaign_id}/entities",
                headers=owner_headers,
                json={
                    "id": entity_id,
                    "name": entity_id,
                    "kind": "player" if entity_id == "hero" else "creature",
                    "controller": "human" if entity_id == "hero" else "ai",
                    "owner_id": owner_id,
                    "resources": {"hp": 10, "max_hp": 10},
                    "components": {"secret": {"value": "do-not-leak"}} if entity_id == "hidden_foe" else {},
                },
            )
            assert response.status_code == 200

        joined = client.post(
            f"/api/v1/campaigns/{campaign_id}/join",
            json={"user_id": "player", "display_name": "Player", "role": "player", "actor_ids": ["hero"]},
        )
        assert joined.status_code == 200
        player_client_id = joined.json()["client_id"]
        player_headers = {"X-RPG-Client-ID": player_client_id}

        assert client.get(f"/api/v1/campaigns/{campaign_id}").status_code == 401
        owner_state = client.get(f"/api/v1/campaigns/{campaign_id}", headers=owner_headers)
        assert owner_state.status_code == 200
        assert owner_state.json()["knowledge_scoped"] is False
        assert "hidden_foe" in owner_state.json()["campaign"]["entities"]

        player_state = client.get(f"/api/v1/campaigns/{campaign_id}", headers=player_headers)
        assert player_state.status_code == 200
        assert player_state.json()["knowledge_scoped"] is True
        assert set(player_state.json()["entities"]) == {"hero"}
        assert "hidden_foe" not in player_state.text
        assert "do-not-leak" not in player_state.text

        player_events = client.get(
            f"/api/v1/campaigns/{campaign_id}/events",
            headers=player_headers,
        )
        assert player_events.status_code == 200
        assert all(
            event.get("actor_id") != "hidden_foe" and event.get("target_id") != "hidden_foe"
            for event in player_events.json()
        )

        with client.websocket_connect(
            f"/api/v1/campaigns/{campaign_id}/ws?client_id={player_client_id}"
        ) as websocket:
            initial = websocket.receive_json()
            assert initial["kind"] == "state"
            assert initial["state"]["knowledge_scoped"] is True
            assert set(initial["state"]["entities"]) == {"hero"}
            websocket.send_json({"kind": "state"})
            refreshed = websocket.receive_json()
            assert refreshed["kind"] == "state"
            assert "hidden_foe" not in str(refreshed)


@pytest.mark.asyncio
async def test_persistent_world_and_distribution_registries_round_trip(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "registries.sqlite3")
    await store.initialize()

    worlds = PersistentWorldRegistry(store)
    west = WorldShard(id="west", status=ShardStatus.READY, capacity=50, load=7, regions={"island"}, heartbeat_at=10)
    east = WorldShard(id="east", status=ShardStatus.READY, capacity=50, load=3, heartbeat_at=10)
    await worlds.save_shard(west)
    await worlds.save_shard(east)
    directory = await worlds.load_directory()
    assert directory.route("island").id == "west"
    changes = await worlds.reconcile_assignments(["island", "mainland"], directory)
    assert changes["island"] == "west"
    assert (await worlds.assignments())["island"] == "west"

    coordinator = TransferCoordinator()
    entity = Entity(id="traveler", name="Traveler")
    transfer = coordinator.prepare(
        entity,
        source_shard="west",
        target_shard="east",
        target_region="mainland",
        now=11,
    )
    coordinator.accept(transfer.id, destination_hash=transfer.state_hash)
    coordinator.commit(transfer.id, now=12)
    await worlds.save_transfer(transfer)
    restored = await worlds.load_transfers()
    assert restored.restore_entity(transfer.id).id == "traveler"

    message = coordinator.message(
        source_shard="west",
        target_shard="east",
        topic="world.transfer",
        idempotency_key="transfer-once",
    )
    await worlds.save_message(message)
    messages = await worlds.messages_for("east")
    assert [row.id for row in messages] == [message.id]

    distribution = ContentDistributionService(store)
    base_pack = ContentPack(manifest=ModManifest(id="base.pack", name="Base", version="1.0.0"))
    addon_pack = ContentPack(
        manifest=ModManifest(
            id="addon.pack",
            name="Addon",
            version="1.2.0",
            engine_version=">=3.0.0",
            dependencies={"base.pack": "^1.0.0"},
        )
    )
    await distribution.publish_pack(base_pack)
    await distribution.publish_pack(addon_pack)
    resolution = await distribution.resolve(
        {"addon.pack": "^1.0.0"},
        engine_version="3.0.0",
        lock_id="campaign:test",
    )
    assert resolution.order == ["base.pack", "addon.pack"]
    assert len(resolution.lock_hash) == 64
    locks = await distribution.locks()
    assert locks["campaign:test"]["lock_hash"] == resolution.lock_hash
