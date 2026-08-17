from __future__ import annotations

import pytest

from dnd_rpg_engine.core.models import CampaignState, Entity
from dnd_rpg_engine.distributed import HandoffCoordinator, HandoffStatus, WorldPartition, ZoneDefinition, ZoneRouter


@pytest.mark.asyncio
async def test_entity_handoff_is_verified_and_two_phase() -> None:
    partition = WorldPartition(world_id="world")
    partition.register_zone(ZoneDefinition(id="a", world_id="world", neighbors={"b"}))
    partition.register_zone(ZoneDefinition(id="b", world_id="world", neighbors={"a"}))
    source = CampaignState(id="campaign", name="source")
    source.add_entity(Entity(id="hero", name="Hero"))
    partition.assign("hero", "a")
    coordinator = HandoffCoordinator(partition)
    handoff = await coordinator.prepare(source, "hero", "b", source_sequence=42)
    assert handoff.verify()
    assert handoff.status is HandoffStatus.PREPARED
    await coordinator.commit_source(source, handoff.id)
    assert "hero" not in source.entities
    assert handoff.status is HandoffStatus.SOURCE_COMMITTED

    destination = CampaignState(id="campaign", name="destination")
    hero = await coordinator.accept_target(destination, handoff, accepted_sequence=43)
    assert hero.id == "hero"
    assert hero.position.area_id == "b"
    assert handoff.status is HandoffStatus.ACCEPTED
    assert partition.zone_for("hero") == "b"


def test_zone_rendezvous_placement_is_stable() -> None:
    router = ZoneRouter()
    first = router.placement(["a", "b", "c"], ["worker-1", "worker-2"])
    second = router.placement(["a", "b", "c"], ["worker-2", "worker-1"])
    assert first == second
    assert set(first) == {"a", "b", "c"}
