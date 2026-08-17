from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.creator.studio import CreatorStudio
from dnd_rpg_engine.rules.compiler import RuleCompiler, RuleProvenance

router = APIRouter(prefix="/api/v1/studio", tags=["creator-studio-rules"])


class CompileStudioRuleRequest(BaseModel):
    graph: dict[str, Any] | None = None
    save: bool = False


def _studio(request: Request) -> CreatorStudio:
    state = request.app.state.rpg
    return CreatorStudio(state.store, validator=state.validator)


@router.post("/projects/{project_id}/rules/{rule_id}/compile")
async def compile_studio_rule(
    request: Request,
    project_id: str,
    rule_id: str,
    payload: CompileStudioRuleRequest,
) -> dict[str, Any]:
    studio = _studio(request)
    try:
        project = await studio.get_project(project_id)
        document = project.pack.rules[rule_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    graph_raw = dict(payload.graph if payload.graph is not None else document.graph)
    try:
        compiled = RuleCompiler().compile(
            rule_id,
            document.name,
            graph_raw,
            provenance=RuleProvenance(
                pack_id=project.pack.manifest.id,
                pack_version=project.pack.manifest.version,
                source_object_id=rule_id,
                source_revision=project.revision,
            ),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if payload.save:
        document_payload = document.model_dump(mode="json")
        document_payload["graph"] = graph_raw
        project = await studio.upsert(project_id, "rules", rule_id, document_payload)

    return {
        "valid": True,
        "graph_hash": compiled.graph_hash,
        "node_count": len(compiled.nodes),
        "effect_count": len(compiled.effects),
        "capabilities": sorted(compiled.capabilities),
        "compiled": compiled.model_dump(mode="json"),
        "revision": project.revision,
    }
