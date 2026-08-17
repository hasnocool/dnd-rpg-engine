from __future__ import annotations

from typing import Any

from dnd_rpg_engine.ai.director import AIDirector, DirectorProposal
from dnd_rpg_engine.campaign.orchestrator import CampaignOrchestrator, SceneDefinition
from dnd_rpg_engine.core.advanced_engine import AdvancedGameEngine
from dnd_rpg_engine.core.commands import CustomCommand, GameCommand, WaitCommand
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.knowledge.authority import KnowledgeAuthority, KnowledgeView
from dnd_rpg_engine.rules.compiler import (
    ExecutableRuleGraph,
    RuleCompiler,
    RuleExecutionContext,
    RuleExecutionResult,
    RuleExecutor,
    RuleProvenance,
)
from dnd_rpg_engine.runtime_sync.protocol import RuntimeSnapshot, RuntimeSynchronizer


class WorldPlatformEngine(AdvancedGameEngine):
    """Integrated v1.9-v3.0 profile layered on ``AdvancedGameEngine``.

    This profile adds executable authored rules, campaign orchestration,
    knowledge authority, campaign-scale direction, and visual runtime sync while
    retaining the same external command/event contract as earlier engines.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.rule_compiler = RuleCompiler()
        self.rule_executor = RuleExecutor()
        self.rule_graphs: dict[str, ExecutableRuleGraph] = {}
        self.orchestrator = CampaignOrchestrator(self.state)
        self.knowledge = KnowledgeAuthority()
        self.ai_director = AIDirector()
        self.runtime_sync = RuntimeSynchronizer()

    def register_rule_graph(self, graph: ExecutableRuleGraph) -> None:
        if graph.graph_hash != graph.compute_hash():
            raise ValueError("cannot register an executable rule graph with an invalid hash")
        self.rule_graphs[graph.id] = graph

    def compile_rule_graph(
        self,
        rule_id: str,
        name: str,
        raw: dict[str, Any],
        *,
        provenance: RuleProvenance | None = None,
    ) -> ExecutableRuleGraph:
        graph = self.rule_compiler.compile(rule_id, name, raw, provenance=provenance)
        self.register_rule_graph(graph)
        return graph

    def compile_content_pack_rules(self, pack: Any, *, source_revision: int | None = None) -> dict[str, ExecutableRuleGraph]:
        compiled: dict[str, ExecutableRuleGraph] = {}
        for rule_id, document in sorted(pack.rules.items()):
            if not document.graph:
                continue
            graph = self.compile_rule_graph(
                rule_id,
                document.name,
                document.graph,
                provenance=RuleProvenance(
                    pack_id=pack.manifest.id,
                    pack_version=pack.manifest.version,
                    source_object_id=rule_id,
                    source_revision=source_revision,
                ),
            )
            compiled[rule_id] = graph
        return compiled

    def register_scene(self, definition: SceneDefinition) -> None:
        self.orchestrator.register(definition)

    def knowledge_view(self, actor_id: str) -> KnowledgeView:
        actor = self.state.require_entity(actor_id)
        return self.knowledge.view_for(actor, self.state)

    def runtime_snapshot(self, actor_id: str | None = None) -> RuntimeSnapshot:
        if actor_id is None:
            return self.runtime_sync.snapshot_from_state(self.state)
        return self.runtime_sync.snapshot_from_knowledge(self.knowledge_view(actor_id))

    def director_proposals(self, *, max_results: int = 8) -> list[DirectorProposal]:
        return self.ai_director.proposals(self.state, orchestrator=self.orchestrator, max_results=max_results)

    async def _execute_command(self, command: GameCommand) -> float:
        if isinstance(command, CustomCommand) and command.name == "rule.execute":
            return await self._execute_rule_command(command)
        return await super()._execute_command(command)

    async def _execute_rule_command(self, command: CustomCommand) -> float:
        rule_id = str(command.payload.get("rule_id", ""))
        if not rule_id:
            raise ValueError("rule.execute requires rule_id")
        try:
            graph = self.rule_graphs[rule_id]
        except KeyError as exc:
            raise KeyError(f"unknown executable rule graph: {rule_id}") from exc
        actor = self.state.require_entity(command.actor_id)
        target_id = command.payload.get("target_id")
        target = self.state.require_entity(str(target_id)) if target_id is not None else None
        before_hp = {entity_id: entity.resources.hp for entity_id, entity in self.state.entities.items()}
        variables_raw = command.payload.get("variables", {})
        variables = dict(variables_raw) if isinstance(variables_raw, dict) else {}
        result = self.rule_executor.execute(
            graph,
            RuleExecutionContext(
                state=self.state,
                runtime=self.combat.runtime,
                actor=actor,
                target=target,
                variables=variables,
            ),
        )
        await self._emit_rule_result(result)
        for entity_id, old_hp in before_hp.items():
            entity = self.state.entities.get(entity_id)
            if entity is None or old_hp <= 0 or entity.resources.hp > 0:
                continue
            await self._handle_zero_hp(
                entity,
                source_id=actor.id,
                damage=old_hp,
                excess_damage=0,
                was_at_zero=False,
            )
        return graph.action_time_seconds

    async def _emit_rule_result(self, result: RuleExecutionResult) -> None:
        for emitted in result.emitted:
            await self._emit(
                str(emitted.get("type", "rule.message")),
                actor_id=result.actor_id,
                target_id=result.target_id,
                payload=dict(emitted.get("payload", {})),
            )
        await self._emit(
            "rules.graph_executed",
            actor_id=result.actor_id,
            target_id=result.target_id,
            payload={
                "graph_id": result.graph_id,
                "graph_hash": result.graph_hash,
                "steps": len(result.traces),
                "variables": result.variables,
            },
        )

    async def _ai_take_action(self, actor: Entity) -> None:
        action_id = str(actor.component("ai").get("action_id", "basic_attack"))
        action = self.actions.require(action_id)
        scheduled_location, scheduled_activity = self._scheduled_intent(actor)
        command, perception, candidate = self.actor_intelligence.plan(
            actor,
            self.state,
            action=action,
            goals=self._actor_goals(actor),
            personality=self._actor_personality(actor),
            line_of_sight=self._authoritative_los,
            scheduled_location=scheduled_location,
            scheduled_activity=scheduled_activity,
        )
        self.knowledge.ingest_perception(actor, perception, self.state)
        await self._emit(
            "ai.decision",
            actor_id=actor.id,
            target_id=str(candidate.command.get("target_id")) if candidate.command.get("target_id") else None,
            payload={
                "candidate": candidate.id,
                "utility": candidate.utility,
                "reasons": candidate.reasons,
                "factors": candidate.factors,
                "nearby_allies": perception.nearby_allies,
                "nearby_hostiles": perception.nearby_hostiles,
                "knowledge_entities": len(self.knowledge.knowledge_for(actor).known_entity_ids),
            },
        )
        try:
            duration = await self._execute_command(command)
        except (ValueError, KeyError):
            await self._emit(
                "ai.plan_rejected",
                actor_id=actor.id,
                payload={"candidate": candidate.id},
            )
            duration = await self._execute_command(WaitCommand(actor_id=actor.id))
        self._schedule_actor_ready(actor.id, delay=duration)
