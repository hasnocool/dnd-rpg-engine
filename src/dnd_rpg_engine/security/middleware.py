from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from dnd_rpg_engine.security.models import Permission, ResourceRef
from dnd_rpg_engine.security.tokens import TokenError

_CAMPAIGN_PATH = re.compile(r"^/api/v1/campaigns/([^/]+)(/.*)?$")
_BLOCKED_SECURE_PATHS = {
    ("POST", "/api/v1/campaigns"),
    ("GET", "/api/v1/campaigns"),
}
_PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static/",
    "/api/v1/auth/bootstrap",
)


class IdentityMiddleware(BaseHTTPMiddleware):
    """Authenticate requests and enforce coarse resource policy.

    Fine-grained actor authorization remains in ``CampaignSession`` where the
    authoritative command and actor ID are available. In required mode the
    insecure legacy campaign create/list/join routes are disabled in favor of
    authenticated secure equivalents.
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
            return JSONResponse(
                {"detail": "use the authenticated /api/v1/secure/campaigns endpoint"},
                status_code=409,
            )
        if self.required and path.endswith("/join") and _CAMPAIGN_PATH.match(path):
            return JSONResponse(
                {"detail": "use the authenticated /api/v1/secure/campaigns/{campaign_id}/join endpoint"},
                status_code=409,
            )

        try:
            await self._authorize_path(request, principal, service)
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
        if path.startswith("/api/v1/auth/") or path.startswith("/api/v1/secure/"):
            return
        if path.startswith("/api/v1/studio"):
            permission = Permission.STUDIO_READ if request.method == "GET" else Permission.STUDIO_WRITE
            if path.endswith("/publish"):
                permission = Permission.STUDIO_PUBLISH
            service.authorize(
                principal,
                permission,
                ResourceRef(type="project", id="studio", project_id="studio"),
            )
            return
        if path == "/api/v1/marketplace/publish":
            service.authorize(
                principal,
                Permission.STUDIO_PUBLISH,
                ResourceRef(type="project", id="marketplace", project_id="studio"),
            )
            return
        match = _CAMPAIGN_PATH.match(path)
        if not match:
            return
        campaign_id, suffix = match.group(1), match.group(2) or ""
        engine = await request.app.state.rpg.get_engine(campaign_id)
        owner_id = str(engine.state.metadata.get("owner_id", "")) or None
        resource = ResourceRef(
            type="campaign",
            id=campaign_id,
            campaign_id=campaign_id,
            owner_user_id=owner_id,
        )
        if request.method == "GET":
            permission = Permission.CAMPAIGN_READ
        elif suffix.startswith("/commands"):
            permission = Permission.CAMPAIGN_CONTROL
        elif suffix.startswith("/characters"):
            permission = Permission.CAMPAIGN_CONTROL
        else:
            permission = Permission.CAMPAIGN_MANAGE
        service.authorize(principal, permission, resource)

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
