from __future__ import annotations

from datetime import timedelta

import pytest

from dnd_rpg_engine.security import (
    AuthorizationRequest,
    IdentityService,
    Permission,
    ResourceRef,
    ScopeType,
    SessionTokenService,
    TenantRole,
)
from dnd_rpg_engine.security.tokens import TokenError


class MemoryStore:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    async def list_json(self, namespace: str):
        return dict(self.rows.get(namespace, {}))

    async def put_json(self, namespace: str, key: str, value: object) -> None:
        self.rows.setdefault(namespace, {})[key] = value

    async def delete_json(self, namespace: str, key: str) -> None:
        self.rows.setdefault(namespace, {}).pop(key, None)


@pytest.mark.asyncio
async def test_identity_rbac_scope_and_session_revocation() -> None:
    service = IdentityService(SessionTokenService("x" * 48))
    store = MemoryStore()
    await service.initialize(store)
    owner = await service.ensure_user("owner", display_name="Owner")
    player = await service.ensure_user("player", display_name="Player")
    owner_token, owner_principal = await service.issue_session(owner.id)
    player_token, player_principal = await service.issue_session(player.id)
    organization = await service.create_organization(owner_principal, "Guild")
    workspace = await service.create_workspace(owner_principal, organization.id, "World")
    await service.grant_membership(
        owner_principal,
        user_id=player.id,
        scope_type=ScopeType.CAMPAIGN,
        scope_id="campaign-1",
        role=TenantRole.PLAYER,
    )

    campaign = ResourceRef(type="campaign", id="campaign-1", campaign_id="campaign-1")
    assert service.can(player_principal, Permission.CAMPAIGN_READ, campaign)
    assert not service.can(player_principal, Permission.CAMPAIGN_MANAGE, campaign)
    owned_actor = ResourceRef(
        type="character",
        id="hero",
        campaign_id="campaign-1",
        actor_owner_user_id="player",
    )
    assert service.can(player_principal, Permission.CHARACTER_CONTROL, owned_actor)

    org_resource = ResourceRef(
        type="organization",
        id=organization.id,
        organization_id=organization.id,
        owner_user_id="owner",
    )
    assert service.can(owner_principal, Permission.ORGANIZATION_MANAGE, org_resource)
    workspace_resource = ResourceRef(
        type="workspace",
        id=workspace.id,
        organization_id=organization.id,
        workspace_id=workspace.id,
        owner_user_id="owner",
    )
    assert service.can(owner_principal, Permission.WORKSPACE_MANAGE, workspace_resource)

    assert service.authenticate(owner_token).user_id == "owner"
    assert service.authenticate(player_token).user_id == "player"
    await service.revoke_session(player_principal)
    with pytest.raises(TokenError):
        service.authenticate(player_token)


@pytest.mark.asyncio
async def test_role_changes_take_effect_without_reissuing_token() -> None:
    service = IdentityService(SessionTokenService("y" * 48))
    await service.initialize(MemoryStore())
    await service.ensure_user("admin")
    await service.ensure_user("member")
    _, admin = await service.issue_session("admin")
    token, member = await service.issue_session("member")
    org = await service.create_organization(admin, "Org")
    membership = await service.grant_membership(
        admin,
        user_id="member",
        scope_type=ScopeType.ORGANIZATION,
        scope_id=org.id,
        role=TenantRole.CREATOR,
    )
    project = ResourceRef(type="project", id="studio", organization_id=org.id, project_id="studio")
    assert service.can(member, Permission.STUDIO_WRITE, project)
    membership.role = TenantRole.SPECTATOR
    await service._put("identity.membership", membership.id, membership)
    assert service.authenticate(token).user_id == "member"
    assert not service.can(member, Permission.STUDIO_WRITE, project)
