# tests/test_production_hosting.py
from __future__ import annotations

import pytest

from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.persistence import SQLiteStore
from dnd_rpg_engine.hosting.postgres import MIGRATIONS, PostgreSQLStore, create_store
from dnd_rpg_engine.hosting.reconnect import ReconnectManager
from dnd_rpg_engine.hosting.workers import RendezvousRouter
from dnd_rpg_engine.multiplayer.protocol import ClientIdentity, ClientRole
from dnd_rpg_engine.multiplayer.sessions import CampaignSession


def test_store_factory_and_migration_sequence(tmp_path) -> None:
    sqlite = create_store(tmp_path / "campaign.sqlite3")
    postgres = create_store("postgresql://user:password@db.example/rpg")
    assert isinstance(sqlite, SQLiteStore)
    assert isinstance(postgres, PostgreSQLStore)
    assert [migration.version for migration in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))
    assert "campaign_leases" in MIGRATIONS[1].sql


def test_rendezvous_router_is_deterministic_and_minimizes_movement() -> None:
    router = RendezvousRouter()
    workers = ["worker-a", "worker-b", "worker-c"]
    assignments = {campaign: router.choose(campaign, workers) for campaign in ["a", "b", "c", "d", "e", "f"]}
    assert assignments == {campaign: router.choose(campaign, reversed(workers)) for campaign in assignments}

    expanded = workers + ["worker-d"]
    for campaign, previous in assignments.items():
        next_worker = router.choose(campaign, expanded)
        assert next_worker in {previous, "worker-d"}


@pytest.mark.asyncio
async def test_reconnect_ticket_is_rotated_and_replays_from_checkpoint(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "resume.sqlite3")
    await store.initialize()
    engine = await GameEngine.create("Reconnect", store=store)
    session = CampaignSession(engine.state.id, engine, owner_id="owner")
    identity = ClientIdentity(user_id="owner", display_name="Owner", role=ClientRole.OWNER)
    session.join(identity)

    manager = ReconnectManager(store, default_ttl_seconds=60)
    ticket = await manager.issue(engine.state.id, identity, last_event_sequence=4)
    assert ticket.token
    assert await store.get_json("resume_ticket", ticket.token) is None

    await manager.checkpoint(ticket.token, 8)
    session.leave(identity.client_id)
    result, rotated = await manager.resume(ticket.token, session)
    assert result.client.client_id == identity.client_id
    assert result.replay_after_sequence == 8
    assert rotated is not None
    assert rotated.token != ticket.token
    assert session.require_client(identity.client_id).role is ClientRole.OWNER

    with pytest.raises(PermissionError):
        await manager.resume(ticket.token, session)
