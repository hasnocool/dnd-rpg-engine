# src/dnd_rpg_engine/api/hosting.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.hosting.reconnect import ReconnectManager

router = APIRouter(prefix="/api/v1", tags=["production-hosting"])


class ResumeRequest(BaseModel):
    token: str
    observed_event_sequence: int | None = Field(default=None, ge=0)


class ResumeCheckpointRequest(BaseModel):
    token: str
    last_event_sequence: int = Field(ge=0)


@router.get("/hosting/status")
async def hosting_status(request: Request) -> dict[str, Any]:
    store = request.app.state.rpg.store
    status_method = getattr(store, "hosting_status", None)
    if status_method is None:
        campaigns = await store.list_campaigns(limit=10_000)
        return {
            "backend": "sqlite",
            "hosted_campaigns": len(campaigns),
            "active_workers": 0,
            "active_leases": 0,
            "schema_version": 0,
        }
    return await status_method()


@router.post("/campaigns/{campaign_id}/resume-tickets")
async def issue_resume_ticket(
    request: Request,
    campaign_id: str,
    after: int = Query(default=0, ge=0),
    client_id: str | None = Header(default=None, alias="X-RPG-Client-ID"),
) -> dict[str, Any]:
    state = request.app.state.rpg
    await state.get_engine(campaign_id)
    identity = state.require_client(campaign_id, client_id)
    manager = ReconnectManager(state.store)
    ticket = await manager.issue(campaign_id, identity, last_event_sequence=after)
    return ticket.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(
    request: Request,
    campaign_id: str,
    payload: ResumeRequest,
) -> dict[str, Any]:
    state = request.app.state.rpg
    await state.get_engine(campaign_id)
    try:
        session = state.sessions.require(campaign_id)
        manager = ReconnectManager(state.store)
        result, rotated = await manager.resume(
            payload.token,
            session,
            observed_event_sequence=payload.observed_event_sequence,
            rotate=True,
        )
    except (KeyError, PermissionError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    events = await state.store.list_events(
        campaign_id,
        after_sequence=result.replay_after_sequence,
        limit=5000,
    )
    return {
        "client": result.client.model_dump(mode="json"),
        "resume_ticket": rotated.model_dump(mode="json") if rotated is not None else None,
        "replay_after_sequence": result.replay_after_sequence,
        "events": [event.model_dump(mode="json") for event in events],
    }


@router.post("/campaigns/{campaign_id}/resume/checkpoint")
async def checkpoint_resume_ticket(
    request: Request,
    campaign_id: str,
    payload: ResumeCheckpointRequest,
) -> dict[str, int | str]:
    state = request.app.state.rpg
    await state.get_engine(campaign_id)
    manager = ReconnectManager(state.store)
    try:
        await manager.checkpoint(payload.token, payload.last_event_sequence)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"status": "ok", "last_event_sequence": payload.last_event_sequence}


@router.delete("/campaigns/{campaign_id}/resume-tickets/{token}")
async def revoke_resume_ticket(request: Request, campaign_id: str, token: str) -> dict[str, str]:
    state = request.app.state.rpg
    await state.get_engine(campaign_id)
    await ReconnectManager(state.store).revoke(token)
    return {"status": "revoked"}
