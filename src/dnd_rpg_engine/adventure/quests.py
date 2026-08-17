# src/dnd_rpg_engine/adventure/quests.py
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.events import GameEvent


class QuestStatus(StrEnum):
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class ObjectiveType(StrEnum):
    VISIT = "visit"
    INTERACT = "interact"
    DEFEAT = "defeat"
    COLLECT = "collect"
    CUSTOM = "custom"


class QuestObjective(BaseModel):
    id: str
    type: ObjectiveType
    target_id: str
    required: int = Field(default=1, ge=1)
    progress: int = Field(default=0, ge=0)

    @property
    def complete(self) -> bool:
        return self.progress >= self.required


class QuestDefinition(BaseModel):
    id: str
    name: str
    description: str = ""
    objectives: list[QuestObjective] = Field(default_factory=list)
    reward_currency: int = Field(default=0, ge=0)
    set_flags: dict[str, object] = Field(default_factory=dict)


class QuestProgress(BaseModel):
    quest: QuestDefinition
    status: QuestStatus = QuestStatus.ACTIVE

    @property
    def complete(self) -> bool:
        return bool(self.quest.objectives) and all(o.complete for o in self.quest.objectives)


class QuestJournal:
    def __init__(self) -> None:
        self.active: dict[str, QuestProgress] = {}
        self.completed: dict[str, QuestProgress] = {}

    def start(self, quest: QuestDefinition) -> QuestProgress:
        progress = QuestProgress(quest=quest.model_copy(deep=True))
        self.active[quest.id] = progress
        return progress

    def apply_event(self, event: GameEvent) -> list[str]:
        completed: list[str] = []
        event_to_objective = {
            "location.visited": ObjectiveType.VISIT,
            "entity.interacted": ObjectiveType.INTERACT,
            "combat.entity_defeated": ObjectiveType.DEFEAT,
            "inventory.item_added": ObjectiveType.COLLECT,
        }
        objective_type = event_to_objective.get(event.type)
        if objective_type is None:
            return completed
        target = event.target_id or str(event.payload.get("target_id", ""))
        for quest_id, progress in list(self.active.items()):
            for objective in progress.quest.objectives:
                if objective.type is objective_type and objective.target_id == target and not objective.complete:
                    objective.progress = min(objective.required, objective.progress + int(event.payload.get("quantity", 1)))
            if progress.complete:
                progress.status = QuestStatus.COMPLETED
                self.completed[quest_id] = self.active.pop(quest_id)
                completed.append(quest_id)
        return completed
