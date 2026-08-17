from __future__ import annotations

from pydantic import BaseModel, Field

from dnd_rpg_engine.security.models import Membership, Permission, Principal, ResourceRef, TenantRole


ROLE_PERMISSIONS: dict[TenantRole, frozenset[Permission]] = {
    TenantRole.OWNER: frozenset(Permission),
    TenantRole.ADMIN: frozenset(Permission),
    TenantRole.GAME_MASTER: frozenset(
        {
            Permission.CAMPAIGN_CREATE,
            Permission.CAMPAIGN_READ,
            Permission.CAMPAIGN_CONTROL,
            Permission.CAMPAIGN_MANAGE,
            Permission.CHARACTER_CONTROL,
            Permission.STUDIO_READ,
            Permission.SIMULATION_RUN,
            Permission.DIRECTOR_MANAGE,
            Permission.MARKETPLACE_READ,
        }
    ),
    TenantRole.PLAYER: frozenset(
        {
            Permission.CAMPAIGN_READ,
            Permission.CHARACTER_CONTROL,
            Permission.MARKETPLACE_READ,
        }
    ),
    TenantRole.SPECTATOR: frozenset({Permission.CAMPAIGN_READ, Permission.MARKETPLACE_READ}),
    TenantRole.CREATOR: frozenset(
        {
            Permission.CAMPAIGN_CREATE,
            Permission.CAMPAIGN_READ,
            Permission.STUDIO_READ,
            Permission.STUDIO_WRITE,
            Permission.STUDIO_PUBLISH,
            Permission.SIMULATION_RUN,
            Permission.MARKETPLACE_READ,
        }
    ),
    TenantRole.MODERATOR: frozenset(
        {
            Permission.CAMPAIGN_READ,
            Permission.STUDIO_READ,
            Permission.MARKETPLACE_READ,
            Permission.MARKETPLACE_MODERATE,
            Permission.AUDIT_READ,
        }
    ),
}


class AuthorizationRequest(BaseModel):
    permission: Permission
    resource: ResourceRef
    metadata: dict[str, object] = Field(default_factory=dict)


class AuthorizationDecision(BaseModel):
    allowed: bool
    permission: Permission
    roles: set[TenantRole] = Field(default_factory=set)
    reason: str


class PolicyEngine:
    """Deterministic resource-scoped RBAC policy evaluator."""

    def roles_for(
        self,
        principal: Principal,
        resource: ResourceRef,
        memberships: list[Membership],
    ) -> set[TenantRole]:
        roles: set[TenantRole] = set()
        chain = set(resource.scope_chain())
        for membership in memberships:
            if membership.user_id != principal.user_id:
                continue
            if (membership.scope_type, membership.scope_id) in chain:
                roles.add(membership.role)
        if resource.owner_user_id == principal.user_id:
            roles.add(TenantRole.OWNER)
        return roles

    def decide(
        self,
        principal: Principal,
        request: AuthorizationRequest,
        memberships: list[Membership],
    ) -> AuthorizationDecision:
        if principal.expired:
            return AuthorizationDecision(
                allowed=False,
                permission=request.permission,
                reason="authenticated session expired",
            )
        roles = self.roles_for(principal, request.resource, memberships)
        if request.permission is Permission.CHARACTER_CONTROL:
            if request.resource.actor_owner_user_id == principal.user_id:
                return AuthorizationDecision(
                    allowed=True,
                    permission=request.permission,
                    roles=roles,
                    reason="character owner",
                )
        for role in sorted(roles, key=lambda value: value.value):
            if request.permission in ROLE_PERMISSIONS[role]:
                return AuthorizationDecision(
                    allowed=True,
                    permission=request.permission,
                    roles=roles,
                    reason=f"granted by {role.value}",
                )
        return AuthorizationDecision(
            allowed=False,
            permission=request.permission,
            roles=roles,
            reason="permission is not granted in this resource scope",
        )

    def authorize(
        self,
        principal: Principal,
        request: AuthorizationRequest,
        memberships: list[Membership],
    ) -> AuthorizationDecision:
        decision = self.decide(principal, request, memberships)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return decision
