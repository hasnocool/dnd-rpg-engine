# src/dnd_rpg_engine/adventure/exploration.py
from __future__ import annotations

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.dice import DeterministicDice


class ExplorationState(BaseModel):
    revealed_nodes: set[str] = Field(default_factory=set)
    visited_nodes: set[str] = Field(default_factory=set)
    discoveries: set[str] = Field(default_factory=set)


class ExplorationSystem:
    def __init__(self, dice: DeterministicDice) -> None:
        self.dice = dice
        self.by_actor: dict[str, ExplorationState] = {}

    def state_for(self, actor_id: str) -> ExplorationState:
        return self.by_actor.setdefault(actor_id, ExplorationState())

    def visit(self, actor_id: str, node_id: str) -> ExplorationState:
        state = self.state_for(actor_id)
        state.revealed_nodes.add(node_id)
        state.visited_nodes.add(node_id)
        return state

    def discover(self, actor_id: str, discovery_id: str, *, dc: int = 12, modifier: int = 0) -> bool:
        state = self.state_for(actor_id)
        if discovery_id in state.discoveries:
            return True
        roll = self.dice.d20(stream=f"explore:{actor_id}:{discovery_id}") + modifier
        if roll >= dc:
            state.discoveries.add(discovery_id)
            return True
        return False
