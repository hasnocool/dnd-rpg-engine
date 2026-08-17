from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dnd_rpg_engine.security.models import (
    AuditRecord,
    Membership,
    Organization,
    Permission,
    Principal,
    ResourceRef,
    ScopeType,
    SessionRecord,
    TenantRole,
    User,
    Workspace,
)
from dnd_rpg_engine.security.policy import AuthorizationDecision, AuthorizationRequest, PolicyEngine
from dnd_rpg_engine.security.tokens import SessionTokenService, TokenError


class IdentityService:
    """Persistent identity, tenancy, session and audit service.

    The service intentionally stores authorization state server-side. Signed
    session tokens identify a user/session but never embed effective roles, so
    revoking a membership takes effect without waiting for token expiry.
    """

    def __init__(
        self,
        tokens: SessionTokenService,
        *,
        policy: PolicyEngine | None = None,
    ) -> None:
        self.tokens = tokens
        self.policy = policy or PolicyEngine()
        self.store: Any | None = None
        self.users: dict[str, User] = {}
        self.organizations: dict[str, Organization] = {}
        self.workspaces: dict[str, Workspace] = {}
        self.memberships: dict[str, Membership] = {}
        self.sessions: dict[str, SessionRecord] = {}
        self.audit_records: dict[str, AuditRecord] = {}
        self._initialized = False

    async def initialize(self, store: Any) -> None:
        if self._initialized and self.store is store:
            return
        self.store = store
        self.users = {key: User.model_validate(value) for key, value in (await store.list_json("identity.user")).items()}
        self.organizations = {
            key: Organization.model_validate(value)
            for key, value in (await store.list_json("identity.organization")).items()
        }
        self.workspaces = {
            key: Workspace.model_validate(value)
            for key, value in (await store.list_json("identity.workspace")).items()
        }
        self.memberships = {
            key: Membership.model_validate(value)
            for key, value in (await store.list_json("identity.membership")).items()
        }
        self.sessions = {
            key: SessionRecord.model_validate(value)
            for key, value in (await store.list_json("identity.session")).items()
        }
        self.audit_records = {
            key: AuditRecord.model_validate(value)
            for key, value in (await store.list_json("identity.audit")).items()
        }
        self._initialized = True

    async def _put(self, namespace: str, key: str, value: Any) -> None:
        if self.store is not None:
            payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
            await self.store.put_json(namespace, key, payload)

    async def ensure_user(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
    ) -> User:
        existing = self.users.get(user_id)
        if existing is not None:
            if display_name and existing.display_name != display_name:
                existing.display_name = display_name
                await self._put("identity.user", existing.id, existing)
            return existing
        user = User(id=user_id, display_name=display_name or user_id, email=email)
        self.users[user.id] = user
        await self._put("identity.user", user.id, user)
        return user

    async def create_organization(self, principal: Principal, name: str) -> Organization:
        organization = Organization(name=name, owner_user_id=principal.user_id)
        self.organizations[organization.id] = organization
        membership = Membership(
            user_id=principal.user_id,
            scope_type=ScopeType.ORGANIZATION,
            scope_id=organization.id,
            role=TenantRole.OWNER,
            granted_by=principal.user_id,
        )
        self.memberships[membership.id] = membership
        await self._put("identity.organization", organization.id, organization)
        await self._put("identity.membership", membership.id, membership)
        await self.audit(principal, "organization.create", "organization", organization.id)
        return organization

    async def create_workspace(self, principal: Principal, organization_id: str, name: str) -> Workspace:
        organization = self.organizations[organization_id]
        self.authorize(
            principal,
            Permission.ORGANIZATION_MANAGE,
            ResourceRef(type="organization", id=organization_id, owner_user_id=organization.owner_user_id),
        )
        workspace = Workspace(organization_id=organization_id, name=name)
        self.workspaces[workspace.id] = workspace
        await self._put("identity.workspace", workspace.id, workspace)
        await self.audit(principal, "workspace.create", "workspace", workspace.id, metadata={"organization_id": organization_id})
        return workspace

    async def grant_membership(
        self,
        principal: Principal,
        *,
        user_id: str,
        scope_type: ScopeType,
        scope_id: str,
        role: TenantRole,
    ) -> Membership:
        resource = self.resource_for_scope(scope_type, scope_id)
        permission = Permission.MEMBERSHIP_MANAGE
        self.authorize(principal, permission, resource)
        if user_id not in self.users:
            raise KeyError("unknown user")
        existing = next(
            (
                value
                for value in self.memberships.values()
                if value.user_id == user_id and value.scope_type is scope_type and value.scope_id == scope_id
            ),
            None,
        )
        membership = existing or Membership(
            user_id=user_id,
            scope_type=scope_type,
            scope_id=scope_id,
            role=role,
            granted_by=principal.user_id,
        )
        membership.role = role
        membership.granted_by = principal.user_id
        self.memberships[membership.id] = membership
        await self._put("identity.membership", membership.id, membership)
        await self.audit(
            principal,
            "membership.grant",
            scope_type.value,
            scope_id,
            metadata={"user_id": user_id, "role": role.value},
        )
        return membership

    async def revoke_membership(self, principal: Principal, membership_id: str) -> None:
        membership = self.memberships[membership_id]
        self.authorize(principal, Permission.MEMBERSHIP_MANAGE, self.resource_for_scope(membership.scope_type, membership.scope_id))
        self.memberships.pop(membership_id, None)
        if self.store is not None:
            await self.store.delete_json("identity.membership", membership_id)
        await self.audit(principal, "membership.revoke", membership.scope_type.value, membership.scope_id, metadata={"user_id": membership.user_id})

    def memberships_for(self, user_id: str) -> list[Membership]:
        return sorted(
            (value for value in self.memberships.values() if value.user_id == user_id),
            key=lambda value: (value.scope_type.value, value.scope_id, value.role.value, value.id),
        )

    def resource_for_scope(self, scope_type: ScopeType, scope_id: str) -> ResourceRef:
        if scope_type is ScopeType.ORGANIZATION:
            organization = self.organizations.get(scope_id)
            return ResourceRef(
                type="organization",
                id=scope_id,
                owner_user_id=organization.owner_user_id if organization else None,
                organization_id=scope_id,
            )
        if scope_type is ScopeType.WORKSPACE:
            workspace = self.workspaces.get(scope_id)
            organization = self.organizations.get(workspace.organization_id) if workspace else None
            return ResourceRef(
                type="workspace",
                id=scope_id,
                owner_user_id=organization.owner_user_id if organization else None,
                organization_id=workspace.organization_id if workspace else None,
                workspace_id=scope_id,
            )
        if scope_type is ScopeType.CAMPAIGN:
            return ResourceRef(type="campaign", id=scope_id, campaign_id=scope_id)
        return ResourceRef(type="project", id=scope_id, project_id=scope_id)

    async def issue_session(
        self,
        user_id: str,
        *,
        ttl_seconds: int = 3600,
        organization_id: str | None = None,
        workspace_id: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, Principal]:
        user = self.users.get(user_id)
        if user is None or user.disabled:
            raise PermissionError("unknown or disabled user")
        token, principal = self.tokens.issue(
            user_id=user.id,
            display_name=user.display_name,
            ttl_seconds=ttl_seconds,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        session = SessionRecord(
            id=principal.session_id,
            user_id=user.id,
            issued_at=principal.issued_at,
            expires_at=principal.expires_at,
            user_agent=user_agent,
        )
        self.sessions[session.id] = session
        await self._put("identity.session", session.id, session)
        return token, principal

    def authenticate(self, token: str) -> Principal:
        principal = self.tokens.verify(token)
        user = self.users.get(principal.user_id)
        if user is None or user.disabled:
            raise TokenError("unknown or disabled user")
        session = self.sessions.get(principal.session_id)
        if session is None or not session.active or session.user_id != principal.user_id:
            raise TokenError("session is revoked or unknown")
        return principal

    async def revoke_session(self, principal: Principal, session_id: str | None = None) -> None:
        target_id = session_id or principal.session_id
        session = self.sessions.get(target_id)
        if session is None:
            return
        if session.user_id != principal.user_id and not self.can(
            principal,
            Permission.MEMBERSHIP_MANAGE,
            ResourceRef(type="user", id=session.user_id),
        ):
            raise PermissionError("cannot revoke another user's session")
        session.revoked_at = datetime.now(timezone.utc)
        await self._put("identity.session", target_id, session)
        await self.audit(principal, "session.revoke", "session", target_id)

    def can(self, principal: Principal, permission: Permission, resource: ResourceRef) -> bool:
        request = AuthorizationRequest(permission=permission, resource=resource)
        return self.policy.decide(principal, request, self.memberships_for(principal.user_id)).allowed

    def authorize(self, principal: Principal, permission: Permission, resource: ResourceRef) -> AuthorizationDecision:
        request = AuthorizationRequest(permission=permission, resource=resource)
        return self.policy.authorize(principal, request, self.memberships_for(principal.user_id))

    async def audit(
        self,
        principal: Principal | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        *,
        allowed: bool = True,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        record = AuditRecord(
            user_id=principal.user_id if principal else None,
            session_id=principal.session_id if principal else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            allowed=allowed,
            reason=reason,
            metadata=metadata or {},
        )
        self.audit_records[record.id] = record
        await self._put("identity.audit", record.id, record)
        return record

    def audit_log(self, *, limit: int = 200) -> list[AuditRecord]:
        return sorted(self.audit_records.values(), key=lambda value: (value.at, value.id), reverse=True)[:limit]
