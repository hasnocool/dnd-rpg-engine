# tests/test_multiplayer.py
import asyncio

from dnd_rpg_engine.core.commands import WaitCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, TimeMode, GameConfig
from dnd_rpg_engine.multiplayer.protocol import ClientIdentity, ClientRole
from dnd_rpg_engine.multiplayer.sessions import CampaignSession


def test_spectators_cannot_issue_authoritative_commands() -> None:
    async def scenario() -> None:
        engine = await GameEngine.create(config=GameConfig(time_mode=TimeMode.REAL_TIME))
        await engine.add_entity(Entity(id="hero", name="Hero", kind=EntityKind.PLAYER, controller=ControllerKind.HUMAN))
        session = CampaignSession(engine.state.id, engine, owner_id="owner")
        spectator = ClientIdentity(user_id="viewer", display_name="Viewer", role=ClientRole.SPECTATOR)
        session.join(spectator)
        try:
            await session.dispatch(spectator.client_id, WaitCommand(actor_id="hero"))
        except PermissionError:
            pass
        else:
            raise AssertionError("spectator command should have been rejected")

    asyncio.run(scenario())
