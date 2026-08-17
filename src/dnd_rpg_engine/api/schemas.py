# src/dnd_rpg_engine/api/schemas.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.models import ControllerKind, EntityKind, GameConfig, Position, ResourcePool, Stats, TimeMode


class CreateCampaignRequest(BaseModel):
    name: str = "New Campaign"
    owner_id: str = "local"
    seed: int = 1
    time_mode: TimeMode = TimeMode.HYBRID
    player_decision_timeout_seconds: float | None = Field(default=10.0, gt=0)

    def config(self) -> GameConfig:
        return GameConfig(
            seed=self.seed,
            time_mode=self.time_mode,
            player_decision_timeout_seconds=self.player_decision_timeout_seconds,
        )


class CreateEntityRequest(BaseModel):
    id: str | None = None
    name: str
    kind: EntityKind = EntityKind.NPC
    controller: ControllerKind = ControllerKind.NONE
    owner_id: str | None = None
    stats: Stats = Field(default_factory=Stats)
    resources: ResourcePool = Field(default_factory=ResourcePool)
    position: Position = Field(default_factory=Position)
    tags: set[str] = Field(default_factory=set)
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)
    ready_delay: float = Field(default=0.0, ge=0)


class CommandRequest(BaseModel):
    command: dict[str, Any]
    narrate: bool = False
    client_id: str | None = None


class TickRequest(BaseModel):
    seconds: float = Field(gt=0, le=3600)
    narrate: bool = False


class JoinRequest(BaseModel):
    user_id: str
    display_name: str
    role: str = "player"
    actor_ids: set[str] = Field(default_factory=set)


class UpdateTimingRequest(BaseModel):
    time_mode: TimeMode | None = None
    player_decision_timeout_seconds: float | None = Field(default=None, gt=0)
    pause_when_player_ready: bool | None = None
    time_scale: float | None = Field(default=None, gt=0, le=100)


class EncounterRequest(BaseModel):
    participant_ids: list[str] = Field(min_length=2)


class InstantiatePackRequest(BaseModel):
    pack: dict[str, Any]
    campaign_template_id: str
    owner_id: str = "local"

from dnd_rpg_engine.characters.models import CharacterBuildRequest


class LevelUpRequest(BaseModel):
    target_level: int | None = Field(default=None, ge=2, le=20)
    reason: str = "milestone"


class AwardXPRequest(BaseModel):
    amount: int = Field(ge=0)


class ConfigurePartyRequest(BaseModel):
    actor_ids: set[str] = Field(min_length=1)
    map_id: str | None = None
    node_id: str | None = None


class TravelRequest(BaseModel):
    actor_id: str
    map_id: str
    destination_node_id: str
    pace: str = Field(default="normal", pattern="^(slow|normal|fast)$")


class BudgetedEncounterRequest(BaseModel):
    party_levels: list[int] = Field(min_length=1)
    difficulty: str = Field(default="moderate", pattern="^(low|moderate|high)$")
    query: str = ""


class CampaignExportRequest(BaseModel):
    include_events: bool = False


class ReactionWindowRequest(BaseModel):
    trigger_event_id: str
    eligible_actor_ids: set[str] = Field(min_length=1)
    allowed_reactions: set[str] = Field(default_factory=set)
    timeout_seconds: float | None = Field(default=None, ge=0, le=60)

class ReconnectRequest(BaseModel):
    client_id: str
    user_id: str


class CreatePartyRequest(BaseModel):
    party_id: str
    name: str
    actor_ids: set[str] = Field(default_factory=set)
    member_user_ids: set[str] = Field(default_factory=set)


class ImportCampaignRequest(BaseModel):
    package: dict[str, Any]
    owner_id: str = "local"
    regenerate_id: bool = True


class PlayableCampaignRequest(BaseModel):
    campaign_name: str = "New SRD Campaign"
    owner_id: str = "local"
    seed: int = 1
    time_mode: TimeMode = TimeMode.TURN_BASED
    character: CharacterBuildRequest
