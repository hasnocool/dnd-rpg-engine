from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.api.security_helpers import campaign_resource, identity_service, require_principal
from dnd_rpg_engine.security.models import Permission
from dnd_rpg_engine.simulation import DuelScenario, DuelSimulationCase, ExperimentDefinition, SimulationOutcome

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation-lab"])


class SummarizeRequest(BaseModel):
    definition: ExperimentDefinition
    outcomes: list[SimulationOutcome]


class CampaignDuelRequest(BaseModel):
    left_actor_id: str
    right_actor_id: str
    left_action_id: str = "basic_attack"
    right_action_id: str = "basic_attack"
    iterations: int = Field(default=1000, ge=1, le=100_000)
    base_seed: int = 1
    concurrency: int = Field(default=8, ge=1, le=128)
    max_actions: int = Field(default=1000, ge=1, le=100_000)
    expected_winner: str | None = None
    target_win_rate_min: float | None = Field(default=None, ge=0, le=1)
    target_win_rate_max: float | None = Field(default=None, ge=0, le=1)


@router.post("/summarize")
async def summarize(request: Request, payload: SummarizeRequest) -> dict[str, Any]:
    require_principal(request)
    report = request.app.state.simulation_lab.summarize(payload.definition, payload.outcomes)
    report.findings = request.app.state.simulation_lab.analyzer.analyze(payload.definition, report)
    return report.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/duel")
async def simulate_campaign_duel(
    request: Request,
    campaign_id: str,
    payload: CampaignDuelRequest,
) -> dict[str, Any]:
    principal = require_principal(request)
    resource = await campaign_resource(request, campaign_id)
    try:
        identity_service(request).authorize(principal, Permission.SIMULATION_RUN, resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    engine = await request.app.state.rpg.get_engine(campaign_id)
    try:
        left = engine.state.require_entity(payload.left_actor_id).model_copy(deep=True)
        right = engine.state.require_entity(payload.right_actor_id).model_copy(deep=True)
        left_action = engine.actions.require(payload.left_action_id).model_copy(deep=True)
        right_action = engine.actions.require(payload.right_action_id).model_copy(deep=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    definition = ExperimentDefinition(
        id=f"campaign:{campaign_id}:duel:{left.id}:{right.id}",
        iterations=payload.iterations,
        base_seed=payload.base_seed,
        concurrency=payload.concurrency,
        expected_winner=payload.expected_winner,
        target_win_rate_min=payload.target_win_rate_min,
        target_win_rate_max=payload.target_win_rate_max,
        metadata={"campaign_id": campaign_id, "left_actor_id": left.id, "right_actor_id": right.id},
    )
    case = DuelSimulationCase(
        DuelScenario(
            left=left,
            right=right,
            left_action=left_action,
            right_action=right_action,
            rules=engine.rules.model_copy(deep=True),
            max_actions=payload.max_actions,
        )
    )
    report = await request.app.state.simulation_lab.run(definition, case)
    await identity_service(request).audit(
        principal,
        "simulation.duel",
        "campaign",
        campaign_id,
        metadata={"iterations": payload.iterations, "left": left.id, "right": right.id},
    )
    return report.model_dump(mode="json")
