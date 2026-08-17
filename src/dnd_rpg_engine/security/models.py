from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    GAME_MASTER = "game_master"
    PLAYER = "player"
    SPECTATOR = "spectator"
    CREATOR = "creator"
    MODERATOR = "moderator"


class Permission(StrEnum):
    ORGANIZATION_MANAGE = "organization.manage"
    WORKSPACE_MANAGE = "workspace.manage"
    MEMBERSHIP_MANAGE = "membership.manage"
    CAMPAIGN_CREATE = "campaign.create"
    CAMPAIGN_READ = "campaign.read"
    CAMPAIGN_CONTROL = "campaign.control"
    CAMPAIGN_MANAGE = "campaign.manage"
    CHARACTER_CONTROL = "character.control"
    STUDIO_READ = "studio.read"
    STUDIO_WRITE = "studio.write"
    STUDIO_PUBLISH = "studio.publish"
    MARKETPLACE_READ = "marketplace.read"
    MARKETPLACE_MODERATE = "marketplace.moderate"
    AUDIT_READ = "audit.read"
    DISTRIBUTED_MANAGE = "distributed.manage"
    SIMULATION_RUN = "simulation.run"
    DIRECTOR_MANAGE = "director.manage"


class ScopeType(StrEnum):
    ORGANIZATION = "organization"
    WORKSPACE = "workspace"
    CAMPAIGN = "campaign"
    PROJECT = "project"


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    display_name: str
    email: str | None = None
    disabled: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Organization(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    owner_user_id: str
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Workspace(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    name: str
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Membership(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    scope_type: ScopeType
    scope_id: str
    role: TenantRole
    granted_by: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResourceRef(BaseModel):
    type: str
    id: str
    owner_user_id: str | None = None
    organization_id: str | None = None
    workspace_id: str | None = None
    campaign_id: str | None = None
    project_id: str | None = None
    actor_owner_user_id: str | None = None

    def scope_chain(self) -> list[tuple[ScopeType, str]]:
        values: list[tuple[ScopeType, str]] = []
        if self.organization_id:
            values.append((ScopeType.ORGANIZATION, self.organization_id))
        if self.workspace_id:
            values.append((ScopeType.WORKSPACE, self.workspace_id))
        if self.campaign_id:
            values.append((ScopeType.CAMPAIGN, self.campaign_id))
        if self.project_id:
            values.append((ScopeType.PROJECT, self.project_id))
        if not values:
            try:
                values.append((ScopeType(self.type), self.id))
            except ValueError:
                pass
        return values


class Principal(BaseModel):
    user_id: str
    session_id: str
    display_name: str = ""
    issued_at: datetime
    expires_at: datetime
    organization_id: str | None = None
    workspace_id: str | None = None
    claims: dict[str, Any] = Field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return self.expires_at <= utcnow()


class SessionRecord(BaseModel):
    id: str
    user_id: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def active(self) -> bool:
        return self.revoked_at is None and self.expires_at > utcnow()


class AuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    at: datetime = Field(default_factory=utcnow)
    user_id: str | None = None
    session_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    allowed: bool = True
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
