from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CampaignPhase(StrEnum):
    EXPLORATION = "exploration"
    TRAVEL = "travel"
    SOCIAL = "social"
    ENCOUNTER = "encounter"
    REST = "rest"
    DOWNTIME = "downtime"


class CampaignRuntimeState(BaseModel):
    phase: CampaignPhase = CampaignPhase.EXPLORATION
    party_actor_ids: set[str] = Field(default_factory=set)
    active_encounter_id: str | None = None
    current_map_id: str | None = None
    current_node_id: str | None = None
    chapter_id: str | None = None
    completed_beats: set[str] = Field(default_factory=set)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)


class CampaignStepResult(BaseModel):
    phase: CampaignPhase
    world_minutes: float
    events: list[dict[str, Any]] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    encounter_id: str | None = None
