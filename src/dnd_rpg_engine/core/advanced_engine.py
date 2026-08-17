# src/dnd_rpg_engine/core/advanced_engine.py
from __future__ import annotations

from typing import Any

from dnd_rpg_engine.ai.intelligence import Goal, GoalKind, IntelligentActorController
from dnd_rpg_engine.core.commands import CustomCommand, GameCommand, MoveCommand, WaitCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.spatial import ContinuousSpace, GraphSpace, GridSpace, SpatialAuthority, Vector3


class AdvancedGameEngine(GameEngine):
    """Integrated v1.2-v1.5 engine profile.

    The base ``GameEngine`` stays backward compatible. This subclass opts a
    campaign into authoritative spatial validation and the intelligent-actor
    planner while preserving the same command/event, scheduler, persistence,
    and multiplayer contracts.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.spatial = SpatialAuthority()
        self.actor_intelligence = IntelligentActorController()

    def register_spatial_space(self, space: GraphSpace | GridSpace | ContinuousSpace) -> None:
        self.spatial.register(space)

    async def _execute_command(self, command: GameCommand) -> float:
        if isinstance(command, CustomCommand) and command.name == "spatial_move":
            return await self._spatial_move(command)
        return await super()._execute_command(command)

    async def _move(self, command: MoveCommand) -> float:
        actor = self.state.require_entity(command.actor_id)
        space_id = str(actor.component("spatial").get("space_id", ""))
        if not space_id or space_id not in self.spatial.spaces:
            return await super()._move(command)
        if command.map_id and command.map_id != space_id:
            raise ValueError("cross-space movement must use custom.spatial_move")

        space = self.spatial.require(space_id)
        movement = actor.component("movement")
        speed = float(movement.get("units_per_second", 1.5))
        if speed <= 0:
            raise ValueError("actor cannot move")
        budget_raw = movement.get("remaining", movement.get("budget"))
        budget = None if budget_raw is None else float(budget_raw)

        if isinstance(space, GridSpace):
            if abs(command.x - round(command.x)) > 1e-9 or abs(command.y - round(command.y)) > 1e-9:
                raise ValueError("grid movement requires integer x/y coordinates")
            destination = (int(round(command.x)), int(round(command.y)))
            validation = space.validate_move(actor.id, destination, max_cost=budget)
        elif isinstance(space, ContinuousSpace):
            destination = Vector3(x=command.x, y=command.y, z=command.z)
            validation = space.validate_move(actor.id, destination, max_distance=budget)
        else:
            raise ValueError("graph movement must use custom.spatial_move with a node destination")

        if not validation.allowed:
            raise ValueError(validation.reason or "spatial movement rejected")
        duration = await super()._move(command)
        if isinstance(space, GridSpace):
            space.place(actor.id, destination)
        else:
            radius = float(actor.component("spatial").get("radius", 0.0))
            space.place(actor.id, destination, radius=radius)
        if budget is not None:
            movement["remaining"] = max(0.0, budget - validation.cost)
        return duration

    async def _spatial_move(self, command: CustomCommand) -> float:
        actor = self.state.require_entity(command.actor_id)
        payload = command.payload
        space_id = str(payload.get("space_id") or actor.component("spatial").get("space_id", ""))
        if not space_id:
            raise ValueError("spatial_move requires a space_id")
        space = self.spatial.require(space_id)
        destination = payload.get("destination")
        if destination is None:
            raise ValueError("spatial_move requires destination")

        movement = actor.component("movement")
        speed = float(movement.get("units_per_second", 1.5))
        if speed <= 0:
            raise ValueError("actor cannot move")
        budget_raw = payload.get("budget", movement.get("remaining"))
        budget = None if budget_raw is None else float(budget_raw)
        validation = self.spatial.validate_move(space_id, actor.id, destination, budget=budget)
        if not validation.allowed:
            raise ValueError(validation.reason or "spatial movement rejected")

        old = actor.position.model_copy(deep=True)
        actor.component("spatial")["space_id"] = space_id
        if isinstance(space, GraphSpace):
            node_id = str(destination)
            space.place(actor.id, node_id)
            actor.position.area_id = space_id
            actor.position.node_id = node_id
        elif isinstance(space, GridSpace):
            cell = tuple(destination)
            grid_destination = (int(cell[0]), int(cell[1]))
            space.place(actor.id, grid_destination)
            actor.position.area_id = space_id
            actor.position.node_id = None
            actor.position.x = float(grid_destination[0])
            actor.position.y = float(grid_destination[1])
            actor.position.z = 0.0
        else:
            point = destination if isinstance(destination, Vector3) else Vector3.model_validate(destination)
            radius = float(actor.component("spatial").get("radius", 0.0))
            space.place(actor.id, point, radius=radius)
            actor.position.area_id = space_id
            actor.position.node_id = None
            actor.position.x = point.x
            actor.position.y = point.y
            actor.position.z = point.z

        if budget is not None:
            movement["remaining"] = max(0.0, budget - validation.cost)
        duration = max(0.25, validation.cost / speed)
        await self._emit(
            "entity.moved",
            actor_id=actor.id,
            target_id=space_id,
            payload={
                "from": old.model_dump(mode="json"),
                "to": actor.position.model_dump(mode="json"),
                "distance": validation.cost,
                "path": validation.path,
                "spatial_mode": space.mode.value,
            },
        )
        self.exploration.visit(actor.id, actor.position.area_id)
        await self._emit("location.visited", actor_id=actor.id, target_id=actor.position.area_id)
        return duration

    def _actor_goals(self, actor: Entity) -> list[Goal]:
        raw_goals = actor.component("ai").get("goals", [])
        goals: list[Goal] = []
        for index, raw in enumerate(raw_goals):
            if isinstance(raw, dict):
                goals.append(Goal.model_validate(raw))
            elif isinstance(raw, str):
                try:
                    kind = GoalKind(raw)
                except ValueError:
                    continue
                goals.append(Goal(id=f"{actor.id}:goal:{index}", kind=kind, tags={kind.value}))
        if goals:
            return goals
        target_id = actor.component("ai").get("target_id")
        defaults = [Goal(id=f"{actor.id}:survive", kind=GoalKind.SURVIVE, weight=1.0, tags={"survive", "flee"})]
        if target_id:
            defaults.append(
                Goal(
                    id=f"{actor.id}:defeat",
                    kind=GoalKind.DEFEAT,
                    weight=1.0,
                    target_id=str(target_id),
                    tags={"defeat", "attack"},
                )
            )
        return defaults

    def _actor_personality(self, actor: Entity) -> dict[str, float]:
        personality_id = actor.component("ai").get("personality_id")
        personality = self.personalities.get(str(personality_id)) if personality_id else None
        return dict(personality.traits) if personality is not None else {}

    def _scheduled_intent(self, actor: Entity) -> tuple[str | None, str | None]:
        entry = self.world.schedules.current_for(actor.id, self.world.clock.minute_of_day)
        if entry is None:
            return None, None
        return entry.location_id, entry.activity

    def _authoritative_los(self, observer: Entity, target: Entity) -> bool:
        observer_space_id = str(observer.component("spatial").get("space_id", ""))
        target_space_id = str(target.component("spatial").get("space_id", ""))
        if not observer_space_id or observer_space_id != target_space_id:
            return observer.position.area_id == target.position.area_id
        space = self.spatial.spaces.get(observer_space_id)
        if isinstance(space, GridSpace):
            start = space.occupants.get(observer.id)
            end = space.occupants.get(target.id)
            return bool(start is not None and end is not None and space.line_of_sight(start, end))
        if isinstance(space, ContinuousSpace):
            start = space.occupants.get(observer.id)
            end = space.occupants.get(target.id)
            return bool(start is not None and end is not None and space.line_of_sight(start[0], end[0]))
        return True

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
