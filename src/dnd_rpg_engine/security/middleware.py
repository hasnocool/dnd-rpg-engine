from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from dnd_rpg_engine.security.models import Permission, ResourceRef, ScopeType
from dnd_rpg_engine.security.tokens import TokenError

_CAMPAIGN_PATH = re.compile(r"^/api/v1/campaigns/([^/]+)(/.*)?$")
_BLOCKED_SECURE_PATHS = {
    ("POST", "/api/v1/campaigns"),
    ("GET", "/api/v1/campaigns"),
    ("POST", "/api/v1/creator/instantiate"),
    ("POST", "/api/v1/marketplace/publish"),
}
_PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static/",
    "/api/v1/auth/bootstrap",
)
_FINE_GRAINED_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/secure/",
    "/api/v1/studio",
    "/api/v1/reliable/",
    "/api/v1/distributed/",
    "/api/v1/packages/",
    "/api/v1/simulation/",
    "/api/v1/director/",
)


class IdentityMiddleware(BaseHTTPMiddleware):
    """Authenticate HTTP requests and close legacy authorization bypasses.

    Fine-grained policy stays in the resource-aware routers and
    ``CampaignSession``. In required mode, older routes that accept caller-
    supplied ownership or transport identity are disabled rather than being
    allowed to undermine the authenticated API.
    """

    def __init__(self, app: Any, *, required: bool = False) -> None:
        super().__init__(app)
        self.required = required

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if self._public(path):
            return await call_next(request)
        service = getattr(request.app.state, "identity", None)
        if service is None:
            return await call_next(request)
        if not service._initialized and hasattr(request.app.state, "rpg"):
            await service.initialize(request.app.state.rpg.store)

        token = self._bearer(request.headers.get("authorization"))
        principal = None
        if token:
            try:
                principal = service.authenticate(token)
            except TokenError as exc:
                return JSONResponse({"detail": str(exc)}, status_code=401)
        if principal is None and self.required:
            return JSONResponse({"detail": "authenticated session required"}, status_code=401)
        request.state.principal = principal
        if principal is None:
            return await call_next(request)

        if self.required and (request.method, path) in _BLOCKED_SECURE_PATHS:
            destination = "/api/v1/secure/campaigns" if "campaign" in path else "/api/v1/studio"
            return JSONResponse(
                {"detail": f"legacy mutation disabled in authenticated mode; use {destination}"},
                status_code=409,
            )
        match = _CAMPAIGN_PATH.match(path)
        if self.required and match:
            suffix = match.group(2) or ""
            if suffix.startswith("/join"):
                return JSONResponse(
                    {"detail": "use /api/v1/secure/campaigns/{campaign_id}/join"},
                    status_code=409,
                )
            if suffix.startswith("/commands"):
                return JSONResponse(
                    {"detail": "use /api/v1/reliable/campaigns/{campaign_id}/commands"},
                    status_code=409,
                )

        try:
            await self._authorize_path(request, principal, service)
            await self._verify_transport_binding(request, principal)
        except PermissionError as exc:
            await service.audit(
                principal,
                "http.denied",
                "http",
                path,
                allowed=False,
                reason=str(exc),
                metadata={"method": request.method},
            )
            return JSONResponse({"detail": str(exc)}, status_code=403)
        return await call_next(request)

    async def _authorize_path(self, request: Request, principal: Any, service: Any) -> None:
        path = request.url.path
        if path.startswith(_FINE_GRAINED_PREFIXES):
            return
        match = _CAMPAIGN_PATH.match(path)
        if not match:
            return
        campaign_id, suffix = match.group(1), match.group(2) or ""
        engine = await request.app.state.rpg.get_engine(campaign_id)
        resource = service.resource_for_scope(ScopeType.CAMPAIGN, campaign_id)
        if not resource.owner_user_id and not resource.organization_id and not resource.workspace_id:
            metadata = engine.state.metadata
            resource = ResourceRef(
                type="campaign",
                id=campaign_id,
                campaign_id=campaign_id,
                owner_user_id=str(metadata.get("owner_id", "")) or None,
                organization_id=str(metadata.get("organization_id", "")) or None,
                workspace_id=str(metadata.get("workspace_id", "")) or None,
            )
        if request.method == "GET":
            permission = Permission.CAMPAIGN_READ
        elif suffix.startswith("/characters"):
            permission = Permission.CAMPAIGN_CONTROL
        else:
            permission = Permission.CAMPAIGN_MANAGE
        service.authorize(principal, permission, resource)

    async def _verify_transport_binding(self, request: Request, principal: Any) -> None:
        match = _CAMPAIGN_PATH.match(request.url.path)
        if not match:
            return
        client_id = request.headers.get("X-RPG-Client-ID")
        if not client_id:
            return
        campaign_id = match.group(1)
        try:
            client = request.app.state.rpg.sessions.require(campaign_id).require_client(client_id)
        except (KeyError, PermissionError) as exc:
            raise PermissionError("unknown campaign client") from exc
        if client.user_id != principal.user_id:
            raise PermissionError("campaign client belongs to a different user")
        if client.session_id and client.session_id != principal.session_id:
            raise PermissionError("campaign client belongs to a different authenticated session")

    @staticmethod
    def _public(path: str) -> bool:
        return path in {"/", "/creator"} or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)

    @staticmethod
    def _bearer(value: str | None) -> str | None:
        if not value:
            return None
        scheme, _, token = value.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        return token.strip()
