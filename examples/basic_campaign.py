# examples/basic_campaign.py
from __future__ import annotations

import asyncio

from dnd_rpg_engine.core.commands import WaitCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, GameConfig, Position, ResourcePool, TimeMode


async def main() -> None:
    engine = await GameEngine.create(
        "Example Campaign",
        config=GameConfig(
            time_mode=TimeMode.HYBRID,
            seed=42,
            player_decision_timeout_seconds=5,
            pause_when_player_ready=True,
        ),
    )
    await engine.add_entity(
        Entity(
            id="hero",
            name="Hero",
            kind=EntityKind.PLAYER,
            controller=ControllerKind.HUMAN,
            resources=ResourcePool(hp=30, max_hp=30, energy=5, max_energy=5),
            position=Position(area_id="courtyard", x=0, y=0),
        )
    )
    await engine.add_entity(
        Entity(
            id="rival",
            name="Clockwork Rival",
            kind=EntityKind.CREATURE,
            controller=ControllerKind.AI,
            resources=ResourcePool(hp=24, max_hp=24),
            position=Position(area_id="courtyard", x=1, y=0),
            components={"ai": {"target_id": "hero"}},
        )
    )

    # The first tick opens the five-second decision window. Waiting beyond it
    # releases the same timeline and AI readiness keeps recurring.
    for _ in range(14):
        result = await engine.tick(1.0)
        for event in result.events:
            print(f"[{event.simulation_time:6.2f}] {event.type}: {event.payload}")

    if "hero" in engine.state_payload()["ready_humans"]:
        await engine.dispatch(WaitCommand(actor_id="hero"))


if __name__ == "__main__":
    asyncio.run(main())
