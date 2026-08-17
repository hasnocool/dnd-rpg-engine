from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.campaign.orchestrator import CampaignOrchestrator, SceneKind
from dnd_rpg_engine.core.models import CampaignState, EntityKind


class DirectorProposalKind(StrEnum):
    PACING = "pacing"
    ENCOUNTER = "encounter"
    QUEST = "quest"
    WORLD_EVENT = "world_event"
    FACTION_MOVE = "faction_move"
    DOWNTIME = "downtime"


class DirectorProposal(BaseModel):
    id: str
    kind: DirectorProposalKind
    utility: float = Field(ge=0.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)


class DirectorSnapshot(BaseModel):
    simulation_time: float
    player_count: int
    living_player_count: int
    average_hp_fraction: float
    active_scene_kinds: list[str] = Field(default_factory=list)
    recent_pressure: float = 0.0
    unresolved_quest_count: int = 0
    faction_count: int = 0


class AIDirector:
    """Campaign-scale deterministic proposal engine.

    The director never mutates authoritative state. It produces ranked,
    explainable proposals that a policy, GM, or normal command path may accept.
    This preserves the same authority boundary used by individual actor AI.
    """

    def observe(
        self,
        state: CampaignState,
        *,
        orchestrator: CampaignOrchestrator | None = None,
    ) -> DirectorSnapshot:
        players = [entity for entity in state.entities.values() if entity.kind is EntityKind.PLAYER]
        living = [entity for entity in players if entity.alive]
        hp_fractions = [entity.resources.hp / max(1, entity.resources.max_hp) for entity in living]
        active_kinds: list[str] = []
        if orchestrator is not None:
            active_kinds = sorted(definition.kind.value for definition in orchestrator.active_definitions())
        pressure = float(state.metadata.get("director_pressure", 0.0))
        quests = state.flags.get("quests", {})
        unresolved = 0
        if isinstance(quests, dict):
            unresolved = sum(
                1
                for value in quests.values()
                if isinstance(value, dict) and not bool(value.get("complete", False))
            )
        factions = {
            str(entity.component("faction").get("id"))
            for entity in state.entities.values()
            if entity.component("faction").get("id")
        }
        return DirectorSnapshot(
            simulation_time=state.simulation_time,
            player_count=len(players),
            living_player_count=len(living),
            average_hp_fraction=sum(hp_fractions) / len(hp_fractions) if hp_fractions else 0.0,
            active_scene_kinds=active_kinds,
            recent_pressure=max(0.0, min(1.0, pressure)),
            unresolved_quest_count=unresolved,
            faction_count=len(factions),
        )

    def proposals(
        self,
        state: CampaignState,
        *,
        orchestrator: CampaignOrchestrator | None = None,
        max_results: int = 8,
    ) -> list[DirectorProposal]:
        snapshot = self.observe(state, orchestrator=orchestrator)
        results: list[DirectorProposal] = []
        low_resources = 1.0 - snapshot.average_hp_fraction
        active_combat = SceneKind.ENCOUNTER.value in snapshot.active_scene_kinds

        if snapshot.living_player_count and (low_resources > 0.45 or snapshot.recent_pressure > 0.80):
            utility = 0.55 + max(low_resources * 0.35, (snapshot.recent_pressure - 0.80) * 0.6)
            reasons: list[str] = []
            if low_resources > 0.45:
                reasons.append(f"party average HP is {snapshot.average_hp_fraction:.2f}")
            if snapshot.recent_pressure > 0.80:
                reasons.append(f"recent pressure is high at {snapshot.recent_pressure:.2f}")
            reasons.append("avoid encounter pile-up")
            results.append(
                DirectorProposal(
                    id="director:recovery-window",
                    kind=DirectorProposalKind.DOWNTIME,
                    utility=utility,
                    payload={"intent": "offer_recovery_window", "pressure_delta": -0.25},
                    reasons=reasons,
                    tags={"recovery", "pacing"},
                )
            )

        if snapshot.living_player_count and not active_combat and snapshot.recent_pressure < 0.45:
            utility = 0.48 + (0.45 - snapshot.recent_pressure) * 0.5
            results.append(
                DirectorProposal(
                    id="director:encounter-opportunity",
                    kind=DirectorProposalKind.ENCOUNTER,
                    utility=utility,
                    payload={"intent": "introduce_encounter", "difficulty_bias": "moderate"},
                    reasons=[f"recent pressure is {snapshot.recent_pressure:.2f}", "no encounter scene is active"],
                    tags={"encounter", "tension"},
                )
            )

        if snapshot.unresolved_quest_count == 0:
            results.append(
                DirectorProposal(
                    id="director:quest-hook",
                    kind=DirectorProposalKind.QUEST,
                    utility=0.62,
                    payload={"intent": "offer_quest_hook", "scope": "local"},
                    reasons=["no unresolved quest is currently tracked"],
                    tags={"quest", "agency"},
                )
            )

        if snapshot.faction_count >= 2:
            results.append(
                DirectorProposal(
                    id="director:faction-motion",
                    kind=DirectorProposalKind.FACTION_MOVE,
                    utility=min(0.78, 0.38 + snapshot.faction_count * 0.06),
                    payload={"intent": "advance_faction_goal", "background_only": True},
                    reasons=[f"{snapshot.faction_count} factions can advance independently"],
                    tags={"faction", "living_world"},
                )
            )

        if snapshot.recent_pressure > 0.75:
            results.append(
                DirectorProposal(
                    id="director:decompress",
                    kind=DirectorProposalKind.PACING,
                    utility=0.70 + (snapshot.recent_pressure - 0.75),
                    payload={"intent": "decompress", "pressure_delta": -0.35},
                    reasons=[f"recent pressure is high at {snapshot.recent_pressure:.2f}"],
                    tags={"pacing", "decompression"},
                )
            )

        results.append(
            DirectorProposal(
                id="director:world-motion",
                kind=DirectorProposalKind.WORLD_EVENT,
                utility=0.30 + min(0.25, snapshot.faction_count * 0.03),
                payload={"intent": "advance_background_world", "visible": False},
                reasons=["keep living-world simulation moving without forcing player attention"],
                tags={"world", "background"},
            )
        )
        results.sort(key=lambda value: (-value.utility, value.kind.value, value.id))
        return results[: max(0, max_results)]

    def choose(
        self,
        state: CampaignState,
        *,
        orchestrator: CampaignOrchestrator | None = None,
    ) -> DirectorProposal | None:
        proposals = self.proposals(state, orchestrator=orchestrator, max_results=1)
        return proposals[0] if proposals else None
