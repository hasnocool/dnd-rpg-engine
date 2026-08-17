# src/dnd_rpg_engine/creator/studio.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from dnd_rpg_engine.adventure.dialogue import DialogueGraph
from dnd_rpg_engine.adventure.maps import AreaEdge, AreaNode, WorldMap
from dnd_rpg_engine.adventure.npcs import NPCProfile
from dnd_rpg_engine.adventure.quests import QuestDefinition
from dnd_rpg_engine.adventure.shops import Shop
from dnd_rpg_engine.ai.encounters import EncounterTemplate
from dnd_rpg_engine.ai.personalities import Personality
from dnd_rpg_engine.campaign.orchestrator import SceneDefinition
from dnd_rpg_engine.creator.content import (
    CampaignTemplate,
    ContentPack,
    ContentValidator,
    CreatureTemplate,
    ModManifest,
    RuleDocument,
)
from dnd_rpg_engine.living.dynamic_events import DynamicEventDefinition
from dnd_rpg_engine.living.factions import Faction
from dnd_rpg_engine.living.schedules import NPCSchedule
from dnd_rpg_engine.tactical.actions import ActionDefinition
from dnd_rpg_engine.tactical.conditions import ConditionDefinition
from dnd_rpg_engine.tactical.items import ItemDefinition
from dnd_rpg_engine.tactical.spells import SpellDefinition


class JsonStore(Protocol):
    async def put_json(self, namespace: str, key: str, value: Any) -> None: ...
    async def get_json(self, namespace: str, key: str) -> Any | None: ...


class StudioSection(StrEnum):
    CAMPAIGNS = "campaigns"
    SCENES = "scenes"
    MAPS = "maps"
    CREATURES = "creatures"
    NPCS = "npcs"
    PERSONALITIES = "personalities"
    ENCOUNTERS = "encounters"
    ACTIONS = "actions"
    CONDITIONS = "conditions"
    ITEMS = "items"
    SPELLS = "spells"
    DIALOGUES = "dialogues"
    QUESTS = "quests"
    SHOPS = "shops"
    FACTIONS = "factions"
    SCHEDULES = "schedules"
    DYNAMIC_EVENTS = "dynamic_events"
    RULES = "rules"
    RULES_DATA = "rules_data"
    ASSETS = "assets"


_SECTION_MODELS: dict[StudioSection, type[BaseModel]] = {
    StudioSection.CAMPAIGNS: CampaignTemplate,
    StudioSection.SCENES: SceneDefinition,
    StudioSection.MAPS: WorldMap,
    StudioSection.CREATURES: CreatureTemplate,
    StudioSection.NPCS: NPCProfile,
    StudioSection.PERSONALITIES: Personality,
    StudioSection.ENCOUNTERS: EncounterTemplate,
    StudioSection.ACTIONS: ActionDefinition,
    StudioSection.CONDITIONS: ConditionDefinition,
    StudioSection.ITEMS: ItemDefinition,
    StudioSection.SPELLS: SpellDefinition,
    StudioSection.DIALOGUES: DialogueGraph,
    StudioSection.QUESTS: QuestDefinition,
    StudioSection.SHOPS: Shop,
    StudioSection.FACTIONS: Faction,
    StudioSection.SCHEDULES: NPCSchedule,
    StudioSection.DYNAMIC_EVENTS: DynamicEventDefinition,
    StudioSection.RULES: RuleDocument,
}


class StudioProject(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    pack: ContentPack
    revision: int = Field(default=0, ge=0)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StudioValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    content_hash: str
    revision: int


class CreatorStudio:
    """Persistent typed editing service for every ContentPack authoring section."""

    project_namespace = "studio.project"
    revision_namespace = "studio.revision"

    def __init__(self, store: JsonStore, *, validator: ContentValidator | None = None) -> None:
        self.store = store
        self.validator = validator or ContentValidator()

    async def create_project(
        self,
        *,
        name: str,
        manifest: ModManifest | dict[str, Any],
    ) -> StudioProject:
        parsed_manifest = manifest if isinstance(manifest, ModManifest) else ModManifest.model_validate(manifest)
        project = StudioProject(name=name, pack=ContentPack(manifest=parsed_manifest))
        await self._persist(project, snapshot=True)
        return project

    async def get_project(self, project_id: str) -> StudioProject:
        raw = await self.store.get_json(self.project_namespace, project_id)
        if raw is None:
            raise KeyError(f"unknown studio project: {project_id}")
        return StudioProject.model_validate(raw)

    async def replace_pack(self, project_id: str, pack: ContentPack | dict[str, Any]) -> StudioProject:
        project = await self.get_project(project_id)
        project.pack = pack if isinstance(pack, ContentPack) else ContentPack.model_validate(pack)
        return await self._commit(project)

    async def update_manifest(self, project_id: str, manifest: ModManifest | dict[str, Any]) -> StudioProject:
        project = await self.get_project(project_id)
        project.pack.manifest = manifest if isinstance(manifest, ModManifest) else ModManifest.model_validate(manifest)
        project.name = project.pack.manifest.name
        return await self._commit(project)

    async def upsert(
        self,
        project_id: str,
        section: StudioSection | str,
        object_id: str,
        payload: dict[str, Any],
    ) -> StudioProject:
        project = await self.get_project(project_id)
        parsed_section = StudioSection(section)
        section_map = getattr(project.pack, parsed_section.value)
        if parsed_section is StudioSection.ASSETS:
            value = payload.get("value", payload.get("path", payload.get("uri")))
            if not isinstance(value, str) or not value.strip():
                raise ValueError("asset payload requires non-empty value/path/uri")
            section_map[object_id] = value
            return await self._commit(project)
        if parsed_section is StudioSection.RULES_DATA:
            section_map[object_id] = payload
            return await self._commit(project)
        model = _SECTION_MODELS[parsed_section]
        id_field = "entity_id" if parsed_section is StudioSection.NPCS else "id"
        normalized = {**payload, id_field: object_id}
        value = model.model_validate(normalized)
        section_map[object_id] = value
        return await self._commit(project)

    async def delete(self, project_id: str, section: StudioSection | str, object_id: str) -> StudioProject:
        project = await self.get_project(project_id)
        parsed_section = StudioSection(section)
        section_map = getattr(project.pack, parsed_section.value)
        if object_id not in section_map:
            raise KeyError(f"unknown {parsed_section.value} object: {object_id}")
        section_map.pop(object_id)
        return await self._commit(project)

    async def add_map_node(self, project_id: str, map_id: str, node: AreaNode | dict[str, Any]) -> StudioProject:
        project = await self.get_project(project_id)
        world_map = self._require_map(project, map_id)
        parsed = node if isinstance(node, AreaNode) else AreaNode.model_validate(node)
        if parsed.id in world_map.nodes:
            raise ValueError("map node already exists")
        world_map.nodes[parsed.id] = parsed
        return await self._commit(project)

    async def move_map_node(
        self,
        project_id: str,
        map_id: str,
        node_id: str,
        *,
        x: float,
        y: float,
        z: float | None = None,
    ) -> StudioProject:
        project = await self.get_project(project_id)
        world_map = self._require_map(project, map_id)
        try:
            node = world_map.nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"unknown map node: {node_id}") from exc
        node.x = x
        node.y = y
        if z is not None:
            node.z = z
        return await self._commit(project)

    async def connect_map_nodes(
        self,
        project_id: str,
        map_id: str,
        edge: AreaEdge | dict[str, Any],
    ) -> StudioProject:
        project = await self.get_project(project_id)
        world_map = self._require_map(project, map_id)
        parsed = edge if isinstance(edge, AreaEdge) else AreaEdge.model_validate(edge)
        if parsed.source not in world_map.nodes or parsed.target not in world_map.nodes:
            raise ValueError("map edge endpoints must exist")
        duplicate = any(
            existing.source == parsed.source
            and existing.target == parsed.target
            and existing.bidirectional == parsed.bidirectional
            for existing in world_map.edges
        )
        if not duplicate:
            world_map.edges.append(parsed)
        return await self._commit(project)

    async def disconnect_map_nodes(
        self,
        project_id: str,
        map_id: str,
        *,
        source: str,
        target: str,
    ) -> StudioProject:
        project = await self.get_project(project_id)
        world_map = self._require_map(project, map_id)
        before = len(world_map.edges)
        world_map.edges = [
            edge
            for edge in world_map.edges
            if not (
                (edge.source == source and edge.target == target)
                or (edge.bidirectional and edge.source == target and edge.target == source)
            )
        ]
        if len(world_map.edges) == before:
            raise KeyError("map edge not found")
        return await self._commit(project)

    async def validate(self, project_id: str) -> StudioValidation:
        project = await self.get_project(project_id)
        errors = self.validator.validate(project.pack)
        return StudioValidation(
            valid=not errors,
            errors=errors,
            content_hash=project.pack.content_hash(),
            revision=project.revision,
        )

    async def revision(self, project_id: str, revision: int) -> StudioProject:
        raw = await self.store.get_json(self.revision_namespace, f"{project_id}:{revision:08d}")
        if raw is None:
            raise KeyError("studio revision not found")
        return StudioProject.model_validate(raw)

    async def restore_revision(self, project_id: str, revision: int) -> StudioProject:
        historical = await self.revision(project_id, revision)
        current = await self.get_project(project_id)
        current.pack = historical.pack.model_copy(deep=True)
        return await self._commit(current)

    async def export_pack(self, project_id: str) -> ContentPack:
        project = await self.get_project(project_id)
        errors = self.validator.validate(project.pack)
        if errors:
            raise ValueError("cannot export invalid content pack: " + "; ".join(errors))
        return project.pack.model_copy(deep=True)

    async def _commit(self, project: StudioProject) -> StudioProject:
        project.revision += 1
        project.updated_at = datetime.now(timezone.utc).isoformat()
        await self._persist(project, snapshot=True)
        return project

    async def _persist(self, project: StudioProject, *, snapshot: bool) -> None:
        payload = project.model_dump(mode="json")
        await self.store.put_json(self.project_namespace, project.id, payload)
        if snapshot:
            await self.store.put_json(
                self.revision_namespace,
                f"{project.id}:{project.revision:08d}",
                payload,
            )

    @staticmethod
    def _require_map(project: StudioProject, map_id: str) -> WorldMap:
        try:
            return project.pack.maps[map_id]
        except KeyError as exc:
            raise KeyError(f"unknown map: {map_id}") from exc
