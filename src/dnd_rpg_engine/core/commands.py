# src/dnd_rpg_engine/core/commands.py
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CommandBase(BaseModel):
    command_id: str = Field(default_factory=lambda: str(uuid4()))
    actor_id: str
    expected_version: int | None = None


class AttackCommand(CommandBase):
    type: Literal["attack"] = "attack"
    target_id: str
    action_id: str = "basic_attack"


class MoveCommand(CommandBase):
    type: Literal["move"] = "move"
    map_id: str | None = None
    x: float
    y: float
    z: float = 0.0


class CastCommand(CommandBase):
    type: Literal["cast"] = "cast"
    spell_id: str
    target_id: str | None = None


class UseItemCommand(CommandBase):
    type: Literal["use_item"] = "use_item"
    item_id: str
    target_id: str | None = None


class WaitCommand(CommandBase):
    type: Literal["wait"] = "wait"
    duration: float | None = None


class EndTurnCommand(CommandBase):
    type: Literal["end_turn"] = "end_turn"


class RestCommand(CommandBase):
    type: Literal["rest"] = "rest"
    rest_kind: Literal["short", "long"]
    hit_dice_to_spend: int = Field(default=0, ge=0, le=20)


class PrepareSpellsCommand(CommandBase):
    type: Literal["prepare_spells"] = "prepare_spells"
    spell_ids: set[str] = Field(default_factory=set)


class ReactionCommand(CommandBase):
    type: Literal["reaction"] = "reaction"
    window_id: str
    reaction_id: str
    target_id: str | None = None


class TravelCommand(CommandBase):
    type: Literal["travel"] = "travel"
    map_id: str
    destination_node_id: str
    pace: Literal["slow", "normal", "fast"] = "normal"


class InteractCommand(CommandBase):
    type: Literal["interact"] = "interact"
    target_id: str
    interaction: str = "default"


class DialogueCommand(CommandBase):
    type: Literal["dialogue"] = "dialogue"
    dialogue_id: str
    option_id: str


class ShopCommand(CommandBase):
    type: Literal["shop"] = "shop"
    shop_id: str
    operation: Literal["buy", "sell"]
    item_id: str
    quantity: int = Field(default=1, ge=1, le=999)


class CustomCommand(CommandBase):
    type: Literal["custom"] = "custom"
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


GameCommand = (
    AttackCommand
    | MoveCommand
    | CastCommand
    | UseItemCommand
    | WaitCommand
    | EndTurnCommand
    | RestCommand
    | PrepareSpellsCommand
    | ReactionCommand
    | TravelCommand
    | InteractCommand
    | DialogueCommand
    | ShopCommand
    | CustomCommand
)

_COMMAND_TYPES = {
    "attack": AttackCommand,
    "move": MoveCommand,
    "cast": CastCommand,
    "use_item": UseItemCommand,
    "wait": WaitCommand,
    "end_turn": EndTurnCommand,
    "rest": RestCommand,
    "prepare_spells": PrepareSpellsCommand,
    "reaction": ReactionCommand,
    "travel": TravelCommand,
    "interact": InteractCommand,
    "dialogue": DialogueCommand,
    "shop": ShopCommand,
    "custom": CustomCommand,
}


def parse_command(data: dict[str, Any]) -> GameCommand:
    kind = str(data.get("type", ""))
    model = _COMMAND_TYPES.get(kind)
    if model is None:
        raise ValueError(f"unknown command type: {kind}")
    return model.model_validate(data)
