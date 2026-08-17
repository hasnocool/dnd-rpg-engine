# src/dnd_rpg_engine/adventure/dialogue.py
from __future__ import annotations

from pydantic import BaseModel, Field


class DialogueRequirement(BaseModel):
    flag: str
    equals: object = True


class DialogueOption(BaseModel):
    id: str
    text: str
    next_node: str | None = None
    requirements: list[DialogueRequirement] = Field(default_factory=list)
    set_flags: dict[str, object] = Field(default_factory=dict)
    quest_id: str | None = None


class DialogueNode(BaseModel):
    id: str
    speaker_id: str | None = None
    text: str
    options: list[DialogueOption] = Field(default_factory=list)


class DialogueGraph(BaseModel):
    id: str
    start_node: str
    nodes: dict[str, DialogueNode]

    def available_options(self, node_id: str, flags: dict[str, object]) -> list[DialogueOption]:
        node = self.nodes[node_id]
        return [
            option
            for option in node.options
            if all(flags.get(req.flag) == req.equals for req in option.requirements)
        ]

    def choose(self, node_id: str, option_id: str, flags: dict[str, object]) -> DialogueOption:
        options = {o.id: o for o in self.available_options(node_id, flags)}
        if option_id not in options:
            raise ValueError("dialogue option is unavailable")
        option = options[option_id]
        flags.update(option.set_flags)
        return option


class DialogueRegistry:
    def __init__(self) -> None:
        self._graphs: dict[str, DialogueGraph] = {}

    def register(self, graph: DialogueGraph) -> None:
        self._graphs[graph.id] = graph

    def require(self, dialogue_id: str) -> DialogueGraph:
        try:
            return self._graphs[dialogue_id]
        except KeyError as exc:
            raise KeyError(f"unknown dialogue: {dialogue_id}") from exc
