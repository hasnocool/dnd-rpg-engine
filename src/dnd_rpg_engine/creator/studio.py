# src/dnd_rpg_engine/creator/studio.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from dnd_rpg_engine.adventure.maps import AreaEdge, AreaNode, WorldMap
from dnd_rpg_engine.adventure.quests import QuestDefinition
from dnd_rpg_engine.creator.content import (
    CampaignTemplate,
    ContentPack,
    ContentValidator,
    CreatureTemplate,
    ModManifest,
    RuleDocument,
)
from dnd_rpg_engine.tactical.spells import SpellDefinition


class JsonStore(Protocol):
    async def put_json(self, namespace: str, key: str, value: Any) -> None: ...
    async def get_json(self, namespace: str, key: str) -> Any | None: ...


class StudioSection(StrEnum):
    CAMPAIGNS = "campaigns"
    CREATURES = "creatures"
    MAPS = "maps"
    RULES = "rules"
    SPELLS = "spells"
    QUESTS = "quests"


_SECTION_MODELS: dict[StudioSection, type[BaseModel]] = {
    StudioSection.CAMPAIGNS: CampaignTemplate,
    StudioSection.CREATURES: CreatureTemplate,
    StudioSection.MAPS: WorldMap,
    StudioSection.RULES: RuleDocument,
    StudioSection.SPELLS: SpellDefinition,
    StudioSection.QUESTS: QuestDefinition,
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
    """Persistent typed editing service for the browser Creator Studio."""

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
        model = _SECTION_MODELS[parsed_section]
        normalized = {**payload, "id": object_id}
        value = model.model_validate(normalized)
        section_map = getattr(project.pack, parsed_section.value)
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
