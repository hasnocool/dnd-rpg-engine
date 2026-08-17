from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.commands import GameCommand, parse_command
from dnd_rpg_engine.core.events import GameEvent
from dnd_rpg_engine.core.models import CampaignState


class DirectorObjectiveKind(StrEnum):
    TENSION = "tension"
    STORY_THREAD = "story_thread"
    RELATIONSHIP = "relationship"
    FACTION = "faction"
    VARIETY = "variety"
    CONSEQUENCE = "consequence"


class StoryThreadStatus(StrEnum):
    OPEN = "open"
    ACTIVE = "active"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class StoryThread(BaseModel):
    id: str
    title: str
    status: StoryThreadStatus = StoryThreadStatus.OPEN
    weight: float = Field(default=1.0, ge=0, le=10)
    involved_entity_ids: set[str] = Field(default_factory=set)
    tags: set[str] = Field(default_factory=set)
    beats: list[str] = Field(default_factory=list)
    last_advanced_at: float = 0.0


class DirectorState(BaseModel):
    tension: float = Field(default=0.35, ge=0, le=1)
    threads: dict[str, StoryThread] = Field(default_factory=dict)
    recent_scene_tags: list[str] = Field(default_factory=list)
    event_count: int = 0
    last_proposal_sequence: int = 0
    faction_pressure: dict[str, float] = Field(default_factory=dict)
    relationship_pressure: dict[str, float] = Field(default_factory=dict)


class DirectorIntentKind(StrEnum):
    ADVANCE_THREAD = "advance_thread"
    INTRODUCE_ENCOUNTER = "introduce_encounter"
    SOCIAL_BEAT = "social_beat"
    FACTION_CONSEQUENCE = "faction_consequence"
    RECOVERY_BEAT = "recovery_beat"
    WORLD_EVENT = "world_event"


class DirectorProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    sequence: int
    kind: DirectorIntentKind
    reason: str
    urgency: float = Field(default=0.5, ge=0, le=1)
    thread_id: str | None = None
    suggested_command: dict[str, Any] | None = None
    tags: set[str] = Field(default_factory=set)
    approved: bool = False
    rejected: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class DirectorProvider(Protocol):
    async def propose(self, context: dict[str, Any]) -> list[DirectorProposal]: ...


class CampaignDirector:
    """Persistent campaign-level planner that proposes, but never mutates, truth."""

    metadata_key = "campaign_director"

    def __init__(self) -> None:
        self.proposals: dict[str, DirectorProposal] = {}

    def state_for(self, campaign: CampaignState) -> DirectorState:
        raw = campaign.metadata.get(self.metadata_key)
        if isinstance(raw, dict):
            return DirectorState.model_validate(raw)
        return DirectorState()

    def save_state(self, campaign: CampaignState, state: DirectorState) -> None:
        campaign.metadata[self.metadata_key] = state.model_dump(mode="json")

    def add_thread(self, campaign: CampaignState, thread: StoryThread) -> StoryThread:
        state = self.state_for(campaign)
        state.threads[thread.id] = thread
        self.save_state(campaign, state)
        return thread

    def observe(self, campaign: CampaignState, events: list[GameEvent]) -> DirectorState:
        state = self.state_for(campaign)
        for event in events:
            state.event_count += 1
            tag = self._scene_tag(event.type)
            state.recent_scene_tags.append(tag)
            state.recent_scene_tags = state.recent_scene_tags[-24:]
            if event.type.startswith("combat."):
                state.tension = min(1.0, state.tension * 0.82 + 0.23)
            elif event.type.startswith("dialogue.") or event.type.startswith("quest."):
                state.tension = min(1.0, state.tension * 0.90 + 0.08)
            elif event.type in {"character.rested", "timeline.waited"}:
                state.tension = max(0.0, state.tension * 0.72 - 0.05)
            else:
                state.tension = max(0.0, min(1.0, state.tension * 0.97 + 0.01))
            faction_id = event.payload.get("faction_id") if isinstance(event.payload, dict) else None
            if faction_id:
                key = str(faction_id)
                state.faction_pressure[key] = min(1.0, state.faction_pressure.get(key, 0.0) + 0.08)
            for thread in state.threads.values():
                if thread.status in {StoryThreadStatus.OPEN, StoryThreadStatus.ACTIVE} and thread.tags & set(event.type.split(".")):
                    thread.status = StoryThreadStatus.ACTIVE
                    thread.last_advanced_at = campaign.simulation_time
        self.save_state(campaign, state)
        return state

    def propose(self, campaign: CampaignState, *, limit: int = 3) -> list[DirectorProposal]:
        state = self.state_for(campaign)
        candidates: list[tuple[float, DirectorProposal]] = []
        repetition = self._repetition(state.recent_scene_tags)
        active_threads = [
            value for value in state.threads.values() if value.status in {StoryThreadStatus.OPEN, StoryThreadStatus.ACTIVE}
        ]
        active_threads.sort(key=lambda value: (-value.weight, value.last_advanced_at, value.id))
        if active_threads:
            thread = active_threads[0]
            urgency = min(1.0, 0.45 + thread.weight * 0.05 + min(0.3, campaign.simulation_time - thread.last_advanced_at) / 1000)
            candidates.append(
                (
                    urgency,
                    self._proposal(
                        state,
                        DirectorIntentKind.ADVANCE_THREAD,
                        f"advance unresolved thread: {thread.title}",
                        urgency,
                        thread_id=thread.id,
                        tags={"story", *thread.tags},
                    ),
                )
            )
        if state.tension < 0.32:
            urgency = min(0.9, 0.58 + (0.32 - state.tension))
            candidates.append(
                (
                    urgency,
                    self._proposal(
                        state,
                        DirectorIntentKind.INTRODUCE_ENCOUNTER,
                        "tension has fallen below the configured dramatic floor",
                        urgency,
                        tags={"encounter", "pressure"},
                    ),
                )
            )
        if state.tension > 0.82:
            urgency = min(1.0, 0.6 + (state.tension - 0.82))
            candidates.append(
                (
                    urgency,
                    self._proposal(
                        state,
                        DirectorIntentKind.RECOVERY_BEAT,
                        "sustained tension is high; offer a recovery or social beat",
                        urgency,
                        tags={"recovery", "social"},
                    ),
                )
            )
        if repetition > 0.55:
            candidates.append(
                (
                    repetition,
                    self._proposal(
                        state,
                        DirectorIntentKind.SOCIAL_BEAT,
                        "recent scene types are repetitive",
                        repetition,
                        tags={"variety", "social"},
                    ),
                )
            )
        if state.faction_pressure:
            faction_id, pressure = max(sorted(state.faction_pressure.items()), key=lambda row: row[1])
            if pressure >= 0.4:
                candidates.append(
                    (
                        pressure,
                        self._proposal(
                            state,
                            DirectorIntentKind.FACTION_CONSEQUENCE,
                            f"unresolved faction pressure from {faction_id}",
                            pressure,
                            tags={"faction", "consequence"},
                            metadata={"faction_id": faction_id},
                        ),
                    )
                )
        candidates.sort(key=lambda row: (-row[0], row[1].kind.value, row[1].id))
        selected = [proposal for _, proposal in candidates[: max(0, limit)]]
        for proposal in selected:
            self.proposals[proposal.id] = proposal
        self.save_state(campaign, state)
        return selected

    def attach_command(self, proposal_id: str, command: dict[str, Any]) -> DirectorProposal:
        proposal = self.proposals[proposal_id]
        # Parse now so providers/GM tools cannot attach malformed commands.
        parsed = parse_command(command)
        proposal.suggested_command = parsed.model_dump(mode="json")
        return proposal

    def approve(self, proposal_id: str) -> GameCommand | None:
        proposal = self.proposals[proposal_id]
        if proposal.rejected:
            raise ValueError("rejected proposal cannot be approved")
        proposal.approved = True
        return parse_command(proposal.suggested_command) if proposal.suggested_command else None

    def reject(self, proposal_id: str) -> DirectorProposal:
        proposal = self.proposals[proposal_id]
        if proposal.approved:
            raise ValueError("approved proposal cannot be rejected")
        proposal.rejected = True
        return proposal

    def provider_context(self, campaign: CampaignState) -> dict[str, Any]:
        state = self.state_for(campaign)
        return {
            "campaign_id": campaign.id,
            "simulation_time": campaign.simulation_time,
            "tension": state.tension,
            "threads": [value.model_dump(mode="json") for value in state.threads.values()],
            "recent_scene_tags": list(state.recent_scene_tags),
            "faction_pressure": dict(state.faction_pressure),
            # Deliberately omit writable engine/service objects.
        }

    @staticmethod
    def _scene_tag(event_type: str) -> str:
        return event_type.split(".", 1)[0]

    @staticmethod
    def _repetition(tags: list[str]) -> float:
        if len(tags) < 4:
            return 0.0
        recent = tags[-8:]
        counts: dict[str, int] = {}
        for tag in recent:
            counts[tag] = counts.get(tag, 0) + 1
        return max(counts.values()) / len(recent)

    @staticmethod
    def _proposal(
        state: DirectorState,
        kind: DirectorIntentKind,
        reason: str,
        urgency: float,
        *,
        thread_id: str | None = None,
        tags: set[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DirectorProposal:
        state.last_proposal_sequence += 1
        stable = hashlib.sha256(
            f"{state.last_proposal_sequence}:{kind.value}:{reason}:{thread_id or ''}".encode()
        ).hexdigest()[:16]
        return DirectorProposal(
            id=f"director:{state.last_proposal_sequence}:{stable}",
            sequence=state.last_proposal_sequence,
            kind=kind,
            reason=reason,
            urgency=urgency,
            thread_id=thread_id,
            tags=tags or set(),
            metadata=metadata or {},
        )
