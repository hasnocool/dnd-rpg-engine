from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_rpg_engine.campaign.models import CampaignPhase, CampaignRuntimeState, CampaignStepResult

if TYPE_CHECKING:
    from dnd_rpg_engine.core.engine import GameEngine
    from dnd_rpg_engine.rulesets.srd_5_2_1.runtime import SRDRuntimeCatalog


class CampaignRunner:
    """Connects exploration, travel, encounters, rests, quests and advancement."""

    METADATA_KEY = "campaign_runner"

    def __init__(self, engine: "GameEngine") -> None:
        self.engine = engine
        self.catalog: "SRDRuntimeCatalog | None" = None

    def bind_catalog(self, catalog: "SRDRuntimeCatalog | None") -> None:
        self.catalog = catalog

    def state(self) -> CampaignRuntimeState:
        return CampaignRuntimeState.model_validate(self.engine.state.metadata.get(self.METADATA_KEY, {}))

    def save(self, state: CampaignRuntimeState) -> None:
        self.engine.state.metadata[self.METADATA_KEY] = state.model_dump(mode="json")

    def configure_party(self, actor_ids: set[str], *, map_id: str | None = None, node_id: str | None = None) -> CampaignRuntimeState:
        for actor_id in actor_ids:
            self.engine.state.require_entity(actor_id)
        state = self.state()
        state.party_actor_ids = set(actor_ids)
        state.current_map_id = map_id or state.current_map_id
        state.current_node_id = node_id or state.current_node_id
        self.save(state)
        return state

    async def travel(self, actor_id: str, map_id: str, destination_node_id: str, pace: str = "normal") -> CampaignStepResult:
        state = self.state()
        world_map = self.engine.maps.require(map_id)
        actor = self.engine.state.require_entity(actor_id)
        start = actor.position.node_id or state.current_node_id
        if start is None:
            raise ValueError("actor has no current map node")
        edge_time: float | None = None
        for node, travel_time in world_map.neighbors(start):
            if node.id == destination_node_id:
                edge_time = travel_time
                break
        if edge_time is None:
            raise ValueError("destination is not directly reachable from current node")
        multiplier = {"slow": 1.25, "normal": 1.0, "fast": 0.75}[pace]
        minutes = edge_time * 60.0 * multiplier
        before = len(self.engine._recent_events)
        state.phase = CampaignPhase.TRAVEL
        self.save(state)
        await self.engine._advance_world_minutes(minutes)
        destination = world_map.nodes[destination_node_id]
        for member_id in (state.party_actor_ids or {actor_id}):
            member = self.engine.state.require_entity(member_id)
            member.position.area_id = map_id
            member.position.node_id = destination.id
            member.position.x, member.position.y, member.position.z = destination.x, destination.y, destination.z
            self.engine.exploration.visit(member.id, destination.id)
            await self.engine._emit("location.visited", actor_id=member.id, target_id=destination.id, payload={"map_id": map_id, "pace": pace})
        state.current_map_id = map_id
        state.current_node_id = destination.id
        state.phase = CampaignPhase.EXPLORATION
        self.save(state)
        return CampaignStepResult(
            phase=state.phase,
            world_minutes=self.engine.world.clock.total_minutes,
            events=[event.model_dump(mode="json") for event in self.engine._recent_events[before:]],
            suggested_actions=["explore", "interact", "rest", "seek_encounter"],
        )

    async def start_budgeted_encounter(self, party_levels: list[int], *, difficulty: str = "moderate", query: str = "") -> CampaignStepResult:
        if self.catalog is None:
            raise RuntimeError("SRD catalog is required for budgeted encounter generation")
        state = self.state()
        candidate = await self.catalog.encounter_candidate(party_levels, difficulty=difficulty, query=query)
        created: list[str] = []
        for index, monster_id in enumerate(candidate.monster_ids):
            entity = await self.catalog.monster_entity(monster_id, entity_id=f"{monster_id}-{index+1}")
            await self.engine.add_entity(entity)
            created.append(entity.id)
        participants = sorted(state.party_actor_ids) + created
        encounter = await self.engine.start_encounter(participants)
        state.phase = CampaignPhase.ENCOUNTER
        state.active_encounter_id = str(encounter["encounter_id"])
        self.save(state)
        return CampaignStepResult(
            phase=state.phase,
            world_minutes=self.engine.world.clock.total_minutes,
            encounter_id=state.active_encounter_id,
            suggested_actions=["query_legal_actions", "command", "end_encounter"],
        )

    async def finish_encounter(self, *, award_xp: bool = True) -> CampaignStepResult:
        state = self.state()
        if not state.active_encounter_id:
            raise ValueError("no active campaign-runner encounter")
        encounter = self.engine.combat.encounters[state.active_encounter_id]
        defeated_xp = 0
        for entity_id in encounter.participants:
            entity = self.engine.state.entities.get(entity_id)
            if entity and entity.kind.value == "creature" and not entity.alive:
                defeated_xp += int(entity.component("srd").get("xp") or 0)
        await self.engine.end_encounter(state.active_encounter_id)
        if award_xp and defeated_xp and state.party_actor_ids:
            share = defeated_xp // len(state.party_actor_ids)
            for actor_id in state.party_actor_ids:
                entity = self.engine.state.require_entity(actor_id)
                if self.engine.characters.has_character(entity):
                    gained = await self.engine.characters.award_xp(entity, share)
                    await self.engine._emit("character.xp_awarded", actor_id=actor_id, payload={"xp": share, "levels_gained": gained})
        state.phase = CampaignPhase.EXPLORATION
        state.active_encounter_id = None
        self.save(state)
        return CampaignStepResult(
            phase=state.phase,
            world_minutes=self.engine.world.clock.total_minutes,
            suggested_actions=["travel", "rest", "quest", "dialogue"],
        )
