from __future__ import annotations

import pytest

from dnd_rpg_engine.core.commands import WaitCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind
from dnd_rpg_engine.multiplayer.protocol import ClientIdentity
from dnd_rpg_engine.multiplayer.reliable import BackpressureBuffer, ReliableCampaignGateway, ReliableCommandEnvelope, SequenceGapError
from dnd_rpg_engine.multiplayer.sessions import CampaignSession


@pytest.mark.asyncio
async def test_reliable_gateway_deduplicates_sequence_without_reexecuting() -> None:
    engine = await GameEngine.create("test")
    hero = Entity(id="hero", name="Hero", kind=EntityKind.PLAYER, controller=ControllerKind.HUMAN, owner_id="u1")
    await engine.add_entity(hero)
    session = CampaignSession(engine.state.id, engine, owner_id="u1")
    client = ClientIdentity(user_id="u1", display_name="User")
    session.join(client)
    gateway = ReliableCampaignGateway()
    command = WaitCommand(actor_id="hero", command_id="cmd-1").model_dump(mode="json")
    envelope = ReliableCommandEnvelope(client_id=client.client_id, client_sequence=1, command=command)
    first = await gateway.dispatch(session, envelope)
    duplicate = await gateway.dispatch(session, envelope)
    assert duplicate.duplicate
    assert duplicate.engine_version == first.engine_version
    assert gateway.state_for(engine.state.id, client.client_id).next_client_sequence == 2
    with pytest.raises(SequenceGapError):
        await gateway.dispatch(
            session,
            ReliableCommandEnvelope(client_id=client.client_id, client_sequence=3, command=command),
        )


def test_backpressure_buffer_is_bounded_and_coalesces_state() -> None:
    buffer = BackpressureBuffer(max_items=3)
    buffer.push("state", {"n": 1})
    buffer.push("state", {"n": 2})
    buffer.push("presence", {"n": 3})
    buffer.push("event", {"n": 4}, critical=True)
    values = buffer.drain()
    assert len(values) <= 3
    states = [value for value in values if value.kind == "state"]
    assert len(states) == 1 and states[0].payload["n"] == 2
