# src/dnd_rpg_engine/core/engine.py
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from dnd_rpg_engine.adventure.dialogue import DialogueRegistry
from dnd_rpg_engine.adventure.exploration import ExplorationState, ExplorationSystem
from dnd_rpg_engine.adventure.maps import MapRegistry
from dnd_rpg_engine.adventure.npcs import NPCRegistry
from dnd_rpg_engine.adventure.quests import QuestDefinition, QuestJournal, QuestProgress
from dnd_rpg_engine.adventure.shops import ShopRegistry
from dnd_rpg_engine.ai.gm import GameMaster
from dnd_rpg_engine.ai.personalities import PersonalityRegistry
from dnd_rpg_engine.ai.encounters import EncounterGenerator
from dnd_rpg_engine.ai.quests import QuestGenerator
from dnd_rpg_engine.core.checks import CheckService
from dnd_rpg_engine.core.commands import (
    AttackCommand,
    CastCommand,
    CustomCommand,
    DialogueCommand,
    GameCommand,
    InteractCommand,
    MoveCommand,
    ShopCommand,
    UseItemCommand,
    WaitCommand,
)
from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.events import EventBus, GameEvent
from dnd_rpg_engine.core.models import (
    CampaignState,
    ControllerKind,
    Entity,
    EntityKind,
    GameConfig,
    TimeMode,
)
from dnd_rpg_engine.core.persistence import SQLiteStore
from dnd_rpg_engine.core.scheduler import ScheduledTask, TimelineScheduler
from dnd_rpg_engine.core.rules import RuleSet
from dnd_rpg_engine.living.world import LivingWorld
from dnd_rpg_engine.living.economy import MarketState
from dnd_rpg_engine.living.weather import Weather
from dnd_rpg_engine.adventure.shops import Shop
from dnd_rpg_engine.tactical.actions import ActionRegistry, default_actions
from dnd_rpg_engine.tactical.combat import CombatSystem, CombatantState, Encounter
from dnd_rpg_engine.tactical.conditions import ActiveCondition, ConditionRegistry, default_conditions
from dnd_rpg_engine.tactical.items import Inventory, ItemRegistry, default_items
from dnd_rpg_engine.tactical.spells import SpellRegistry, default_spells


@dataclass(slots=True)
class EngineResult:
    events: list[GameEvent]
    version: int
    simulation_time: float
    narration: str | None = None


class GameEngine:
    """Authoritative deterministic RPG simulation.

    Rendering, network transports, UI, and narration all consume commands/events;
    none of them mutate simulation state directly.
    """

    def __init__(
        self,
        state: CampaignState,
        config: GameConfig | None = None,
        *,
        store: SQLiteStore | None = None,
        game_master: GameMaster | None = None,
    ) -> None:
        self.state = state
        persisted_config = state.metadata.get("engine_config")
        self.config = config or (GameConfig.model_validate(persisted_config) if persisted_config else GameConfig(seed=state.seed))
        self.store = store
        runtime = state.metadata.get("engine_runtime", {})
        self.version = int(runtime.get("version", 0))
        self.sequence = int(runtime.get("sequence", 0))
        self.dice = DeterministicDice(state.seed, runtime.get("dice_counters"))
        self.scheduler = TimelineScheduler(state.simulation_time)
        self.scheduler.restore(runtime.get("scheduler", []))
        self.events = EventBus()
        self.checks = CheckService(self.dice)
        self.actions: ActionRegistry = default_actions()
        self.conditions: ConditionRegistry = default_conditions()
        self.items: ItemRegistry = default_items()
        self.spells: SpellRegistry = default_spells()
        self.rules = RuleSet.model_validate(runtime.get("rules") or {})
        self.rule_documents: dict[str, object] = {}
        self.combat = CombatSystem(self.dice, self.conditions, self.rules)
        self.maps = MapRegistry()
        self.exploration = ExplorationSystem(self.dice)
        self.dialogues = DialogueRegistry()
        self.npcs = NPCRegistry()
        self.shops = ShopRegistry()
        self.personalities = PersonalityRegistry()
        self.encounter_generator = EncounterGenerator(self.dice)
        self.quest_generator = QuestGenerator(self.dice)
        self.quests: dict[str, QuestDefinition] = {}
        self.quest_journals: dict[str, QuestJournal] = {}
        self.world = LivingWorld(self.dice, state.world_minutes)
        self.gm = game_master or GameMaster()
        self._lock = asyncio.Lock()
        self._ready_humans: set[str] = set(runtime.get("ready_humans", []))
        self._decision_pause_remaining: float | None = runtime.get("decision_pause_remaining")
        self._recent_events: list[GameEvent] = []
        self._registered_ai: set[str] = set(runtime.get("registered_ai", []))
        self._initialize_economy()
        self._restore_runtime_mutables(runtime)

    @classmethod
    async def create(
        cls,
        name: str = "New Campaign",
        *,
        config: GameConfig | None = None,
        store: SQLiteStore | None = None,
        seed: int | None = None,
    ) -> GameEngine:
        cfg = config or GameConfig()
        actual_seed = cfg.seed if seed is None else seed
        state = CampaignState(name=name, seed=actual_seed)
        engine = cls(state, cfg, store=store)
        if store is not None:
            await store.initialize()
            await engine._persist_state()
        return engine

    @classmethod
    async def load(cls, campaign_id: str, *, store: SQLiteStore, config: GameConfig | None = None) -> GameEngine:
        await store.initialize()
        loaded = await store.load_campaign(campaign_id)
        if loaded is None:
            raise KeyError(f"campaign not found: {campaign_id}")
        state, version = loaded
        engine = cls(state, config, store=store)
        installed = state.metadata.get("installed_content_packs", {})
        if installed:
            from dnd_rpg_engine.creator.content import ContentPack
            from dnd_rpg_engine.creator.loader import install_content_pack

            for raw_pack in installed.values():
                install_content_pack(engine, ContentPack.model_validate(raw_pack))
        engine._restore_runtime_mutables(state.metadata.get("engine_runtime", {}))
        engine.version = max(engine.version, version)
        return engine

    async def save(self) -> None:
        async with self._lock:
            await self._persist_state()

    async def update_timing(
        self,
        *,
        time_mode: TimeMode | None = None,
        player_decision_timeout_seconds: float | None | object = ...,
        pause_when_player_ready: bool | None = None,
        time_scale: float | None = None,
    ) -> GameConfig:
        async with self._lock:
            updates: dict[str, object] = {}
            if time_mode is not None:
                updates["time_mode"] = time_mode
            if player_decision_timeout_seconds is not ...:
                updates["player_decision_timeout_seconds"] = player_decision_timeout_seconds
            if pause_when_player_ready is not None:
                updates["pause_when_player_ready"] = pause_when_player_ready
            if time_scale is not None:
                updates["time_scale"] = time_scale
            self.config = self.config.model_copy(update=updates)
            self.config = GameConfig.model_validate(self.config.model_dump())
            await self._emit("timeline.config_updated", payload=self.config.model_dump(mode="json"))
            self.version += 1
            await self._persist_state()
            return self.config

    async def add_entity(self, entity: Entity, *, ready_delay: float = 0.0) -> GameEvent:
        async with self._lock:
            self.state.add_entity(entity)
            event = await self._emit(
                "entity.created",
                actor_id=entity.id,
                payload={"name": entity.name, "kind": entity.kind.value},
            )
            if entity.controller is ControllerKind.AI:
                self._schedule_actor_ready(entity.id, delay=ready_delay)
                self._registered_ai.add(entity.id)
            elif entity.controller is ControllerKind.HUMAN:
                self._schedule_actor_ready(entity.id, delay=ready_delay)
            self.version += 1
            await self._persist_state()
            return event

    async def start_encounter(self, participant_ids: list[str]) -> dict[str, object]:
        """Schedule deterministic initiative on the unified timeline."""
        async with self._lock:
            if len(participant_ids) < 2:
                raise ValueError("an encounter requires at least two participants")
            scored: list[tuple[int, str]] = []
            for entity_id in participant_ids:
                entity = self.state.require_entity(entity_id)
                if not entity.alive:
                    raise ValueError(f"inactive participant: {entity_id}")
                raw = self.dice.d20(stream=f"initiative:{entity_id}")
                scored.append((raw + entity.stats.modifier("dexterity"), entity_id))
                self.scheduler.cancel_matching(kind="actor_ready", actor_id=entity_id)
                self._ready_humans.discard(entity_id)
            scored.sort(key=lambda item: (-item[0], item[1]))
            encounter_id = str(uuid4())
            participants = {entity_id: CombatantState(entity_id=entity_id) for _, entity_id in scored}
            self.combat.encounters[encounter_id] = Encounter(
                id=encounter_id,
                participants=participants,
                started_at=self.scheduler.now,
                round_length=self.rules.round_seconds,
            )
            for index, (_, entity_id) in enumerate(scored):
                delay = index * 0.001
                participants[entity_id].next_ready_at = self.scheduler.now + delay
                self._schedule_actor_ready(entity_id, delay=delay)
            await self._emit(
                "combat.encounter_started",
                payload={
                    "encounter_id": encounter_id,
                    "initiative": [{"entity_id": entity_id, "score": score} for score, entity_id in scored],
                },
            )
            if self.config.time_mode is TimeMode.TURN_BASED:
                await self._advance_turn_based_until_human()
            self.version += 1
            await self._persist_state()
            return {
                "encounter_id": encounter_id,
                "initiative": [{"entity_id": entity_id, "score": score} for score, entity_id in scored],
            }

    async def end_encounter(self, encounter_id: str) -> None:
        async with self._lock:
            encounter = self.combat.encounters.get(encounter_id)
            if encounter is None:
                raise KeyError(encounter_id)
            encounter.active = False
            await self._emit("combat.encounter_ended", payload={"encounter_id": encounter_id})
            self.version += 1
            await self._persist_state()

    def activate_rules(self, rules: RuleSet) -> None:
        self.rules = rules
        self.combat.rules = rules

    def register_quest(self, quest: QuestDefinition) -> None:
        self.quests[quest.id] = quest

    def start_quest(self, actor_id: str, quest_id: str) -> None:
        quest = self.quests[quest_id]
        self.quest_journals.setdefault(actor_id, QuestJournal()).start(quest)

    async def dispatch(self, command: GameCommand, *, narrate: bool = False) -> EngineResult:
        async with self._lock:
            if command.expected_version is not None and command.expected_version != self.version:
                raise RuntimeError(f"state version mismatch: expected {command.expected_version}, current {self.version}")
            barrier_active = (
                self._decision_pause_remaining is not None
                or (self.config.time_mode is TimeMode.TURN_BASED and bool(self._ready_humans))
            )
            if not barrier_active:
                await self._process_tasks(self.scheduler.pop_due())
            actor = self.state.require_entity(command.actor_id)
            if not actor.alive:
                raise ValueError("actor is not active")
            if actor.controller is ControllerKind.HUMAN and command.actor_id not in self._ready_humans:
                # Before a formal encounter, a human may still act freely. Once readiness
                # tracking has started, an actor must wait until its timeline slot.
                if self._has_readiness_task(command.actor_id):
                    raise ValueError("actor is not ready")

            start_index = len(self._recent_events)
            action_time = await self._execute_command(command)
            if actor.controller is ControllerKind.HUMAN:
                self._ready_humans.discard(actor.id)
                if not self._ready_humans:
                    self._decision_pause_remaining = None
            self._schedule_actor_ready(actor.id, delay=action_time)
            self.version += 1

            if self.config.time_mode is TimeMode.TURN_BASED:
                await self._advance_turn_based_until_human()

            await self._persist_state()
            produced = self._recent_events[start_index:]
            narration = await self.gm.narrate(self.state, produced) if narrate else None
            return EngineResult(produced, self.version, self.state.simulation_time, narration)

    async def tick(self, real_delta_seconds: float, *, narrate: bool = False) -> EngineResult:
        if real_delta_seconds < 0:
            raise ValueError("delta cannot be negative")
        async with self._lock:
            start_index = len(self._recent_events)
            if self.config.time_mode is TimeMode.TURN_BASED:
                return EngineResult([], self.version, self.state.simulation_time, None)

            # Make zero-time readiness visible before consuming wall-clock time,
            # but never drain deferred tasks while a tactical pause is active.
            if self._decision_pause_remaining is None:
                await self._process_tasks(self.scheduler.pop_due())
            remaining = real_delta_seconds
            if self._decision_pause_remaining is not None:
                consumed = min(remaining, self._decision_pause_remaining)
                self._decision_pause_remaining -= consumed
                remaining -= consumed
                if self._decision_pause_remaining <= 0:
                    self._decision_pause_remaining = None
                    await self._emit("timeline.decision_window_expired", payload={"ready_actors": sorted(self._ready_humans)})
                    await self._emit("timeline.resumed")

            if remaining > 0:
                sim_delta = remaining * self.config.time_scale
                await self._advance_simulation(sim_delta)
                self.version += 1
                await self._persist_state()

            produced = self._recent_events[start_index:]
            narration = await self.gm.narrate(self.state, produced) if narrate and produced else None
            return EngineResult(produced, self.version, self.state.simulation_time, narration)

    async def run_realtime(self, stop_event: asyncio.Event) -> None:
        """Drive the engine without blocking the event loop."""
        step = 1.0 / self.config.ticks_per_second
        loop = asyncio.get_running_loop()
        last = loop.time()
        while not stop_event.is_set():
            await asyncio.sleep(step)
            now = loop.time()
            delta = now - last
            last = now
            await self.tick(delta)

    async def _execute_command(self, command: GameCommand) -> float:
        if isinstance(command, AttackCommand):
            return await self._attack(command.actor_id, command.target_id, command.action_id)
        if isinstance(command, MoveCommand):
            return await self._move(command)
        if isinstance(command, CastCommand):
            return await self._begin_cast(command)
        if isinstance(command, UseItemCommand):
            return await self._use_item(command)
        if isinstance(command, WaitCommand):
            duration = command.duration or self.config.default_action_time_seconds
            await self._emit("actor.waited", actor_id=command.actor_id, payload={"duration": duration})
            return duration
        if isinstance(command, InteractCommand):
            await self._emit(
                "entity.interacted",
                actor_id=command.actor_id,
                target_id=command.target_id,
                payload={"interaction": command.interaction},
            )
            return self.config.default_action_time_seconds / 2
        if isinstance(command, DialogueCommand):
            return await self._dialogue(command)
        if isinstance(command, ShopCommand):
            return await self._shop(command)
        if isinstance(command, CustomCommand):
            await self._emit(
                f"custom.{command.name}", actor_id=command.actor_id, payload=command.payload
            )
            return self.config.default_action_time_seconds
        raise TypeError(f"unsupported command: {type(command).__name__}")

    async def _attack(self, actor_id: str, target_id: str, action_id: str) -> float:
        actor = self.state.require_entity(actor_id)
        target = self.state.require_entity(target_id)
        if not target.alive:
            raise ValueError("target is not active")
        action = self.actions.require(action_id)
        distance = actor.position.distance_to(target.position)
        if distance > action.range:
            raise ValueError(f"target is out of action range ({distance:.2f} > {action.range:.2f})")
        active = self._active_conditions(actor)
        if any(self.conditions.require(condition.condition_id).blocks_actions for condition in active):
            raise ValueError("actor is prevented from acting by a condition")
        resolution = self.combat.resolve_attack(actor, target, action, active_conditions=active)
        applied = target.resources.apply_damage(resolution.damage) if resolution.hit else 0
        await self._emit(
            "combat.attack_resolved",
            actor_id=actor_id,
            target_id=target_id,
            payload={
                "action_id": action_id,
                "roll": resolution.roll,
                "modifier": resolution.modifier,
                "total": resolution.total,
                "defense": resolution.defense,
                "hit": resolution.hit,
                "critical": resolution.critical,
                "damage": applied,
                "remaining_hp": target.resources.hp,
            },
        )
        if target.resources.hp == 0 and target.alive:
            target.alive = False
            await self._emit("combat.entity_defeated", actor_id=actor_id, target_id=target_id)
        return action.time_cost

    async def _move(self, command: MoveCommand) -> float:
        actor = self.state.require_entity(command.actor_id)
        old = actor.position.model_copy(deep=True)
        distance = math.dist((old.x, old.y, old.z), (command.x, command.y, command.z))
        speed = float(actor.component("movement").get("units_per_second", 1.5))
        if speed <= 0:
            raise ValueError("actor cannot move")
        actor.position.x = command.x
        actor.position.y = command.y
        actor.position.z = command.z
        if command.map_id:
            actor.position.area_id = command.map_id
        await self._emit(
            "entity.moved",
            actor_id=actor.id,
            target_id=actor.position.area_id,
            payload={
                "from": old.model_dump(),
                "to": actor.position.model_dump(),
                "distance": distance,
            },
        )
        self.exploration.visit(actor.id, actor.position.area_id)
        await self._emit("location.visited", actor_id=actor.id, target_id=actor.position.area_id)
        return max(0.25, distance / speed)

    async def _begin_cast(self, command: CastCommand) -> float:
        caster = self.state.require_entity(command.actor_id)
        spell = self.spells.require(command.spell_id)
        if caster.resources.energy < spell.energy_cost:
            raise ValueError("insufficient energy")
        target_id = command.target_id or caster.id
        target = self.state.require_entity(target_id)
        if caster.position.distance_to(target.position) > spell.range:
            raise ValueError("spell target is out of range")
        caster.resources.energy -= spell.energy_cost
        await self._emit(
            "spell.cast_started",
            actor_id=caster.id,
            target_id=target_id,
            payload={"spell_id": spell.id, "cast_time": spell.cast_time},
        )
        self.scheduler.schedule(
            "spell_resolve",
            delay=spell.cast_time,
            actor_id=caster.id,
            payload={"spell_id": spell.id, "target_id": target_id},
            priority=40,
        )
        return spell.cast_time

    async def _resolve_spell(self, task: ScheduledTask) -> None:
        caster = self.state.entities.get(task.actor_id or "")
        target = self.state.entities.get(str(task.payload.get("target_id", "")))
        if caster is None or target is None or not caster.alive:
            return
        spell = self.spells.require(str(task.payload["spell_id"]))
        payload: dict[str, object] = {"spell_id": spell.id}
        if spell.damage and target.alive:
            amount = max(0, self.dice.roll(spell.damage, stream=f"spell:damage:{caster.id}:{spell.id}").total)
            payload["damage"] = target.resources.apply_damage(amount)
            payload["remaining_hp"] = target.resources.hp
            if target.resources.hp == 0 and target.alive:
                target.alive = False
                await self._emit("combat.entity_defeated", actor_id=caster.id, target_id=target.id)
        if spell.heal:
            amount = max(0, self.dice.roll(spell.heal, stream=f"spell:heal:{caster.id}:{spell.id}").total)
            payload["healed"] = target.resources.heal(amount)
        if spell.applies_condition:
            await self._apply_condition(
                target.id,
                spell.applies_condition,
                source_id=caster.id,
                duration=spell.duration,
            )
        await self._emit("spell.resolved", actor_id=caster.id, target_id=target.id, payload=payload)

    async def _use_item(self, command: UseItemCommand) -> float:
        actor = self.state.require_entity(command.actor_id)
        target = self.state.require_entity(command.target_id or command.actor_id)
        item = self.items.require(command.item_id)
        inventory = self._inventory(actor)
        inventory.remove(item.id, 1)
        self._set_inventory(actor, inventory)
        payload: dict[str, object] = {"item_id": item.id}
        if item.heal:
            amount = self.dice.roll(item.heal, stream=f"item:heal:{actor.id}:{item.id}").total
            payload["healed"] = target.resources.heal(amount)
        if item.energy_restore:
            before = target.resources.energy
            target.resources.energy = min(target.resources.max_energy, target.resources.energy + item.energy_restore)
            payload["energy_restored"] = target.resources.energy - before
        if item.applies_condition:
            await self._apply_condition(target.id, item.applies_condition, source_id=actor.id)
        await self._emit("inventory.item_used", actor_id=actor.id, target_id=target.id, payload=payload)
        return item.use_time

    async def _dialogue(self, command: DialogueCommand) -> float:
        graph = self.dialogues.require(command.dialogue_id)
        node_id = str(self.state.flags.get(f"dialogue:{command.actor_id}:{graph.id}", graph.start_node))
        option = graph.choose(node_id, command.option_id, self.state.flags)
        if option.next_node:
            self.state.flags[f"dialogue:{command.actor_id}:{graph.id}"] = option.next_node
        if option.quest_id and option.quest_id in self.quests:
            self.quest_journals.setdefault(command.actor_id, QuestJournal()).start(self.quests[option.quest_id])
            await self._emit("quest.started", actor_id=command.actor_id, payload={"quest_id": option.quest_id})
        await self._emit(
            "dialogue.option_selected",
            actor_id=command.actor_id,
            payload={"dialogue_id": graph.id, "node_id": node_id, "option_id": option.id, "next_node": option.next_node},
        )
        return self.config.default_action_time_seconds / 2

    async def _shop(self, command: ShopCommand) -> float:
        actor = self.state.require_entity(command.actor_id)
        shop = self.shops.require(command.shop_id)
        item = self.items.require(command.item_id)
        inventory = self._inventory(actor)
        if command.operation == "buy":
            price = self.world.economy.price(item.id, multiplier=shop.buy_multiplier) * command.quantity
            if inventory.currency < price:
                raise ValueError("insufficient currency")
            shop.take(item.id, command.quantity)
            inventory.currency -= price
            inventory.add(item.id, command.quantity)
            self.world.economy.transact(item.id, command.quantity, buying_from_market=True)
        else:
            inventory.remove(item.id, command.quantity)
            price = self.world.economy.price(item.id, multiplier=shop.sell_multiplier) * command.quantity
            inventory.currency += price
            shop.add(item.id, command.quantity)
            self.world.economy.transact(item.id, command.quantity, buying_from_market=False)
        self._set_inventory(actor, inventory)
        await self._emit(
            "shop.transaction",
            actor_id=actor.id,
            target_id=shop.id,
            payload={"operation": command.operation, "item_id": item.id, "quantity": command.quantity, "total": price},
        )
        return self.config.default_action_time_seconds / 2

    async def _advance_simulation(self, delta: float) -> None:
        if delta < 0:
            raise ValueError("simulation delta cannot be negative")
        due = self.scheduler.pop_due() if delta == 0 else self.scheduler.advance(delta)
        self.state.simulation_time = self.scheduler.now
        world_minutes = delta * self.config.world_minutes_per_sim_second
        before_weather = self.world.weather.current
        self.state.world_minutes += world_minutes
        world_advance = self.world.advance(world_minutes, self.state)
        if world_advance.weather_after != before_weather:
            await self._emit("weather.changed", payload={"weather": world_advance.weather_after.value})
        for rule in world_advance.dynamic_events:
            await self._emit(rule.event_type, payload=rule.payload)
        await self._process_tasks(due)

    async def _advance_turn_based_until_human(self) -> None:
        safety = 0
        while not self._ready_humans and self.scheduler.peek() is not None:
            safety += 1
            if safety > 10_000:
                raise RuntimeError("turn scheduler safety limit exceeded")
            previous = self.scheduler.now
            due = self.scheduler.advance_to_next()
            delta = self.scheduler.now - previous
            self.state.simulation_time = self.scheduler.now
            if delta > 0:
                world_minutes = delta * self.config.world_minutes_per_sim_second
                self.state.world_minutes += world_minutes
                world_advance = self.world.advance(world_minutes, self.state)
                for rule in world_advance.dynamic_events:
                    await self._emit(rule.event_type, payload=rule.payload)
            await self._process_tasks(due)

    async def _process_tasks(self, tasks: Iterable[ScheduledTask]) -> None:
        queue = list(tasks)
        processed = 0
        while queue:
            task = queue.pop(0)
            processed += 1
            if processed > 20_000:
                raise RuntimeError("scheduler task safety limit exceeded")
            if task.kind == "actor_ready":
                await self._actor_ready(task)
            elif task.kind == "spell_resolve":
                await self._resolve_spell(task)
            elif task.kind == "condition_expire":
                await self._expire_condition(task)
            elif task.kind == "condition_tick":
                await self._condition_tick(task)
            elif task.kind == "dynamic_event":
                await self._emit(str(task.payload.get("event_type", "world.dynamic")), actor_id=task.actor_id, payload=task.payload)
            elif task.kind == "player_timeout":
                await self._emit("timeline.player_timeout", actor_id=task.actor_id)
            # Strict turns and configured tactical decision windows are true
            # scheduling barriers: work later in the same timestamp is deferred.
            if self._ready_humans and (
                self.config.time_mode is TimeMode.TURN_BASED
                or self._decision_pause_remaining is not None
            ):
                self.scheduler.requeue_many(queue)
                return
            # Tasks scheduled for exactly 'now' by handlers are processed in the same deterministic cycle.
            queue.extend(self.scheduler.pop_due())

    async def _actor_ready(self, task: ScheduledTask) -> None:
        actor = self.state.entities.get(task.actor_id or "")
        if actor is None or not actor.alive:
            return
        if actor.controller is ControllerKind.AI:
            await self._ai_take_action(actor)
            return
        if actor.controller is ControllerKind.HUMAN:
            self._ready_humans.add(actor.id)
            await self._emit("timeline.actor_ready", actor_id=actor.id)
            if self.config.time_mode in {TimeMode.TIMED_TURN_BASED, TimeMode.REAL_TIME_WITH_PAUSE, TimeMode.HYBRID} and self.config.pause_when_player_ready:
                timeout = self.config.player_decision_timeout_seconds
                if timeout is not None:
                    if self._decision_pause_remaining is None:
                        self._decision_pause_remaining = timeout
                        await self._emit("timeline.paused_for_decision", actor_id=actor.id, payload={"timeout": timeout})
            return
        await self._emit("timeline.actor_ready", actor_id=actor.id)

    async def _ai_take_action(self, actor: Entity) -> None:
        target = self._select_ai_target(actor)
        if target is None:
            await self._emit("ai.idle", actor_id=actor.id)
            self._schedule_actor_ready(actor.id, delay=self.config.default_action_time_seconds)
            return
        action_id = str(actor.component("ai").get("action_id", "basic_attack"))
        action = self.actions.require(action_id)
        distance = actor.position.distance_to(target.position)
        if distance <= action.range:
            duration = await self._attack(actor.id, target.id, action_id)
            self._schedule_actor_ready(actor.id, delay=duration)
            return
        speed = float(actor.component("movement").get("units_per_second", 1.5))
        duration = max(1.0, min(self.config.default_action_time_seconds, distance / max(speed, 0.1)))
        travel = speed * duration
        ratio = min(1.0, travel / max(distance, 0.0001))
        actor.position.x += (target.position.x - actor.position.x) * ratio
        actor.position.y += (target.position.y - actor.position.y) * ratio
        actor.position.z += (target.position.z - actor.position.z) * ratio
        await self._emit("ai.moved_toward_target", actor_id=actor.id, target_id=target.id, payload={"duration": duration})
        self._schedule_actor_ready(actor.id, delay=duration)

    def _select_ai_target(self, actor: Entity) -> Entity | None:
        explicit = actor.component("ai").get("target_id")
        if explicit:
            target = self.state.entities.get(str(explicit))
            if target and target.alive:
                return target
        candidates = [
            entity
            for entity in self.state.entities.values()
            if entity.alive and entity.id != actor.id and entity.kind is EntityKind.PLAYER
        ]
        if not candidates:
            candidates = [
                entity
                for entity in self.state.entities.values()
                if entity.alive and entity.id != actor.id and entity.controller is ControllerKind.HUMAN
            ]
        return min(candidates, key=lambda e: actor.position.distance_to(e.position), default=None)

    async def _apply_condition(
        self,
        entity_id: str,
        condition_id: str,
        *,
        source_id: str | None = None,
        duration: float | None = None,
    ) -> None:
        entity = self.state.require_entity(entity_id)
        definition = self.conditions.require(condition_id)
        active = ActiveCondition(
            condition_id=condition_id,
            source_id=source_id,
            expires_at=self.scheduler.now + duration if duration else None,
        )
        conditions = self._active_conditions(entity)
        conditions.append(active)
        self._set_conditions(entity, conditions)
        await self._emit("condition.applied", actor_id=source_id, target_id=entity_id, payload={"condition_id": condition_id, "duration": duration})
        if duration:
            self.scheduler.schedule(
                "condition_expire",
                delay=duration,
                actor_id=entity_id,
                payload={"condition_id": condition_id},
                priority=30,
            )
        if definition.periodic_damage and definition.periodic_interval:
            self.scheduler.schedule(
                "condition_tick",
                delay=definition.periodic_interval,
                actor_id=entity_id,
                payload={"condition_id": condition_id, "source_id": source_id},
                priority=20,
            )

    async def _expire_condition(self, task: ScheduledTask) -> None:
        entity = self.state.entities.get(task.actor_id or "")
        if entity is None:
            return
        condition_id = str(task.payload.get("condition_id", ""))
        conditions = [condition for condition in self._active_conditions(entity) if condition.condition_id != condition_id]
        self._set_conditions(entity, conditions)
        await self._emit("condition.expired", target_id=entity.id, payload={"condition_id": condition_id})

    async def _condition_tick(self, task: ScheduledTask) -> None:
        entity = self.state.entities.get(task.actor_id or "")
        if entity is None or not entity.alive:
            return
        condition_id = str(task.payload.get("condition_id", ""))
        active = next((c for c in self._active_conditions(entity) if c.condition_id == condition_id), None)
        if active is None:
            return
        definition = self.conditions.require(condition_id)
        if definition.periodic_damage:
            amount = self.dice.roll(definition.periodic_damage, stream=f"condition:{entity.id}:{condition_id}").total
            applied = entity.resources.apply_damage(amount)
            await self._emit("condition.tick", actor_id=active.source_id, target_id=entity.id, payload={"condition_id": condition_id, "damage": applied})
            if entity.resources.hp == 0:
                entity.alive = False
                await self._emit("combat.entity_defeated", actor_id=active.source_id, target_id=entity.id)
                return
        if definition.periodic_interval and (active.expires_at is None or self.scheduler.now + definition.periodic_interval < active.expires_at):
            self.scheduler.schedule(
                "condition_tick",
                delay=definition.periodic_interval,
                actor_id=entity.id,
                payload=task.payload,
                priority=20,
            )

    def _schedule_actor_ready(self, actor_id: str, *, delay: float) -> None:
        self.scheduler.schedule("actor_ready", delay=max(0.0, delay), actor_id=actor_id, priority=100)

    def _has_readiness_task(self, actor_id: str) -> bool:
        return any(row["kind"] == "actor_ready" and row["actor_id"] == actor_id for row in self.scheduler.snapshot())

    def _active_conditions(self, entity: Entity) -> list[ActiveCondition]:
        raw = entity.component("conditions").get("active", [])
        return [ActiveCondition.model_validate(item) for item in raw]

    @staticmethod
    def _set_conditions(entity: Entity, conditions: list[ActiveCondition]) -> None:
        entity.component("conditions")["active"] = [condition.model_dump(mode="json") for condition in conditions]

    @staticmethod
    def _inventory(entity: Entity) -> Inventory:
        return Inventory.model_validate(entity.component("inventory") or {})

    @staticmethod
    def _set_inventory(entity: Entity, inventory: Inventory) -> None:
        entity.components["inventory"] = inventory.model_dump(mode="json")

    def _initialize_economy(self) -> None:
        for item in self.items.all():
            if item.id not in self.world.economy.markets:
                self.world.economy.register_item(item.id, item.value)

    async def _emit(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        payload: dict | None = None,
    ) -> GameEvent:
        self.sequence += 1
        event = GameEvent(
            type=event_type,
            campaign_id=self.state.id,
            sequence=self.sequence,
            simulation_time=self.scheduler.now,
            actor_id=actor_id,
            target_id=target_id,
            payload=payload or {},
        )
        self._recent_events.append(event)
        if len(self._recent_events) > 10_000:
            del self._recent_events[:2_000]
        await self.events.publish(event)
        if self.store is not None:
            await self.store.append_event(event)
        await self._apply_event_to_quests(event)
        return event

    async def _apply_event_to_quests(self, event: GameEvent) -> None:
        if event.type.startswith("quest."):
            return
        for actor_id, journal in self.quest_journals.items():
            for quest_id in journal.apply_event(event):
                progress = journal.completed[quest_id]
                actor = self.state.entities.get(actor_id)
                if actor:
                    inventory = self._inventory(actor)
                    inventory.currency += progress.quest.reward_currency
                    self._set_inventory(actor, inventory)
                self.state.flags.update(progress.quest.set_flags)
                await self._emit("quest.completed", actor_id=actor_id, payload={"quest_id": quest_id, "reward_currency": progress.quest.reward_currency})

    def _restore_runtime_mutables(self, runtime: dict) -> None:
        living = runtime.get("living", {})
        weather = living.get("weather")
        if weather:
            self.world.weather.current = Weather(weather.get("current", Weather.CLEAR.value))
            self.world.weather.last_change_world_minute = float(weather.get("last_change_world_minute", 0.0))
        markets = living.get("economy", {})
        for item_id, data in markets.items():
            self.world.economy.markets[item_id] = MarketState(
                base_value=int(data["base_value"]),
                supply=float(data.get("supply", 1.0)),
                demand=float(data.get("demand", 1.0)),
            )
        factions = living.get("factions", {})
        self.world.factions.relations = {
            (str(a), str(b)): int(value) for a, b, value in factions.get("relations", [])
        }
        self.world.factions.reputation = {
            (str(a), str(b)): int(value) for a, b, value in factions.get("reputation", [])
        }
        self.world.schedules.assignments = {str(k): str(v) for k, v in living.get("schedule_assignments", {}).items()}
        self.world.dynamic_events.fired = set(living.get("dynamic_events_fired", []))
        for shop_id, raw_shop in living.get("shops", {}).items():
            self.shops.register(Shop.model_validate(raw_shop))
        self.exploration.by_actor = {
            actor_id: ExplorationState.model_validate(raw)
            for actor_id, raw in runtime.get("exploration", {}).items()
        }
        journals: dict[str, QuestJournal] = {}
        for actor_id, raw in runtime.get("quest_journals", {}).items():
            journal = QuestJournal()
            journal.active = {key: QuestProgress.model_validate(value) for key, value in raw.get("active", {}).items()}
            journal.completed = {key: QuestProgress.model_validate(value) for key, value in raw.get("completed", {}).items()}
            journals[actor_id] = journal
        self.quest_journals = journals

    def _runtime_snapshot(self) -> dict:
        return {
            "version": self.version,
            "sequence": self.sequence,
            "dice_counters": self.dice.counters,
            "scheduler": self.scheduler.snapshot(),
            "ready_humans": sorted(self._ready_humans),
            "decision_pause_remaining": self._decision_pause_remaining,
            "registered_ai": sorted(self._registered_ai),
            "rules": self.rules.model_dump(mode="json"),
            "living": {
                "weather": {
                    "current": self.world.weather.current.value,
                    "last_change_world_minute": self.world.weather.last_change_world_minute,
                },
                "economy": {
                    item_id: {
                        "base_value": market.base_value,
                        "supply": market.supply,
                        "demand": market.demand,
                    }
                    for item_id, market in self.world.economy.markets.items()
                },
                "factions": {
                    "relations": [[a, b, value] for (a, b), value in self.world.factions.relations.items()],
                    "reputation": [[a, b, value] for (a, b), value in self.world.factions.reputation.items()],
                },
                "schedule_assignments": dict(self.world.schedules.assignments),
                "dynamic_events_fired": sorted(self.world.dynamic_events.fired),
                "shops": {shop.id: shop.model_dump(mode="json") for shop in self.shops.all()},
            },
            "exploration": {
                actor_id: value.model_dump(mode="json") for actor_id, value in self.exploration.by_actor.items()
            },
            "quest_journals": {
                actor_id: {
                    "active": {key: value.model_dump(mode="json") for key, value in journal.active.items()},
                    "completed": {key: value.model_dump(mode="json") for key, value in journal.completed.items()},
                }
                for actor_id, journal in self.quest_journals.items()
            },
        }

    async def _persist_state(self) -> None:
        self.state.simulation_time = self.scheduler.now
        self.state.world_minutes = self.world.clock.total_minutes
        self.state.metadata["engine_runtime"] = self._runtime_snapshot()
        self.state.metadata["engine_config"] = self.config.model_dump(mode="json")
        if self.store is None:
            return
        await self.store.save_campaign(self.state, self.version)
        if self.sequence and self.sequence % self.config.snapshot_every_events == 0:
            await self.store.save_snapshot(self.state, self.sequence, self.dice.counters, self.scheduler.snapshot())

    def state_payload(self) -> dict:
        return {
            "version": self.version,
            "campaign": self.state.model_dump(mode="json"),
            "time_mode": self.config.time_mode.value,
            "ready_humans": sorted(self._ready_humans),
            "decision_pause_remaining": self._decision_pause_remaining,
            "scheduler": self.scheduler.snapshot(),
            "weather": self.world.weather.current.value,
            "world_time": self.world.clock.display(),
        }
