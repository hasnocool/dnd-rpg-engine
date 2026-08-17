from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from dnd_rpg_engine.campaign.runner import CampaignRunner
    from dnd_rpg_engine.core.engine import GameEngine


@dataclass(slots=True)
class DirectorSuggestion:
    kind: str
    reason: str
    payload: dict[str, object]


class DirectorPolicy(Protocol):
    async def suggest(self, engine: "GameEngine") -> DirectorSuggestion: ...


class DeterministicDirectorPolicy:
    """Rules-only fallback AI GM policy; proposes but never mutates truth."""

    async def suggest(self, engine: "GameEngine") -> DirectorSuggestion:
        runner = engine.campaign_runner.state()
        if runner.active_encounter_id:
            return DirectorSuggestion("continue_encounter", "an encounter is active", {"encounter_id": runner.active_encounter_id})
        if runner.current_node_id is None:
            return DirectorSuggestion("establish_location", "the party has no current campaign location", {})
        injured = [
            entity.id for entity in engine.state.entities.values()
            if entity.id in runner.party_actor_ids and entity.resources.hp < entity.resources.max_hp // 2
        ]
        if injured:
            return DirectorSuggestion("rest", "party health is low", {"actor_ids": injured, "rest_kind": "short"})
        return DirectorSuggestion("explore", "no urgent encounter or recovery need", {"node_id": runner.current_node_id})


class CampaignDirector:
    """AI orchestration boundary. Suggestions require authoritative commands to execute."""

    def __init__(self, engine: "GameEngine", policy: DirectorPolicy | None = None) -> None:
        self.engine = engine
        self.policy = policy or DeterministicDirectorPolicy()

    async def suggest(self) -> DirectorSuggestion:
        return await self.policy.suggest(self.engine)

    async def suggest_encounter(self, party_levels: list[int], *, difficulty: str = "moderate", query: str = "") -> DirectorSuggestion:
        catalog = self.engine.campaign_runner.catalog
        if catalog is None:
            return DirectorSuggestion("encounter_unavailable", "no SRD runtime catalog is bound", {})
        candidate = await catalog.encounter_candidate(party_levels, difficulty=difficulty, query=query)
        return DirectorSuggestion(
            "encounter_candidate",
            f"candidate fits the {difficulty} XP budget",
            candidate.model_dump(mode="json"),
        )

    def npc_intent(self, entity_id: str) -> DirectorSuggestion:
        entity = self.engine.state.require_entity(entity_id)
        profile = self.engine.npcs.get(entity_id)
        if profile is None:
            return DirectorSuggestion("idle", "no NPC profile is registered", {"entity_id": entity_id})
        disposition = entity.component("social").get("disposition", "neutral")
        if disposition == "hostile":
            kind = "avoid_or_confront"
        elif disposition == "friendly":
            kind = "assist_or_converse"
        else:
            kind = "observe_or_converse"
        return DirectorSuggestion(
            kind,
            "derived from authoritative NPC profile and social state",
            {
                "entity_id": entity_id,
                "role": profile.role,
                "knowledge_tags": sorted(profile.knowledge_tags),
                "personality_id": profile.personality_id,
                "faction_id": profile.faction_id,
            },
        )

    def adapt_after_events(self, event_types: list[str]) -> dict[str, int]:
        runtime = self.engine.state.metadata.setdefault("director_runtime", {"pressure": 0, "social_momentum": 0})
        for event_type in event_types:
            if event_type.startswith("combat."):
                runtime["pressure"] = max(0, int(runtime.get("pressure", 0)) + (1 if event_type == "combat.entity_defeated" else 0))
            if event_type.startswith("dialogue.") or event_type.startswith("quest."):
                runtime["social_momentum"] = int(runtime.get("social_momentum", 0)) + 1
        return {"pressure": int(runtime.get("pressure", 0)), "social_momentum": int(runtime.get("social_momentum", 0))}
