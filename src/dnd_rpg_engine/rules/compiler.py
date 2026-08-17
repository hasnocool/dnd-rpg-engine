from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from dnd_rpg_engine.core.models import CampaignState, Entity
from dnd_rpg_engine.rules.effects import EffectDefinition
from dnd_rpg_engine.rules.runtime import DamagePacket, ResolutionContext, RollRequest, RulesRuntime


class RuleOp(StrEnum):
    NOOP = "noop"
    ROLL = "roll"
    DAMAGE = "damage"
    HEAL = "heal"
    SET = "set"
    INCREMENT = "increment"
    CONSUME_RESOURCE = "consume_resource"
    RESTORE_RESOURCE = "restore_resource"
    APPLY_EFFECT = "apply_effect"
    OPEN_REACTION = "open_reaction"
    IF = "if"
    EMIT = "emit"
    STOP = "stop"


class RuleProvenance(BaseModel):
    pack_id: str = "runtime"
    pack_version: str = "0"
    source_object_id: str | None = None
    source_revision: int | None = None
    source_document: str | None = None
    source_page: int | None = None
    compiler_version: str = "1"


class RuleNode(BaseModel):
    id: str
    op: RuleOp
    args: dict[str, Any] = Field(default_factory=dict)
    next: str | None = None
    on_success: str | None = None
    on_failure: str | None = None


class ExecutableRuleGraph(BaseModel):
    id: str
    name: str
    entry: str
    nodes: dict[str, RuleNode]
    effects: dict[str, EffectDefinition] = Field(default_factory=dict)
    capabilities: set[str] = Field(default_factory=set)
    action_time_seconds: float = Field(default=0.0, ge=0.0)
    provenance: RuleProvenance = Field(default_factory=RuleProvenance)
    graph_hash: str = ""

    @model_validator(mode="after")
    def _validate_links(self) -> "ExecutableRuleGraph":
        if self.entry not in self.nodes:
            raise ValueError(f"rule graph entry does not exist: {self.entry}")
        for key, node in self.nodes.items():
            if node.id != key:
                raise ValueError(f"rule node key/id mismatch: {key} != {node.id}")
            for target in (node.next, node.on_success, node.on_failure):
                if target is not None and target not in self.nodes:
                    raise ValueError(f"rule node {node.id} references missing node {target}")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["graph_hash"] = ""
        return payload

    def compute_hash(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


class RuleCompiler:
    """Compile bounded declarative rule data into a validated rule graph.

    The compiler intentionally has no eval/exec/script escape hatch. All
    executable behavior must be represented by a known ``RuleOp`` so authored
    content remains deterministic, inspectable, replay-safe, and server-safe.
    """

    compiler_version = "1"
    max_nodes = 512
    max_effects = 128

    def compile(
        self,
        rule_id: str,
        name: str,
        raw: dict[str, Any],
        *,
        provenance: RuleProvenance | None = None,
    ) -> ExecutableRuleGraph:
        node_rows = raw.get("nodes", {})
        if isinstance(node_rows, list):
            node_rows = {str(row["id"]): row for row in node_rows}
        if not isinstance(node_rows, dict) or not node_rows:
            raise ValueError("executable rule graph requires nodes")
        if len(node_rows) > self.max_nodes:
            raise ValueError(f"rule graph exceeds {self.max_nodes} nodes")

        nodes: dict[str, RuleNode] = {}
        for key, value in sorted(node_rows.items(), key=lambda item: str(item[0])):
            row = dict(value)
            row.setdefault("id", str(key))
            node = RuleNode.model_validate(row)
            self._validate_node(node)
            nodes[node.id] = node

        effect_rows = raw.get("effects", {})
        if isinstance(effect_rows, list):
            effect_rows = {str(row["id"]): row for row in effect_rows}
        if not isinstance(effect_rows, dict):
            raise ValueError("rule graph effects must be an object or list")
        if len(effect_rows) > self.max_effects:
            raise ValueError(f"rule graph exceeds {self.max_effects} effects")
        effects = {str(key): EffectDefinition.model_validate(value) for key, value in sorted(effect_rows.items())}

        source = provenance or RuleProvenance(compiler_version=self.compiler_version)
        source.compiler_version = self.compiler_version
        graph = ExecutableRuleGraph(
            id=rule_id,
            name=name,
            entry=str(raw.get("entry") or next(iter(nodes))),
            nodes=nodes,
            effects=effects,
            capabilities={str(value) for value in raw.get("capabilities", [])},
            action_time_seconds=float(raw.get("action_time_seconds", 0.0)),
            provenance=source,
        )
        return graph.model_copy(update={"graph_hash": graph.compute_hash()})

    def _validate_node(self, node: RuleNode) -> None:
        args = node.args
        if node.op is RuleOp.ROLL:
            expression = str(args.get("expression", "1d20"))
            if len(expression) > 64:
                raise ValueError("roll expression is too long")
        elif node.op in {RuleOp.DAMAGE, RuleOp.HEAL}:
            if "amount" not in args and "expression" not in args:
                raise ValueError(f"{node.op.value} requires amount or expression")
        elif node.op in {RuleOp.SET, RuleOp.INCREMENT}:
            path = str(args.get("path", ""))
            if not path.startswith(("state.flags.", "actor.components.", "target.components.")):
                raise ValueError(f"unsafe rule state path: {path}")
        elif node.op in {RuleOp.CONSUME_RESOURCE, RuleOp.RESTORE_RESOURCE}:
            if not str(args.get("resource", "")):
                raise ValueError(f"{node.op.value} requires resource")
        elif node.op is RuleOp.APPLY_EFFECT:
            if not str(args.get("effect_id", "")):
                raise ValueError("apply_effect requires effect_id")
        elif node.op is RuleOp.OPEN_REACTION:
            timeout = float(args.get("timeout", 0.0))
            if timeout < 0 or timeout > 600:
                raise ValueError("reaction timeout must be between 0 and 600 seconds")
        elif node.op is RuleOp.IF:
            if str(args.get("operator", "")) not in {"eq", "ne", "lt", "lte", "gt", "gte", "in", "contains", "truthy"}:
                raise ValueError("if node has unsupported operator")


class RuleStepTrace(BaseModel):
    node_id: str
    op: RuleOp
    result: Any = None
    branch: str | None = None


class RuleExecutionResult(BaseModel):
    graph_id: str
    graph_hash: str
    actor_id: str
    target_id: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    traces: list[RuleStepTrace] = Field(default_factory=list)
    emitted: list[dict[str, Any]] = Field(default_factory=list)
    stopped: bool = False


@dataclass(slots=True)
class RuleExecutionContext:
    state: CampaignState
    runtime: RulesRuntime
    actor: Entity
    target: Entity | None = None
    variables: dict[str, Any] | None = None


class RuleExecutor:
    max_steps = 2048

    def execute(self, graph: ExecutableRuleGraph, context: RuleExecutionContext) -> RuleExecutionResult:
        if graph.graph_hash != graph.compute_hash():
            raise ValueError("rule graph hash verification failed")
        for effect in graph.effects.values():
            context.runtime.effects.register(effect)

        variables = dict(context.variables or {})
        traces: list[RuleStepTrace] = []
        emitted: list[dict[str, Any]] = []
        current: str | None = graph.entry
        steps = 0
        stopped = False
        while current is not None:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("rule graph exceeded deterministic step budget")
            node = graph.nodes[current]
            result, success = self._execute_node(node, context, variables, emitted)
            branch = node.on_success if success else node.on_failure
            next_node = branch if branch is not None else node.next
            traces.append(RuleStepTrace(node_id=node.id, op=node.op, result=result, branch=next_node))
            if node.op is RuleOp.STOP:
                stopped = True
                break
            current = next_node

        return RuleExecutionResult(
            graph_id=graph.id,
            graph_hash=graph.graph_hash,
            actor_id=context.actor.id,
            target_id=context.target.id if context.target else None,
            variables=variables,
            traces=traces,
            emitted=emitted,
            stopped=stopped,
        )

    def _execute_node(
        self,
        node: RuleNode,
        context: RuleExecutionContext,
        variables: dict[str, Any],
        emitted: list[dict[str, Any]],
    ) -> tuple[Any, bool]:
        args = node.args
        op = node.op
        if op in {RuleOp.NOOP, RuleOp.STOP}:
            return None, True
        if op is RuleOp.ROLL:
            base = int(self._value(args.get("modifier", 0), context, variables))
            target_raw = args.get("target")
            target = None if target_raw is None else int(self._value(target_raw, context, variables))
            outcome = context.runtime.resolve_roll(
                RollRequest(
                    expression=str(args.get("expression", "1d20")),
                    stream=str(args.get("stream", f"rule:{node.id}:{context.actor.id}")),
                    base_modifier=base,
                    target=target,
                    context=ResolutionContext(
                        actor_id=context.actor.id,
                        target_id=context.target.id if context.target else None,
                        action_id=str(args.get("action_id") or node.id),
                        tags={str(value) for value in args.get("tags", [])},
                    ),
                )
            )
            variables[str(args.get("result", node.id))] = outcome.model_dump(mode="json")
            return outcome.model_dump(mode="json"), outcome.success is not False
        if op is RuleOp.DAMAGE:
            target = self._subject(str(args.get("target", "target")), context)
            amount = self._amount(args, context, variables, stream=f"rule:damage:{node.id}")
            packet = DamagePacket(
                amount=amount,
                damage_type=str(args.get("damage_type", "physical")),
                source_id=context.actor.id,
                tags={str(value) for value in args.get("tags", [])},
            )
            outcome = context.runtime.resolve_damage(target, packet)
            applied = target.resources.apply_damage(outcome.after_traits)
            variables[str(args.get("result", node.id))] = applied
            return {"damage": applied, "resolution": outcome.model_dump(mode="json")}, applied > 0
        if op is RuleOp.HEAL:
            target = self._subject(str(args.get("target", "target")), context)
            amount = self._amount(args, context, variables, stream=f"rule:heal:{node.id}")
            healed = target.resources.heal(amount)
            variables[str(args.get("result", node.id))] = healed
            return {"healed": healed}, healed > 0
        if op in {RuleOp.SET, RuleOp.INCREMENT}:
            path = str(args["path"])
            incoming = self._value(args.get("value", 0), context, variables)
            before = self._path_get(path, context)
            value = incoming if op is RuleOp.SET else self._numeric(before) + self._numeric(incoming)
            self._path_set(path, value, context)
            return {"path": path, "before": before, "after": value}, True
        if op in {RuleOp.CONSUME_RESOURCE, RuleOp.RESTORE_RESOURCE}:
            target = self._subject(str(args.get("target", "actor")), context)
            resource = str(args["resource"])
            amount = max(0, int(self._value(args.get("amount", 1), context, variables)))
            before, after = self._resource_change(target, resource, amount, restore=op is RuleOp.RESTORE_RESOURCE)
            return {"resource": resource, "before": before, "after": after}, before != after
        if op is RuleOp.APPLY_EFFECT:
            target = self._subject(str(args.get("target", "target")), context)
            effect_id = str(args["effect_id"])
            instance = context.runtime.effects.apply(
                effect_id,
                target.id,
                source_id=context.actor.id,
                now=context.state.simulation_time,
                stacks=max(1, int(args.get("stacks", 1))),
                metadata={"rule_node": node.id, "rule_actor": context.actor.id},
            )
            return instance.model_dump(mode="json"), True
        if op is RuleOp.OPEN_REACTION:
            target = self._subject(str(args.get("target", "target")), context)
            opportunity = context.runtime.open_reaction(
                target.id,
                str(args.get("trigger", "rule")),
                source_id=context.actor.id,
                target_id=context.target.id if context.target else None,
                now=context.state.simulation_time,
                timeout=float(args.get("timeout", 0.0)) or None,
                options=[str(value) for value in args.get("options", [])],
                metadata={"rule_node": node.id},
            )
            return opportunity.model_dump(mode="json"), True
        if op is RuleOp.IF:
            left = self._value(args.get("left"), context, variables)
            right = self._value(args.get("right"), context, variables)
            success = self._compare(left, right, str(args["operator"]))
            return {"left": left, "right": right, "matched": success}, success
        if op is RuleOp.EMIT:
            payload = {
                "type": str(args.get("type", "rule.message")),
                "payload": self._materialize(dict(args.get("payload", {})), context, variables),
                "source_node": node.id,
            }
            emitted.append(payload)
            return payload, True
        raise ValueError(f"unsupported rule op: {op}")

    def _amount(self, args: dict[str, Any], context: RuleExecutionContext, variables: dict[str, Any], *, stream: str) -> int:
        if "expression" in args:
            return max(0, int(context.runtime.dice.roll(str(args["expression"]), stream=stream).total))
        return max(0, int(self._value(args.get("amount", 0), context, variables)))

    def _subject(self, name: str, context: RuleExecutionContext) -> Entity:
        if name == "actor":
            return context.actor
        if name == "target" and context.target is not None:
            return context.target
        if name.startswith("entity:"):
            return context.state.require_entity(name.split(":", 1)[1])
        raise ValueError(f"rule subject is unavailable: {name}")

    def _value(self, value: Any, context: RuleExecutionContext, variables: dict[str, Any]) -> Any:
        if not isinstance(value, str) or not value.startswith("$"):
            return value
        if value.startswith("$var."):
            return variables.get(value[5:])
        if value.startswith("$state.flags."):
            return context.state.flags.get(value[len("$state.flags."):])
        for prefix, entity in (("$actor.", context.actor), ("$target.", context.target)):
            if value.startswith(prefix):
                if entity is None:
                    return None
                suffix = value[len(prefix):]
                if suffix == "hp":
                    return entity.resources.hp
                if suffix == "max_hp":
                    return entity.resources.max_hp
                if suffix == "energy":
                    return entity.resources.energy
                if suffix.startswith("stat."):
                    return getattr(entity.stats, suffix[5:])
                if suffix.startswith("mod."):
                    return entity.stats.modifier(suffix[4:])
                if suffix.startswith("component."):
                    component, _, key = suffix[len("component."):].partition(".")
                    return entity.component(component).get(key)
        raise ValueError(f"unsupported rule value reference: {value}")

    def _materialize(self, value: Any, context: RuleExecutionContext, variables: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {str(key): self._materialize(item, context, variables) for key, item in value.items()}
        if isinstance(value, list):
            return [self._materialize(item, context, variables) for item in value]
        return self._value(value, context, variables)

    def _path_get(self, path: str, context: RuleExecutionContext) -> Any:
        if path.startswith("state.flags."):
            return context.state.flags.get(path[len("state.flags."):])
        entity, rest = self._component_path(path, context)
        component, _, key = rest.partition(".")
        if not component or not key:
            raise ValueError("component path must include component and key")
        return entity.component(component).get(key)

    def _path_set(self, path: str, value: Any, context: RuleExecutionContext) -> None:
        if path.startswith("state.flags."):
            context.state.flags[path[len("state.flags."):]] = value
            return
        entity, rest = self._component_path(path, context)
        component, _, key = rest.partition(".")
        if not component or not key:
            raise ValueError("component path must include component and key")
        entity.component(component)[key] = value

    def _component_path(self, path: str, context: RuleExecutionContext) -> tuple[Entity, str]:
        if path.startswith("actor.components."):
            return context.actor, path[len("actor.components."):]
        if path.startswith("target.components.") and context.target is not None:
            return context.target, path[len("target.components."):]
        raise ValueError(f"unsafe or unavailable state path: {path}")

    @staticmethod
    def _numeric(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("increment requires numeric state")
        return float(value)

    @staticmethod
    def _compare(left: Any, right: Any, operator: str) -> bool:
        if operator == "truthy":
            return bool(left)
        if operator == "eq":
            return left == right
        if operator == "ne":
            return left != right
        if operator == "lt":
            return left < right
        if operator == "lte":
            return left <= right
        if operator == "gt":
            return left > right
        if operator == "gte":
            return left >= right
        if operator == "in":
            return left in right
        if operator == "contains":
            return right in left
        raise ValueError(f"unsupported comparison operator: {operator}")

    @staticmethod
    def _resource_change(entity: Entity, resource: str, amount: int, *, restore: bool) -> tuple[int, int]:
        if resource == "energy":
            before = entity.resources.energy
            entity.resources.energy = min(entity.resources.max_energy, before + amount) if restore else max(0, before - amount)
            return before, entity.resources.energy
        if resource == "hp":
            before = entity.resources.hp
            if restore:
                entity.resources.heal(amount)
            else:
                entity.resources.apply_damage(amount)
            return before, entity.resources.hp
        raw = entity.component("character_resources").get(resource)
        if not isinstance(raw, dict):
            raise KeyError(f"unknown character resource: {resource}")
        before = int(raw.get("current", 0))
        maximum = int(raw.get("maximum", before))
        if restore:
            raw["current"] = min(maximum, before + amount)
        else:
            if before < amount:
                raise ValueError(f"insufficient {resource}")
            raw["current"] = before - amount
        return before, int(raw["current"])
