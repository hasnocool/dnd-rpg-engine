from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dnd_rpg_engine.api.security_helpers import (
    bind_campaign_client,
    campaign_resource,
    identity_service,
    require_principal,
    transport_role,
)
from dnd_rpg_engine.core.models import GameConfig, TimeMode
from dnd_rpg_engine.multiplayer.protocol import ClientIdentity, ClientRole
from dnd_rpg_engine.security.models import Permission, ResourceRef, ScopeType, TenantRole

router = APIRouter(tags=["identity-security"])


class BootstrapRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    ttl_seconds: int = Field(default=3600, ge=60, le=86_400)


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class EnsureUserRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    organization_id: str


class MembershipRequest(BaseModel):
    user_id: str
    scope_type: ScopeType
    scope_id: str
    role: TenantRole


class SecureCampaignRequest(BaseModel):
    name: str = "New Campaign"
    seed: int = 1
    time_mode: TimeMode = TimeMode.HYBRID
    player_decision_timeout_seconds: float | None = Field(default=10.0, gt=0)
    organization_id: str | None = None
    workspace_id: str | None = None

    def config(self) -> GameConfig:
        return GameConfig(
            seed=self.seed,
            time_mode=self.time_mode,
            player_decision_timeout_seconds=self.player_decision_timeout_seconds,
        )


@router.post("/api/v1/auth/bootstrap")
async def bootstrap_session(
    request: Request,
    payload: BootstrapRequest,
    bootstrap_key: str | None = Header(default=None, alias="X-RPG-Bootstrap-Key"),
) -> dict[str, Any]:
    expected = getattr(request.app.state, "bootstrap_key", None)
    if not expected:
        raise HTTPException(status_code=503, detail="bootstrap authentication is disabled")
    if not bootstrap_key or not hmac.compare_digest(bootstrap_key, expected):
        raise HTTPException(status_code=401, detail="invalid bootstrap key")
    service = identity_service(request)
    user = await service.ensure_user(payload.user_id, display_name=payload.display_name, email=payload.email)
    token, principal = await service.issue_session(
        user.id,
        ttl_seconds=payload.ttl_seconds,
        user_agent=request.headers.get("user-agent"),
    )
    await service.audit(principal, "session.bootstrap", "user", user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": principal.expires_at.isoformat(),
        "session_id": principal.session_id,
        "user": user.model_dump(mode="json"),
    }


@router.get("/api/v1/auth/me")
async def auth_me(request: Request) -> dict[str, Any]:
    principal = require_principal(request)
    service = identity_service(request)
    return {
        "principal": principal.model_dump(mode="json"),
        "user": service.users[principal.user_id].model_dump(mode="json"),
        "memberships": [value.model_dump(mode="json") for value in service.memberships_for(principal.user_id)],
    }


@router.post("/api/v1/auth/refresh")
async def refresh_session(request: Request) -> dict[str, Any]:
    principal = require_principal(request)
    service = identity_service(request)
    token, replacement = await service.issue_session(
        principal.user_id,
        ttl_seconds=max(60, int((principal.expires_at - principal.issued_at).total_seconds())),
        organization_id=principal.organization_id,
        workspace_id=principal.workspace_id,
        user_agent=request.headers.get("user-agent"),
    )
    await service.revoke_session(principal)
    await service.audit(replacement, "session.refresh", "session", replacement.session_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": replacement.expires_at.isoformat(),
        "session_id": replacement.session_id,
    }


@router.post("/api/v1/auth/logout", status_code=204)
async def logout(request: Request) -> None:
    principal = require_principal(request)
    await identity_service(request).revoke_session(principal)


@router.post("/api/v1/secure/organizations")
async def create_organization(request: Request, payload: CreateOrganizationRequest) -> dict[str, Any]:
    principal = require_principal(request)
    organization = await identity_service(request).create_organization(principal, payload.name)
    return organization.model_dump(mode="json")


@router.get("/api/v1/secure/organizations")
async def list_organizations(request: Request) -> list[dict[str, Any]]:
    principal = require_principal(request)
    service = identity_service(request)
    output: list[dict[str, Any]] = []
    for organization in service.organizations.values():
        resource = service.resource_for_scope(ScopeType.ORGANIZATION, organization.id)
        roles = service.policy.roles_for(principal, resource, service.memberships_for(principal.user_id))
        if roles:
            output.append({**organization.model_dump(mode="json"), "roles": sorted(role.value for role in roles)})
    return sorted(output, key=lambda value: (value["name"], value["id"]))


@router.post("/api/v1/secure/organizations/{organization_id}/workspaces")
async def create_workspace(
    request: Request,
    organization_id: str,
    payload: CreateWorkspaceRequest,
) -> dict[str, Any]:
    principal = require_principal(request)
    try:
        workspace = await identity_service(request).create_workspace(principal, organization_id, payload.name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="organization not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return workspace.model_dump(mode="json")


@router.get("/api/v1/secure/organizations/{organization_id}/workspaces")
async def list_workspaces(request: Request, organization_id: str) -> list[dict[str, Any]]:
    principal = require_principal(request)
    service = identity_service(request)
    organization = service.organizations.get(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="organization not found")
    resource = service.resource_for_scope(ScopeType.ORGANIZATION, organization_id)
    if not service.policy.roles_for(principal, resource, service.memberships_for(principal.user_id)):
        raise HTTPException(status_code=403, detail="organization membership required")
    return [
        value.model_dump(mode="json")
        for value in sorted(service.workspaces.values(), key=lambda item: (item.name, item.id))
        if value.organization_id == organization_id
    ]


@router.post("/api/v1/secure/users")
async def ensure_tenant_user(request: Request, payload: EnsureUserRequest) -> dict[str, Any]:
    principal = require_principal(request)
    service = identity_service(request)
    resource = service.resource_for_scope(ScopeType.ORGANIZATION, payload.organization_id)
    try:
        service.authorize(principal, Permission.MEMBERSHIP_MANAGE, resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    user = await service.ensure_user(payload.user_id, display_name=payload.display_name, email=payload.email)
    return user.model_dump(mode="json")


@router.post("/api/v1/secure/memberships")
async def grant_membership(request: Request, payload: MembershipRequest) -> dict[str, Any]:
    principal = require_principal(request)
    try:
        membership = await identity_service(request).grant_membership(
            principal,
            user_id=payload.user_id,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            role=payload.role,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return membership.model_dump(mode="json")


@router.delete("/api/v1/secure/memberships/{membership_id}", status_code=204)
async def revoke_membership(request: Request, membership_id: str) -> None:
    principal = require_principal(request)
    try:
        await identity_service(request).revoke_membership(principal, membership_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="membership not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/api/v1/secure/campaigns")
async def create_secure_campaign(request: Request, payload: SecureCampaignRequest) -> dict[str, Any]:
    principal = require_principal(request)
    service = identity_service(request)
    state = request.app.state.rpg

    organization_id = payload.organization_id
    workspace_id = payload.workspace_id
    if workspace_id:
        workspace = service.workspaces.get(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="workspace not found")
        if organization_id and workspace.organization_id != organization_id:
            raise HTTPException(status_code=422, detail="workspace does not belong to organization")
        organization_id = workspace.organization_id
        parent = service.resource_for_scope(ScopeType.WORKSPACE, workspace_id)
        try:
            service.authorize(principal, Permission.CAMPAIGN_CREATE, parent)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    elif organization_id:
        if organization_id not in service.organizations:
            raise HTTPException(status_code=404, detail="organization not found")
        parent = service.resource_for_scope(ScopeType.ORGANIZATION, organization_id)
        try:
            service.authorize(principal, Permission.CAMPAIGN_CREATE, parent)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    engine_class = request.app.state.platform_engine_class
    engine = await engine_class.create(payload.name, config=payload.config(), store=state.store, seed=payload.seed)
    engine.state.metadata.update(
        {
            "owner_id": principal.user_id,
            "organization_id": organization_id,
            "workspace_id": workspace_id,
            "platform_version": getattr(request.app, "version", ""),
        }
    )
    await engine.save()
    state.engines[engine.state.id] = engine
    session = await state.sessions.host(engine.state.id, engine, principal.user_id)
    owner = ClientIdentity(
        user_id=principal.user_id,
        display_name=principal.display_name or principal.user_id,
        role=ClientRole.OWNER,
        authenticated=True,
        session_id=principal.session_id,
    )
    session.join(owner)
    resource = await service.register_resource(
        principal,
        ResourceRef(
            type="campaign",
            id=engine.state.id,
            owner_user_id=principal.user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            campaign_id=engine.state.id,
        ),
    )
    bind_campaign_client(request, session, owner, principal, resource)
    metadata = {
        "owner_id": principal.user_id,
        "public": False,
        "organization_id": organization_id,
        "workspace_id": workspace_id,
    }
    if hasattr(state.store, "host_campaign"):
        await state.store.host_campaign(engine.state.id, principal.user_id, public=False, metadata=metadata)
    else:
        await state.store.put_json("hosted_campaign", engine.state.id, metadata)
    await state.ensure_realtime(engine.state.id, engine)
    await state.ensure_broadcast(engine.state.id, engine)
    await service.audit(principal, "campaign.create", "campaign", engine.state.id, metadata=metadata)
    return {"campaign_id": engine.state.id, "owner_client_id": owner.client_id, **engine.state_payload()}


@router.get("/api/v1/secure/campaigns")
async def list_secure_campaigns(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    principal = require_principal(request)
    service = identity_service(request)
    rows = await request.app.state.rpg.store.list_campaigns(limit=1000)
    by_id = {str(row["id"]): row for row in rows}
    output: list[dict[str, Any]] = []
    for key, resource in service.resources.items():
        if not key.startswith("campaign:"):
            continue
        if service.can(principal, Permission.CAMPAIGN_READ, resource):
            row = by_id.get(resource.id, {"id": resource.id})
            output.append(
                {
                    **row,
                    "organization_id": resource.organization_id,
                    "workspace_id": resource.workspace_id,
                    "owner_user_id": resource.owner_user_id,
                }
            )
    output.sort(key=lambda value: str(value.get("updated_at", "")), reverse=True)
    return output[:limit]


@router.post("/api/v1/secure/campaigns/{campaign_id}/join")
async def join_secure_campaign(request: Request, campaign_id: str) -> dict[str, Any]:
    principal = require_principal(request)
    service = identity_service(request)
    state = request.app.state.rpg
    engine = await state.get_engine(campaign_id)
    resource = await campaign_resource(request, campaign_id, engine=engine)
    if resource.owner_user_id == principal.user_id and service.resource_key(ScopeType.CAMPAIGN, campaign_id) not in service.resources:
        resource = await service.register_resource(principal, resource)
    try:
        service.authorize(principal, Permission.CAMPAIGN_READ, resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    session = state.sessions.require(campaign_id)
    role_value = transport_role(service, principal, resource)
    identity = ClientIdentity(
        user_id=principal.user_id,
        display_name=principal.display_name or principal.user_id,
        role=ClientRole(role_value),
        authenticated=True,
        session_id=principal.session_id,
    )
    session.join(identity)
    bind_campaign_client(request, session, identity, principal, resource)
    await service.audit(principal, "campaign.join", "campaign", campaign_id, metadata={"client_id": identity.client_id})
    return identity.model_dump(mode="json")


@router.get("/api/v1/secure/audit")
async def audit_log(
    request: Request,
    organization_id: str,
    limit: int = Query(default=200, ge=1, le=2000),
) -> list[dict[str, Any]]:
    principal = require_principal(request)
    service = identity_service(request)
    resource = service.resource_for_scope(ScopeType.ORGANIZATION, organization_id)
    try:
        service.authorize(principal, Permission.AUDIT_READ, resource)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [value.model_dump(mode="json") for value in service.audit_log(limit=limit)]
