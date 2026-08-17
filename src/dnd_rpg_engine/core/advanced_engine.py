# src/dnd_rpg_engine/core/advanced_engine.py
from __future__ import annotations

from typing import Any

from dnd_rpg_engine.ai.intelligence import Goal, GoalKind, IntelligentActorController
from dnd_rpg_engine.characters.lifecycle import CharacterBuildRequest, CharacterLifecycle, default_character_lifecycle
from dnd_rpg_engine.core.commands import CustomCommand, GameCommand, MoveCommand, WaitCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import Entity
from dnd_rpg_engine.rules.runtime import RuleCapability
from dnd_rpg_engine.spatial import ContinuousSpace, GraphSpace, GridSpace, SpatialAuthority, Vector3


class AdvancedGameEngine(GameEngine):
    """Integrated advanced engine profile.

    The base ``GameEngine`` stays backward compatible. This subclass opts a
    campaign into runtime-owned advanced rules, character lifecycle,
    authoritative spatial validation, and the intelligent-actor planner while
    preserving the same command/event, scheduler, persistence, and multiplayer
    contracts.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.spatial = SpatialAuthority()
        self.actor_intelligence = IntelligentActorController()
        self.character_lifecycle = default_character_lifecycle()

    def register_spatial_space(self, space: GraphSpace | GridSpace | ContinuousSpace) -> None:
        self.spatial.register(space)

    def configure_character_lifecycle(self, lifecycle: CharacterLifecycle) -> None:
        self.character_lifecycle = lifecycle

    async def create_character(
        self,
        request: CharacterBuildRequest,
        *,
        ready_delay: float = 0.0,
    ) -> Entity:
        entity = self.character_lifecycle.build_character(request)
        await self.add_entity(entity, ready_delay=ready_delay)
        await self._emit(
            "character.created",
            actor_id=entity.id,
            payload={
                "class_id": request.class_id,
                "starting_level": request.starting_level,
                "species_id": request.species_id,
                "background_id": request.background_id,
            },
        )
        return entity

    async def _execute_command(self, command: GameCommand) -> float:
        if isinstance(command, CustomCommand):
            if command.name.startswith("character."):
                return await self._character_command(command)
            if command.name == "spatial_move":
                return await self._spatial_move(command)
        return await super()._execute_command(command)

    async def _character_command(self, command: CustomCommand) -> float:
        actor = self.state.require_entity(command.actor_id)
        payload = command.payload
        name = command.name
        if name == "character.award_xp":
            amount = int(payload.get("amount", 0))
            progress = self.character_lifecycle.award_xp(actor, amount)
            await self._emit(
                "character.xp_awarded",
                actor_id=actor.id,
                payload={
                    "amount": amount,
                    "xp": progress.xp,
                    "total_level": progress.total_level,
                    "level_ready": self.character_lifecycle.eligible_for_level(actor),
                },
            )
            return 0.0
        if name == "character.level_up":
            class_id = str(payload.get("class_id", ""))
            if not class_id:
                raise ValueError("character.level_up requires class_id")
            outcome = self.character_lifecycle.level_up(actor, class_id)
            await self._emit(
                "character.leveled",
                actor_id=actor.id,
                payload=outcome.model_dump(mode="json"),
            )
            return 0.0
        if name == "character.milestone_ready":
            ready = bool(payload.get("ready", True))
            self.character_lifecycle.mark_milestone_ready(actor, ready)
            await self._emit(
                "character.milestone_changed",
                actor_id=actor.id,
                payload={"ready": ready},
            )
            return 0.0
        if name == "character.rest":
            profile_id = str(payload.get("profile_id", "long_rest"))
            outcome = self.character_lifecycle.rest(actor, profile_id)
            self.combat.runtime.reset_turn(actor)
            await self._emit(
                "character.rested",
                actor_id=actor.id,
                payload=outcome.model_dump(mode="json"),
            )
            return outcome.duration_seconds
        if name == "character.equip":
            item_id = str(payload.get("item_id", ""))
            if not item_id:
                raise ValueError("character.equip requires item_id")
            outcome = self.character_lifecycle.equip(actor, item_id)
            await self._emit(
                "character.equipment_changed",
                actor_id=actor.id,
                target_id=item_id,
                payload=outcome.model_dump(mode="json"),
            )
            return 2.0
        if name == "character.unequip":
            item_id = str(payload.get("item_id", ""))
            if not item_id:
                raise ValueError("character.unequip requires item_id")
            outcome = self.character_lifecycle.unequip(actor, item_id)
            await self._emit(
                "character.equipment_changed",
                actor_id=actor.id,
                target_id=item_id,
                payload=outcome.model_dump(mode="json"),
            )
            return 2.0
        if name == "character.spend_resource":
            resource_id = str(payload.get("resource_id", ""))
            amount = int(payload.get("amount", 1))
            resource = self.character_lifecycle.spend_resource(actor, resource_id, amount)
            await self._emit(
                "character.resource_changed",
                actor_id=actor.id,
                target_id=resource_id,
                payload={"resource": resource.model_dump(mode="json"), "delta": -amount},
            )
            return 0.0
        if name == "character.restore_resource":
            resource_id = str(payload.get("resource_id", ""))
            amount = int(payload.get("amount", 1))
            before = self.character_lifecycle.resources(actor)[resource_id].current
            resource = self.character_lifecycle.restore_resource(actor, resource_id, amount)
            await self._emit(
                "character.resource_changed",
                actor_id=actor.id,
                target_id=resource_id,
                payload={
                    "resource": resource.model_dump(mode="json"),
                    "delta": resource.current - before,
                },
            )
            return 0.0
        raise ValueError(f"unknown character lifecycle command: {name}")

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

    async def _handle_zero_hp(
        self,
        entity: Entity,
        *,
        source_id: str | None = None,
        critical: bool = False,
        damage: int = 0,
        excess_damage: int = 0,
        was_at_zero: bool = False,
    ) -> None:
        runtime = self.combat.runtime
        if not runtime.has_capability(RuleCapability.DEATH_SAVES) or not hasattr(runtime, "handle_zero_hp"):
            await super()._handle_zero_hp(
                entity,
                source_id=source_id,
                critical=critical,
                damage=damage,
                excess_damage=excess_damage,
                was_at_zero=was_at_zero,
            )
            return

        transition = runtime.handle_zero_hp(
            entity,
            critical=critical,
            excess_damage=excess_damage,
            was_at_zero=was_at_zero,
        )
        if transition.state == "death_saves_started":
            if self.conditions.get("unconscious") is not None and not any(
                condition.condition_id == "unconscious" for condition in self._active_conditions(entity)
            ):
                await self._apply_condition(entity.id, "unconscious", source_id=source_id)
            self.scheduler.cancel_matching(kind="actor_ready", actor_id=entity.id)
            self._schedule_actor_ready(entity.id, delay=self.rules.round_seconds)
            await self._emit("combat.death_saves_started", actor_id=source_id, target_id=entity.id)
            return

        if transition.failures_added:
            await self._emit(
                "combat.death_save_damage_failure",
                actor_id=source_id,
                target_id=entity.id,
                payload={
                    "failures_added": transition.failures_added,
                    "failures": transition.failures,
                    "damage": damage,
                },
            )
        if transition.state == "defeated":
            payload = {"reason": transition.reason} if transition.reason else {}
            await self._emit("combat.entity_defeated", actor_id=source_id, target_id=entity.id, payload=payload)
            return
        if transition.state == "death_save_failure" and not self._has_readiness_task(entity.id):
            self._schedule_actor_ready(entity.id, delay=self.rules.round_seconds)

    async def _resolve_death_save(self, entity: Entity) -> None:
        runtime = self.combat.runtime
        if not runtime.has_capability(RuleCapability.DEATH_SAVES) or not hasattr(runtime, "resolve_death_save"):
            await super()._resolve_death_save(entity)
            return

        outcome = runtime.resolve_death_save(entity)
        if outcome.roll:
            payload: dict[str, object] = {
                "roll": outcome.roll,
                "successes": outcome.successes,
                "failures": outcome.failures,
            }
            if outcome.recovered_hp:
                payload["recovered_hp"] = outcome.recovered_hp
            await self._emit("combat.death_save", actor_id=entity.id, payload=payload)

        if outcome.state == "recovered":
            await self._recover_from_zero_hp(entity)
            self._schedule_actor_ready(entity.id, delay=self.rules.round_seconds)
            return
        if outcome.state == "stable":
            await self._emit("combat.stabilized", target_id=entity.id)
            return
        if outcome.state == "defeated":
            await self._emit("combat.entity_defeated", target_id=entity.id)
            return
        self._schedule_actor_ready(entity.id, delay=self.rules.round_seconds)

    async def _recover_from_zero_hp(self, entity: Entity) -> None:
        runtime = self.combat.runtime
        if runtime.has_capability(RuleCapability.DEATH_SAVES) and hasattr(runtime, "recover_from_zero_hp"):
            runtime.recover_from_zero_hp(entity)
            active = [condition for condition in self._active_conditions(entity) if condition.condition_id != "unconscious"]
            self._set_conditions(entity, active)
            return
        await super()._recover_from_zero_hp(entity)

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
