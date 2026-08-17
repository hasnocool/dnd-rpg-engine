from __future__ import annotations

import pytest

from dnd_rpg_engine.ai.director import AIDirector, DirectorProposalKind
from dnd_rpg_engine.ai.intelligence import PerceptionSystem
from dnd_rpg_engine.campaign.orchestrator import CampaignOrchestrator, SceneDefinition, SceneKind, SceneStatus
from dnd_rpg_engine.core.commands import CustomCommand
from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.models import CampaignState, ControllerKind, Entity, EntityKind, GameConfig, Position, ResourcePool, TimeMode
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.core.world_engine import WorldPlatformEngine
from dnd_rpg_engine.creator.content import ContentPack, ModManifest, RuleDocument
from dnd_rpg_engine.distributed.world import ShardDirectory, TransferCoordinator, TransferStatus, WorldShard
from dnd_rpg_engine.distribution.packages import ContentDistributionIndex, HMACPackageSigner, PackageRelease
from dnd_rpg_engine.knowledge.authority import KnowledgeAuthority
from dnd_rpg_engine.rules.compiler import RuleCompiler, RuleExecutionContext, RuleExecutor
from dnd_rpg_engine.rules.runtime import RulesRuntime
from dnd_rpg_engine.runtime_sync.protocol import RuntimeSynchronizer
from dnd_rpg_engine.simulation.lab import SimulationLab, SimulationSample, SimulationScenario
from dnd_rpg_engine.tactical.conditions import default_conditions


def _actor(entity_id: str, *, hp: int = 12, x: float = 0.0) -> Entity:
    return Entity(
        id=entity_id,
        name=entity_id.title(),
        kind=EntityKind.PLAYER if entity_id == "hero" else EntityKind.CREATURE,
        controller=ControllerKind.HUMAN if entity_id == "hero" else ControllerKind.AI,
        resources=ResourcePool(hp=hp, max_hp=hp),
        position=Position(area_id="arena", x=x, y=0),
    )


def _damage_graph() -> dict:
    return {
        "entry": "damage",
        "action_time_seconds": 2.5,
        "nodes": {
            "damage": {
                "id": "damage",
                "op": "damage",
                "args": {"target": "target", "amount": 5, "damage_type": "arcane", "result": "dealt"},
                "next": "mark",
            },
            "mark": {
                "id": "mark",
                "op": "set",
                "args": {"path": "state.flags.rule_hit", "value": True},
                "next": "message",
            },
            "message": {
                "id": "message",
                "op": "emit",
                "args": {"type": "rule.example", "payload": {"remaining_hp": "$target.hp", "damage": "$var.dealt"}},
            },
        },
    }


def test_rule_compiler_executes_bounded_graph_and_round_trips_content() -> None:
    compiler = RuleCompiler()
    graph = compiler.compile("example_rule", "Example Rule", _damage_graph())
    state = CampaignState(name="rules", entities={"hero": _actor("hero"), "foe": _actor("foe")})
    runtime = RulesRuntime(RuleSet(), DeterministicDice(7), default_conditions())
    result = RuleExecutor().execute(
        graph,
        RuleExecutionContext(state=state, runtime=runtime, actor=state.entities["hero"], target=state.entities["foe"]),
    )
    assert state.entities["foe"].resources.hp == 7
    assert state.flags["rule_hit"] is True
    assert result.variables["dealt"] == 5
    assert result.emitted[0]["type"] == "rule.example"
    assert result.graph_hash == graph.compute_hash()

    tampered = graph.model_copy(update={"graph_hash": "0" * 64})
    with pytest.raises(ValueError, match="hash verification"):
        RuleExecutor().execute(
            tampered,
            RuleExecutionContext(state=state, runtime=runtime, actor=state.entities["hero"], target=state.entities["foe"]),
        )

    pack = ContentPack(
        manifest=ModManifest(id="example.rules", name="Example"),
        rules={"example_rule": RuleDocument(id="example_rule", name="Example Rule", graph=_damage_graph())},
    )
    restored = ContentPack.from_zip_bytes(pack.to_zip_bytes())
    assert restored.rules["example_rule"].graph["entry"] == "damage"
    assert restored.content_hash() == pack.content_hash()


def test_campaign_orchestrator_streams_only_active_scene_entities() -> None:
    state = CampaignState(name="orchestration", entities={"hero": _actor("hero"), "foe": _actor("foe")})
    orchestrator = CampaignOrchestrator(state)
    orchestrator.register(
        SceneDefinition(id="town", name="Town", kind=SceneKind.SETTLEMENT, entity_ids={"hero"}, next_scene_ids=["road"])
    )
    orchestrator.register(
        SceneDefinition(id="road", name="Road", kind=SceneKind.TRAVEL, entity_ids={"hero", "foe"})
    )
    transition = orchestrator.activate("town")
    assert transition.status is SceneStatus.ACTIVE
    assert orchestrator.streaming_entity_ids() == {"hero"}
    orchestrator.resolve("town")
    orchestrator.activate("road")
    assert orchestrator.streaming_entity_ids() == {"hero", "foe"}
    assert state.metadata[orchestrator.metadata_key]["active_scene_ids"] == ["road"]


def test_knowledge_authority_prevents_stale_live_truth_and_runtime_deltas_round_trip() -> None:
    hero = _actor("hero")
    foe = _actor("foe", x=2)
    foe.components["secret"] = {"plan": "hidden"}
    unseen = _actor("unseen", x=100)
    state = CampaignState(name="knowledge", entities={entity.id: entity for entity in (hero, foe, unseen)})
    perception = PerceptionSystem().observe(hero, state)
    authority = KnowledgeAuthority()
    authority.ingest_perception(hero, perception, state)

    first_view = authority.view_for(hero, state)
    assert "foe" in first_view.entities
    assert "unseen" not in first_view.entities
    assert "secret" not in first_view.entities["foe"]["components"]
    remembered_hp = first_view.entities["foe"]["resources"]["hp"]

    state.simulation_time = 10
    foe.resources.apply_damage(4)
    stale_view = authority.view_for(hero, state)
    assert stale_view.entities["foe"]["resources"]["hp"] == remembered_hp

    synchronizer = RuntimeSynchronizer()
    first = synchronizer.snapshot_from_knowledge(first_view)
    second_perception = PerceptionSystem().observe(hero, state)
    authority.ingest_perception(hero, second_perception, state)
    second = synchronizer.snapshot_from_knowledge(authority.view_for(hero, state))
    delta = synchronizer.diff(first, second)
    applied = synchronizer.apply(first, delta)
    assert applied.snapshot_hash == second.snapshot_hash
    assert applied.entities["foe"]["resources"]["hp"] == foe.resources.hp


@pytest.mark.asyncio
async def test_simulation_lab_and_ai_director_are_deterministic() -> None:
    async def run_once(seed: int) -> SimulationSample:
        return SimulationSample(
            seed=seed,
            outcome="party" if seed % 2 else "foes",
            metrics={"rounds": float(3 + seed % 4), "remaining_hp": float(seed % 11)},
            event_counts={"attack": 2 + seed % 3},
        )

    lab = SimulationLab(max_concurrency=4)
    report = await lab.run(SimulationScenario(id="arena", run_once=run_once), lab.seed_matrix(start=1, count=20))
    assert report.sample_count == 20
    assert report.outcomes == {"foes": 10, "party": 10}
    assert report.metrics["rounds"].minimum >= 3

    state = CampaignState(name="director", entities={"hero": _actor("hero", hp=4)})
    state.metadata["director_pressure"] = 0.85
    proposals = AIDirector().proposals(state)
    assert proposals == sorted(proposals, key=lambda value: (-value.utility, value.kind.value, value.id))
    assert any(value.kind is DirectorProposalKind.PACING for value in proposals)
    assert any(value.kind is DirectorProposalKind.DOWNTIME for value in proposals)


def test_distribution_resolution_signatures_and_cross_shard_transfer() -> None:
    index = ContentDistributionIndex()
    base = PackageRelease(package_id="base", version="1.0.0", content_hash="a" * 64, engine_requirement=">=1.0.0")
    addon = PackageRelease(
        package_id="addon",
        version="2.1.0",
        content_hash="b" * 64,
        engine_requirement=">=2.0.0",
        dependencies={"base": "^1.0.0"},
    )
    signer = HMACPackageSigner("test-key", b"0123456789abcdef0123456789abcdef")
    addon.signature = signer.sign(addon.signing_payload())
    index.publish(base)
    index.publish(addon)
    resolution = index.resolve({"addon": "^2.0.0"}, engine_version="3.0.0")
    assert resolution.order == ["base", "addon"]
    assert resolution.releases["addon"].version == "2.1.0"
    assert index.verify_release_signature(addon, signer)

    directory = ShardDirectory()
    directory.register(WorldShard(id="west", regions={"island"}, capacity=10))
    directory.register(WorldShard(id="east", capacity=10))
    assert directory.route("island").id == "west"

    coordinator = TransferCoordinator()
    entity = _actor("hero")
    transfer = coordinator.prepare(entity, source_shard="west", target_shard="east", target_region="mainland", now=1.0)
    coordinator.accept(transfer.id, destination_hash=transfer.state_hash)
    coordinator.commit(transfer.id, now=2.0)
    assert transfer.status is TransferStatus.COMMITTED
    assert coordinator.restore_entity(transfer.id).model_dump(mode="json") == entity.model_dump(mode="json")
    message = coordinator.message(source_shard="west", target_shard="east", topic="entity.transfer", idempotency_key="once")
    assert coordinator.receive(message) is True
    assert coordinator.receive(message) is False


@pytest.mark.asyncio
async def test_world_platform_engine_executes_compiled_rule_commands() -> None:
    engine = await WorldPlatformEngine.create(
        "World Platform",
        config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=22),
    )
    hero = _actor("hero")
    foe = _actor("foe")
    await engine.add_entity(hero)
    await engine.add_entity(foe)
    graph = engine.compile_rule_graph("example_rule", "Example Rule", _damage_graph())
    duration = await engine._execute_command(
        CustomCommand(actor_id="hero", name="rule.execute", payload={"rule_id": graph.id, "target_id": "foe"})
    )
    assert duration == 2.5
    assert foe.resources.hp == 7
    assert engine.state.flags["rule_hit"] is True
    assert engine.runtime_snapshot("hero").campaign_id == engine.state.id
