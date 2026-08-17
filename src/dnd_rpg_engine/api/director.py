from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.ai.director import CampaignDirector, StoryThread
from dnd_rpg_engine.api.security_helpers import campaign_resource, identity_service, require_principal
from dnd_rpg_engine.security.models import Permission

router = APIRouter(prefix="/api/v1/director", tags=["campaign-director"])


class ThreadRequest(BaseModel):
    thread: StoryThread


class ObserveRequest(BaseModel):
    after_sequence: int = Field(default=0, ge=0)
    limit: int = Field(default=500, ge=1, le=5000)


class ProposeRequest(BaseModel):
    after_sequence: int | None = Field(default=None, ge=0)
    event_limit: int = Field(default=500, ge=1, le=5000)
    limit: int = Field(default=3, ge=1, le=20)


class AttachCommandRequest(BaseModel):
    command: dict[str, Any]


class ApproveRequest(BaseModel):
    client_id: str


async def _authorize(request: Request, campaign_id: str):
    principal = require_principal(request)
    resource = await campaign_resource(request, campaign_id)
    try:
        identity_service(request).authorize(principal, Permission.DIRECTOR_MANAGE, resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return principal


def _director(request: Request, campaign_id: str) -> CampaignDirector:
    return request.app.state.directors.setdefault(campaign_id, CampaignDirector())


@router.get("/campaigns/{campaign_id}")
async def director_state(request: Request, campaign_id: str) -> dict[str, Any]:
    await _authorize(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    director = _director(request, campaign_id)
    director.hydrate(engine.state)
    return {
        "state": director.state_for(engine.state).model_dump(mode="json"),
        "proposals": [
            value.model_dump(mode="json")
            for value in sorted(director.proposals.values(), key=lambda item: (item.sequence, item.id), reverse=True)
        ],
        "provider_context": director.provider_context(engine.state),
    }


@router.post("/campaigns/{campaign_id}/threads")
async def add_thread(request: Request, campaign_id: str, payload: ThreadRequest) -> dict[str, Any]:
    principal = await _authorize(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    director = _director(request, campaign_id)
    thread = director.add_thread(engine.state, payload.thread)
    await engine.save()
    await identity_service(request).audit(
        principal,
        "director.thread.add",
        "campaign",
        campaign_id,
        metadata={"thread_id": thread.id},
    )
    return thread.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/observe")
async def observe_events(request: Request, campaign_id: str, payload: ObserveRequest) -> dict[str, Any]:
    await _authorize(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    events = await request.app.state.rpg.store.list_events(
        campaign_id,
        after_sequence=payload.after_sequence,
        limit=payload.limit,
    )
    director = _director(request, campaign_id)
    state = director.observe(engine.state, events)
    await engine.save()
    return {
        "observed": len(events),
        "last_sequence": events[-1].sequence if events else payload.after_sequence,
        "state": state.model_dump(mode="json"),
    }


@router.post("/campaigns/{campaign_id}/proposals")
async def propose(request: Request, campaign_id: str, payload: ProposeRequest) -> dict[str, Any]:
    principal = await _authorize(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    director = _director(request, campaign_id)
    observed = 0
    if payload.after_sequence is not None:
        events = await request.app.state.rpg.store.list_events(
            campaign_id,
            after_sequence=payload.after_sequence,
            limit=payload.event_limit,
        )
        director.observe(engine.state, events)
        observed = len(events)
    proposals = director.propose(engine.state, limit=payload.limit)
    await engine.save()
    await identity_service(request).audit(
        principal,
        "director.propose",
        "campaign",
        campaign_id,
        metadata={"proposal_ids": [value.id for value in proposals], "observed": observed},
    )
    return {
        "observed": observed,
        "state": director.state_for(engine.state).model_dump(mode="json"),
        "proposals": [value.model_dump(mode="json") for value in proposals],
    }


@router.put("/campaigns/{campaign_id}/proposals/{proposal_id}/command")
async def attach_command(
    request: Request,
    campaign_id: str,
    proposal_id: str,
    payload: AttachCommandRequest,
) -> dict[str, Any]:
    await _authorize(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    director = _director(request, campaign_id)
    try:
        proposal = director.attach_command(proposal_id, payload.command, campaign=engine.state)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await engine.save()
    return proposal.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/proposals/{proposal_id}/approve")
async def approve_proposal(
    request: Request,
    campaign_id: str,
    proposal_id: str,
    payload: ApproveRequest,
) -> dict[str, Any]:
    principal = await _authorize(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    session = request.app.state.rpg.sessions.require(campaign_id)
    try:
        client = session.require_client(payload.client_id)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="unknown campaign client") from exc
    if client.user_id != principal.user_id or (client.session_id and client.session_id != principal.session_id):
        raise HTTPException(status_code=403, detail="campaign client belongs to a different authenticated session")
    director = _director(request, campaign_id)
    try:
        command = director.approve(proposal_id, campaign=engine.state)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if command is None:
        await engine.save()
        return {"proposal": director.proposal(proposal_id).model_dump(mode="json"), "dispatched": False}
    try:
        result = await session.dispatch(payload.client_id, command)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, KeyError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    director.observe(engine.state, result.events)
    await engine.save()
    await identity_service(request).audit(
        principal,
        "director.approve",
        "campaign",
        campaign_id,
        metadata={"proposal_id": proposal_id, "command_id": command.command_id},
    )
    return {
        "proposal": director.proposal(proposal_id).model_dump(mode="json"),
        "dispatched": True,
        "result": {
            "version": result.version,
            "simulation_time": result.simulation_time,
            "events": [event.model_dump(mode="json") for event in result.events],
        },
    }


@router.post("/campaigns/{campaign_id}/proposals/{proposal_id}/reject")
async def reject_proposal(request: Request, campaign_id: str, proposal_id: str) -> dict[str, Any]:
    principal = await _authorize(request, campaign_id)
    engine = await request.app.state.rpg.get_engine(campaign_id)
    director = _director(request, campaign_id)
    try:
        proposal = director.reject(proposal_id, campaign=engine.state)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await engine.save()
    await identity_service(request).audit(
        principal,
        "director.reject",
        "campaign",
        campaign_id,
        metadata={"proposal_id": proposal_id},
    )
    return proposal.model_dump(mode="json")
