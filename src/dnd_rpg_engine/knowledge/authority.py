from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.ai.intelligence import PerceptionSnapshot
from dnd_rpg_engine.core.models import CampaignState, Entity


class KnowledgeFact(BaseModel):
    id: str
    value: Any
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    learned_at: float = Field(ge=0.0)
    source: str = "observation"
    tags: set[str] = Field(default_factory=set)
    expires_at: float | None = None


class ActorKnowledge(BaseModel):
    actor_id: str
    known_entity_ids: set[str] = Field(default_factory=set)
    last_observed_at: dict[str, float] = Field(default_factory=dict)
    entity_snapshots: dict[str, dict[str, Any]] = Field(default_factory=dict)
    facts: dict[str, KnowledgeFact] = Field(default_factory=dict)


class KnowledgeView(BaseModel):
    campaign_id: str
    actor_id: str
    simulation_time: float
    active_map_id: str | None = None
    entities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    facts: dict[str, KnowledgeFact] = Field(default_factory=dict)


class KnowledgeAuthority:
    """Track what each actor is allowed to know about authoritative truth."""

    component_name = "knowledge"

    def knowledge_for(self, actor: Entity) -> ActorKnowledge:
        raw = actor.component(self.component_name)
        if not raw:
            knowledge = ActorKnowledge(actor_id=actor.id, known_entity_ids={actor.id})
            actor.components[self.component_name] = knowledge.model_dump(mode="json")
            return knowledge
        knowledge = ActorKnowledge.model_validate(raw)
        knowledge.known_entity_ids.add(actor.id)
        return knowledge

    def store(self, actor: Entity, knowledge: ActorKnowledge) -> None:
        actor.components[self.component_name] = knowledge.model_dump(mode="json")

    def reveal_entity(
        self,
        actor: Entity,
        entity_id: str,
        *,
        now: float,
        entity: Entity | None = None,
    ) -> ActorKnowledge:
        knowledge = self.knowledge_for(actor)
        knowledge.known_entity_ids.add(entity_id)
        knowledge.last_observed_at[entity_id] = now
        if entity is not None:
            knowledge.entity_snapshots[entity_id] = self._remembered_entity(entity)
        self.store(actor, knowledge)
        return knowledge

    def conceal_entity(self, actor: Entity, entity_id: str, *, forget: bool = False) -> ActorKnowledge:
        knowledge = self.knowledge_for(actor)
        if forget and entity_id != actor.id:
            knowledge.known_entity_ids.discard(entity_id)
            knowledge.last_observed_at.pop(entity_id, None)
            knowledge.entity_snapshots.pop(entity_id, None)
        self.store(actor, knowledge)
        return knowledge

    def reveal_fact(
        self,
        actor: Entity,
        fact_id: str,
        value: Any,
        *,
        now: float,
        confidence: float = 1.0,
        source: str = "observation",
        tags: set[str] | None = None,
        expires_at: float | None = None,
    ) -> KnowledgeFact:
        knowledge = self.knowledge_for(actor)
        fact = KnowledgeFact(
            id=fact_id,
            value=value,
            confidence=confidence,
            learned_at=now,
            source=source,
            tags=set(tags or set()),
            expires_at=expires_at,
        )
        knowledge.facts[fact_id] = fact
        self.store(actor, knowledge)
        return fact

    def expire(self, actor: Entity, *, now: float) -> list[str]:
        knowledge = self.knowledge_for(actor)
        expired = sorted(
            fact_id
            for fact_id, fact in knowledge.facts.items()
            if fact.expires_at is not None and fact.expires_at <= now
        )
        for fact_id in expired:
            knowledge.facts.pop(fact_id, None)
        if expired:
            self.store(actor, knowledge)
        return expired

    def ingest_perception(
        self,
        actor: Entity,
        snapshot: PerceptionSnapshot,
        state: CampaignState,
    ) -> ActorKnowledge:
        knowledge = self.knowledge_for(actor)
        for observation in snapshot.observations:
            if not observation.visible:
                continue
            knowledge.known_entity_ids.add(observation.entity_id)
            knowledge.last_observed_at[observation.entity_id] = snapshot.simulation_time
            entity = state.entities.get(observation.entity_id)
            if entity is not None:
                knowledge.entity_snapshots[entity.id] = self._remembered_entity(entity)
                fact_id = f"entity:{entity.id}:alive"
                knowledge.facts[fact_id] = KnowledgeFact(
                    id=fact_id,
                    value=entity.alive,
                    learned_at=snapshot.simulation_time,
                    source="perception",
                    tags={"entity", "status"},
                )
        self.store(actor, knowledge)
        return knowledge

    def view_for(
        self,
        actor: Entity,
        state: CampaignState,
        *,
        include_stale_entities: bool = True,
    ) -> KnowledgeView:
        self.expire(actor, now=state.simulation_time)
        knowledge = self.knowledge_for(actor)
        entities: dict[str, dict[str, Any]] = {actor.id: actor.model_dump(mode="json")}
        for entity_id in sorted(knowledge.known_entity_ids - {actor.id}):
            remembered = knowledge.entity_snapshots.get(entity_id)
            if remembered is None:
                if include_stale_entities:
                    entities[entity_id] = {"id": entity_id, "known": True, "details_known": False}
                continue
            observed_at = knowledge.last_observed_at.get(entity_id)
            if not include_stale_entities and (observed_at is None or observed_at < state.simulation_time):
                continue
            entities[entity_id] = dict(remembered)
        return KnowledgeView(
            campaign_id=state.id,
            actor_id=actor.id,
            simulation_time=state.simulation_time,
            active_map_id=state.active_map_id,
            entities=entities,
            facts={key: value for key, value in sorted(knowledge.facts.items())},
        )

    @classmethod
    def _remembered_entity(cls, entity: Entity) -> dict[str, Any]:
        payload = entity.model_dump(mode="json")
        payload["components"] = cls._public_components(payload.get("components", {}))
        return payload

    @staticmethod
    def _public_components(components: dict[str, Any]) -> dict[str, Any]:
        public_names = {"appearance", "faction", "movement", "public", "status"}
        return {
            key: value
            for key, value in sorted(components.items())
            if key in public_names
        }
