from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from dnd_rpg_engine.security.models import Principal


class TokenError(ValueError):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:
        raise TokenError("invalid token encoding") from exc


class SessionTokenService:
    """Small dependency-free HMAC session-token service.

    Tokens are signed capability-free identity assertions. Authorization is
    always resolved from current server-side memberships, so changing a role
    immediately changes what an otherwise-valid token may do.
    """

    def __init__(self, secret: str | bytes, *, issuer: str = "dnd-rpg-engine") -> None:
        raw = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
        if len(raw) < 32:
            raise ValueError("authentication secret must contain at least 32 bytes")
        self._secret = raw
        self.issuer = issuer

    @classmethod
    def ephemeral(cls) -> "SessionTokenService":
        return cls(secrets.token_bytes(48))

    def issue(
        self,
        *,
        user_id: str,
        display_name: str = "",
        ttl_seconds: int = 3600,
        organization_id: str | None = None,
        workspace_id: str | None = None,
        claims: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> tuple[str, Principal]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        sid = session_id or secrets.token_urlsafe(24)
        payload = {
            "iss": self.issuer,
            "sub": user_id,
            "sid": sid,
            "name": display_name,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "org": organization_id,
            "workspace": workspace_id,
            "claims": claims or {},
            "nonce": secrets.token_urlsafe(12),
        }
        header = {"alg": "HS256", "typ": "RPGSESSION", "v": 1}
        encoded_header = _b64encode(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
        encoded_payload = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        body = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = _b64encode(hmac.new(self._secret, body, hashlib.sha256).digest())
        principal = Principal(
            user_id=user_id,
            session_id=sid,
            display_name=display_name,
            issued_at=now,
            expires_at=expires,
            organization_id=organization_id,
            workspace_id=workspace_id,
            claims=claims or {},
        )
        return f"{encoded_header}.{encoded_payload}.{signature}", principal

    def verify(self, token: str) -> Principal:
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenError("invalid session token")
        encoded_header, encoded_payload, encoded_signature = parts
        body = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = hmac.new(self._secret, body, hashlib.sha256).digest()
        actual = _b64decode(encoded_signature)
        if not hmac.compare_digest(expected, actual):
            raise TokenError("invalid session signature")
        try:
            header = json.loads(_b64decode(encoded_header))
            payload = json.loads(_b64decode(encoded_payload))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TokenError("invalid session payload") from exc
        if header.get("alg") != "HS256" or header.get("typ") != "RPGSESSION":
            raise TokenError("unsupported session token")
        if payload.get("iss") != self.issuer:
            raise TokenError("invalid session issuer")
        now = datetime.now(timezone.utc)
        try:
            issued = datetime.fromtimestamp(int(payload["iat"]), timezone.utc)
            expires = datetime.fromtimestamp(int(payload["exp"]), timezone.utc)
            user_id = str(payload["sub"])
            session_id = str(payload["sid"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TokenError("missing session claims") from exc
        if expires <= now:
            raise TokenError("session token expired")
        if issued > now + timedelta(minutes=5):
            raise TokenError("session token issued in the future")
        return Principal(
            user_id=user_id,
            session_id=session_id,
            display_name=str(payload.get("name", "")),
            issued_at=issued,
            expires_at=expires,
            organization_id=payload.get("org"),
            workspace_id=payload.get("workspace"),
            claims=dict(payload.get("claims") or {}),
        )


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
