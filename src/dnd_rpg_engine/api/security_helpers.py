from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.multiplayer.protocol import ClientIdentity
from dnd_rpg_engine.multiplayer.sessions import CampaignSession
from dnd_rpg_engine.security.models import Permission, Principal, ResourceRef, ScopeType, TenantRole
from dnd_rpg_engine.security.service import IdentityService


def require_principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="authenticated session required")
    return principal


def identity_service(request: Request) -> IdentityService:
    service = getattr(request.app.state, "identity", None)
    if service is None:
        raise HTTPException(status_code=503, detail="identity service is unavailable")
    return service


async def campaign_resource(
    request: Request,
    campaign_id: str,
    *,
    engine: GameEngine | None = None,
) -> ResourceRef:
    service = identity_service(request)
    resource = service.resource_for_scope(ScopeType.CAMPAIGN, campaign_id)
    if resource.owner_user_id or resource.organization_id or resource.workspace_id:
        return resource
    engine = engine or await request.app.state.rpg.get_engine(campaign_id)
    metadata = engine.state.metadata
    return ResourceRef(
        type="campaign",
        id=campaign_id,
        campaign_id=campaign_id,
        owner_user_id=str(metadata.get("owner_id", "")) or None,
        organization_id=str(metadata.get("organization_id", "")) or None,
        workspace_id=str(metadata.get("workspace_id", "")) or None,
    )


def _live_principal(app: Any, campaign_id: str, client: ClientIdentity) -> Principal | None:
    principal = getattr(app.state, "client_principals", {}).get((campaign_id, client.client_id))
    if principal is None or principal.user_id != client.user_id:
        return None
    service: IdentityService = app.state.identity
    session = service.sessions.get(principal.session_id)
    if session is None or not session.active or session.user_id != principal.user_id:
        return None
    return principal


def bind_campaign_client(
    request: Request,
    session: CampaignSession,
    identity: ClientIdentity,
    principal: Principal,
    resource: ResourceRef,
) -> None:
    app = request.app
    if not hasattr(app.state, "client_principals"):
        app.state.client_principals = {}
    app.state.client_principals[(session.campaign_id, identity.client_id)] = principal
    service = identity_service(request)

    def can_manage(client: ClientIdentity) -> bool:
        bound = _live_principal(app, session.campaign_id, client)
        return bool(bound and service.can(bound, Permission.CAMPAIGN_MANAGE, resource))

    def can_control(client: ClientIdentity, actor_id: str) -> bool:
        bound = _live_principal(app, session.campaign_id, client)
        if bound is None:
            return False
        entity = session.engine.state.entities.get(actor_id)
        if entity is None:
            return False
        actor_resource = resource.model_copy(
            update={
                "type": "character",
                "id": actor_id,
                "actor_owner_user_id": entity.owner_id,
            }
        )
        return service.can(bound, Permission.CHARACTER_CONTROL, actor_resource) or service.can(
            bound, Permission.CAMPAIGN_CONTROL, resource
        )

    session.manage_resolver = can_manage
    session.control_resolver = can_control


def transport_role(service: IdentityService, principal: Principal, resource: ResourceRef) -> str:
    roles = service.policy.roles_for(principal, resource, service.memberships_for(principal.user_id))
    if resource.owner_user_id == principal.user_id:
        return "player"
    if roles and roles <= {TenantRole.SPECTATOR}:
        return "spectator"
    return "player"
