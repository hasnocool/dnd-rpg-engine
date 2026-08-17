from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


@dataclass(slots=True)
class TokenClaims:
    campaign_id: str
    client_id: str
    user_id: str
    role: str
    exp: int


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def mint_token(secret: str, *, campaign_id: str, client_id: str, user_id: str, role: str, ttl_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"campaign_id": campaign_id, "client_id": client_id, "user_id": user_id, "role": role, "exp": int(time.time()) + ttl_seconds}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def verify_token(secret: str, token: str) -> TokenClaims:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected_sig), sig_b64):
        raise ValueError("invalid token signature")
    payload = json.loads(_b64url_decode(payload_b64))
    if int(payload["exp"]) < int(time.time()):
        raise ValueError("token expired")
    return TokenClaims(**payload)
