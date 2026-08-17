from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ClientRole(StrEnum):
    OWNER = "owner"
    PLAYER = "player"
    SPECTATOR = "spectator"


class ClientIdentity(BaseModel):
    client_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    display_name: str
    role: ClientRole = ClientRole.PLAYER
    actor_ids: set[str] = Field(default_factory=set)
    authenticated: bool = False
    session_id: str | None = None


class ClientEnvelope(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    client_sequence: int = Field(default=0, ge=0)


class ServerEnvelope(BaseModel):
    sequence: int
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
