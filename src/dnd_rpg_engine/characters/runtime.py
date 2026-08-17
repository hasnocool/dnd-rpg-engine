from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from dnd_rpg_engine.core.commands import (
    AttackCommand,
    CastCommand,
    EndTurnCommand,
    GameCommand,
    InteractCommand,
    MoveCommand,
    PrepareSpellsCommand,
    ReactionCommand,
    RestCommand,
    UseItemCommand,
    WaitCommand,
)
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, Position, ResourcePool
from dnd_rpg_engine.rulesets.srd_5_2_1.catalog import BACKGROUNDS, CLASSES, FEATS, SKILLS, SPECIES
from dnd_rpg_engine.rulesets.srd_5_2_1.rules import proficiency_bonus

from .models import (
    CharacterBuildRequest,
    CharacterState,
    FeatureResource,
    HitDiceState,
    RecoveryPolicy,
    SpellcastingState,
    TurnState,
)

if TYPE_CHECKING:
    from dnd_rpg_engine.core.engine import GameEngine
    from dnd_rpg_engine.rulesets.srd_5_2_1.runtime import SRDRuntimeCatalog


XP_THRESHOLDS: tuple[int, ...] = (
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000,
)


class CharacterRuntime:
    """Typed character state layered over generic Entity components.

    The serialized source of truth remains inside the entity so old persistence,
    multiplayer, event replay, and renderer adapters keep working unchanged.
    """

    COMPONENT = "character"

    def __init__(self, engine: "GameEngine") -> None:
        self.engine = engine
        self.catalog: "SRDRuntimeCatalog | None" = None

    def bind_catalog(self, catalog: "SRDRuntimeCatalog | None") -> None:
        self.catalog = catalog

    @staticmethod
    def has_character(entity: Entity) -> bool:
        return bool(entity.components.get(CharacterRuntime.COMPONENT))

    @staticmethod
    def state(entity: Entity) -> CharacterState:
        raw = entity.components.get(CharacterRuntime.COMPONENT)
        if not raw:
            raise ValueError(f"entity is not a built character: {entity.id}")
        return CharacterState.model_validate(raw)

    @staticmethod
    def save(entity: Entity, state: CharacterState) -> None:
        entity.components[CharacterRuntime.COMPONENT] = state.model_dump(mode="json")
        entity.components["progression"] = {"level": state.level, "xp": state.xp}
        entity.components["proficiencies"] = {
            "bonus": proficiency_bonus(state.level),
            "skills": sorted(state.skill_proficiencies),
            "expertise": sorted(state.expertise),
        }
        if state.spellcasting.ability:
            entity.components["spellcasting"] = state.spellcasting.model_dump(mode="json")

    async def build(self, request: CharacterBuildRequest, *, entity_id: str | None = None) -> Entity:
        class_def = CLASSES.get(request.class_id)
        species = SPECIES.get(request.species_id)
        background = BACKGROUNDS.get(request.background_id)
        if class_def is None:
            raise ValueError(f"unknown SRD class: {request.class_id}")
        if species is None:
            raise ValueError(f"unknown SRD species: {request.species_id}")
        if background is None:
            raise ValueError(f"unknown SRD background: {request.background_id}")
        if request.subclass_id and self.catalog is not None:
            raw = await self.catalog.store.get("subclasses", request.subclass_id)
            if raw is None or raw.get("class_id") != request.class_id:
                raise ValueError("subclass does not belong to selected class")
        invalid_skills = (request.skill_proficiencies | request.expertise) - set(SKILLS)
        if invalid_skills:
            raise ValueError(f"unknown skills: {sorted(invalid_skills)}")
        invalid_feats = request.feat_ids - set(FEATS)
        if invalid_feats:
            raise ValueError(f"unknown feats: {sorted(invalid_feats)}")

        con_mod = request.stats.modifier("constitution")
        hp = max(1, class_def.hit_die + con_mod)
        for _ in range(2, request.level + 1):
            hp += max(1, class_def.hit_die // 2 + 1 + con_mod)
        skills = set(request.skill_proficiencies) | set(background.skill_proficiencies)
        feats = set(request.feat_ids) | {background.origin_feat_id}
        spell_slots, features = await self._progression(request.class_id, request.level)
        spellcasting = SpellcastingState(
            ability=class_def.spellcasting_ability.value if class_def.spellcasting_ability else None,
            known_spells=set(request.known_spells),
            prepared_spells=set(request.prepared_spells),
            slots=dict(spell_slots),
            maximum_slots=dict(spell_slots),
        )
        state = CharacterState(
            class_id=request.class_id,
            subclass_id=request.subclass_id,
            species_id=request.species_id,
            background_id=request.background_id,
            level=request.level,
            feature_ids=set(features),
            feat_ids=feats,
            skill_proficiencies=skills,
            expertise=set(request.expertise),
            hit_dice=HitDiceState(die_size=class_def.hit_die, current=request.level, maximum=request.level),
            spellcasting=spellcasting,
            turn=TurnState(movement_max=float(species.speed_feet), movement_remaining=float(species.speed_feet)),
            advancement_log=[{"level": request.level, "reason": "character_created"}],
        )
        entity = Entity(
            id=entity_id or request.name.lower().replace(" ", "-") or "character",
            name=request.name,
            kind=EntityKind.PLAYER,
            controller=ControllerKind.HUMAN,
            owner_id=request.owner_id,
            stats=request.stats,
            resources=ResourcePool(hp=hp, max_hp=hp),
            position=Position(),
            tags={"player_character", "srd_5_2_1", request.class_id, request.species_id},
            components={
                "combat": {"armor_class": 10 + request.stats.modifier("dexterity")},
                "movement": {"speed_feet": species.speed_feet, "units_per_second": species.speed_feet / 20.0},
            },
        )
        self.save(entity, state)
        return entity

    async def _progression(self, class_id: str, level: int) -> tuple[dict[int, int], set[str]]:
        slots: dict[int, int] = {}
        features: set[str] = set()
        if self.catalog is None:
            return slots, features
        for current in range(1, level + 1):
            raw = await self.catalog.store.get("class_progressions", f"{class_id}.{current}")
            if not raw:
                continue
            features.update(raw.get("feature_ids", []))
            features.update(raw.get("subclass_feature_ids", []))
            raw_slots = list(raw.get("spell_slots", []))
            if current == level:
                slots = {idx + 1: int(count) for idx, count in enumerate(raw_slots) if int(count) > 0}
        return slots, features

    def begin_turn(self, entity: Entity) -> None:
        if not self.has_character(entity):
            return
        state = self.state(entity)
        speed = float(entity.component("movement").get("speed_feet", state.turn.movement_max))
        state.turn.reset(speed)
        for resource in state.resources.values():
            if resource.recovery in {RecoveryPolicy.TURN, RecoveryPolicy.ROUND}:
                resource.restore()
        self.save(entity, state)

    def command_cost(self, entity: Entity, command: GameCommand) -> str | None:
        if not self.has_character(entity):
            return None
        if isinstance(command, MoveCommand):
            return "movement"
        if isinstance(command, ReactionCommand):
            return "reaction"
        if isinstance(command, EndTurnCommand):
            return "end_turn"
        if isinstance(command, CastCommand):
            try:
                spell = self.engine.spells.require(command.spell_id)
                if spell.cast_time <= 3.0:
                    return "bonus_action"
            except KeyError:
                pass
            return "action"
        if isinstance(command, RestCommand):
            return "end_turn"
        if isinstance(command, (AttackCommand, UseItemCommand, InteractCommand, PrepareSpellsCommand)):
            return "action"
        if isinstance(command, WaitCommand):
            return "end_turn"
        return "action"

    def validate_command(self, entity: Entity, command: GameCommand) -> None:
        if not self.has_character(entity):
            return
        state = self.state(entity)
        cost = self.command_cost(entity, command)
        if cost != "reaction" and not state.turn.active:
            # Out-of-encounter/free-play commands are permitted; readiness will
            # start a formal ledger when the timeline asks for a turn.
            return
        if cost == "action" and not state.turn.action_available:
            raise ValueError("action already used this turn")
        if cost == "bonus_action" and not state.turn.bonus_action_available:
            raise ValueError("bonus action already used this turn")
        if cost == "reaction" and not state.turn.reaction_available:
            raise ValueError("reaction already used this round")
        if isinstance(command, MoveCommand):
            distance_units = entity.position.distance_to(Position(area_id=entity.position.area_id, x=command.x, y=command.y, z=command.z))
            distance_feet = distance_units * 5.0
            if distance_feet > state.turn.movement_remaining + 1e-9:
                raise ValueError("movement exceeds remaining speed for this turn")
        if isinstance(command, CastCommand):
            spell = self.engine.spells.require(command.spell_id)
            casting = state.spellcasting
            if not casting.can_cast(command.spell_id, spell.level):
                raise ValueError("spell is not available or has no remaining slot")
        if isinstance(command, PrepareSpellsCommand):
            unknown = set(command.spell_ids) - state.spellcasting.known_spells
            if state.spellcasting.known_spells and unknown:
                raise ValueError(f"cannot prepare unknown spells: {sorted(unknown)}")

    def apply_command(self, entity: Entity, command: GameCommand, *, old_position: Position | None = None) -> bool:
        """Consume turn resources. Returns True while the actor stays ready."""
        if not self.has_character(entity):
            return False
        state = self.state(entity)
        if not state.turn.active:
            return False
        cost = self.command_cost(entity, command)
        if cost == "movement":
            if old_position is not None:
                state.turn.movement_remaining = max(0.0, state.turn.movement_remaining - old_position.distance_to(entity.position) * 5.0)
        elif cost == "action":
            state.turn.action_available = False
        elif cost == "bonus_action":
            state.turn.bonus_action_available = False
        elif cost == "reaction":
            state.turn.reaction_available = False
        elif cost == "end_turn":
            state.turn.active = False
        if isinstance(command, CastCommand):
            spell = self.engine.spells.require(command.spell_id)
            state.spellcasting.spend_slot(spell.level)
            if spell.concentration:
                state.spellcasting.concentration_spell_id = spell.id
        if isinstance(command, PrepareSpellsCommand):
            state.spellcasting.prepared_spells = set(command.spell_ids)
        self.save(entity, state)
        if cost == "end_turn":
            return False
        return any((state.turn.action_available, state.turn.bonus_action_available, state.turn.movement_remaining > 0))

    def available_actions(self, entity: Entity) -> dict[str, Any]:
        if not self.has_character(entity):
            return {"character": False, "available": ["attack", "move", "wait", "interact"]}
        state = self.state(entity)
        available: list[str] = []
        if state.turn.action_available:
            available.extend(["attack", "dash", "disengage", "dodge", "help", "hide", "ready", "search", "study", "use_item"])
            for spell_id in sorted(state.spellcasting.known_spells | state.spellcasting.prepared_spells):
                try:
                    spell = self.engine.spells.require(spell_id)
                except KeyError:
                    continue
                if spell.cast_time > 3.0 and state.spellcasting.can_cast(spell_id, spell.level):
                    available.append(f"cast:{spell_id}")
        if state.turn.bonus_action_available:
            for spell_id in sorted(state.spellcasting.known_spells | state.spellcasting.prepared_spells):
                try:
                    spell = self.engine.spells.require(spell_id)
                except KeyError:
                    continue
                if spell.cast_time <= 3.0 and state.spellcasting.can_cast(spell_id, spell.level):
                    available.append(f"cast:{spell_id}")
        if state.turn.movement_remaining > 0:
            available.append("move")
        available.append("end_turn")
        return {
            "character": True,
            "level": state.level,
            "class_id": state.class_id,
            "turn": state.turn.model_dump(mode="json"),
            "spellcasting": state.spellcasting.model_dump(mode="json"),
            "available": available,
        }

    async def level_up(self, entity: Entity, *, target_level: int | None = None, reason: str = "milestone") -> CharacterState:
        state = self.state(entity)
        new_level = target_level or state.level + 1
        if new_level != state.level + 1 or new_level > 20:
            raise ValueError("level-up must advance exactly one level through 20")
        class_def = CLASSES[state.class_id]
        con_mod = entity.stats.modifier("constitution")
        hp_gain = max(1, class_def.hit_die // 2 + 1 + con_mod)
        entity.resources.max_hp += hp_gain
        entity.resources.hp += hp_gain
        slots, features = await self._progression(state.class_id, new_level)
        state.level = new_level
        state.hit_dice.maximum = new_level
        state.hit_dice.current += 1
        state.feature_ids.update(features)
        state.spellcasting.maximum_slots = slots
        for slot_level, maximum in slots.items():
            state.spellcasting.slots[slot_level] = max(state.spellcasting.slots.get(slot_level, 0), maximum)
        state.advancement_log.append({"level": new_level, "reason": reason, "hp_gain": hp_gain})
        self.save(entity, state)
        return state

    async def award_xp(self, entity: Entity, amount: int) -> list[int]:
        if amount < 0:
            raise ValueError("xp award cannot be negative")
        state = self.state(entity)
        state.xp += amount
        self.save(entity, state)
        gained: list[int] = []
        while state.level < 20 and state.xp >= XP_THRESHOLDS[state.level]:
            state = await self.level_up(entity, reason="xp")
            gained.append(state.level)
        return gained

    def recover(self, entity: Entity, rest_kind: str, *, hit_dice_to_spend: int = 0) -> dict[str, Any]:
        state = self.state(entity)
        restored: list[str] = []
        healed = 0
        if rest_kind == "short":
            spend = min(max(0, hit_dice_to_spend), state.hit_dice.current)
            for index in range(spend):
                roll = self.engine.dice.roll(
                    f"1d{state.hit_dice.die_size}+{entity.stats.modifier('constitution')}",
                    stream=f"rest:hit-die:{entity.id}:{state.level}:{index}",
                )
                healed += entity.resources.heal(max(0, roll.total))
            state.hit_dice.current -= spend
            for resource in state.resources.values():
                if resource.recovery is RecoveryPolicy.SHORT_REST:
                    resource.restore(); restored.append(resource.id)
        elif rest_kind == "long":
            healed = entity.resources.heal(entity.resources.max_hp)
            state.spellcasting.restore_slots()
            for resource in state.resources.values():
                if resource.recovery in {RecoveryPolicy.SHORT_REST, RecoveryPolicy.LONG_REST}:
                    resource.restore(); restored.append(resource.id)
            state.hit_dice.current = min(state.hit_dice.maximum, state.hit_dice.current + max(1, math.ceil(state.hit_dice.maximum / 2)))
            entity.component("death_saves").clear()
        else:
            raise ValueError("rest kind must be short or long")
        self.save(entity, state)
        return {"healed": healed, "restored_resources": restored, "hit_dice": state.hit_dice.model_dump(mode="json")}
