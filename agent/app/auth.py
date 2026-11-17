"""Who is calling? Verifies the Supabase JWT sent by the frontend.

The frontend sends `Authorization: Bearer <access_token>`. We check the
signature, expiry and audience, then use the token's `sub` (the user's id).

Supports both Supabase signing styles:
- legacy shared secret (HS256)        -> SUPABASE_JWT_SECRET
- new asymmetric keys (ES256 / RS256) -> public keys from the project's JWKS URL
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

AUDIENCE = "authenticated"
DEV_SECRET_FALLBACK = "slaybus-dev-only-secret-change-me-0123456789"

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None = None


def _hs_secret() -> str:
    s = get_settings()
    if s.supabase_jwt_secret:
        return s.supabase_jwt_secret
    if s.dev_auth:
        return DEV_SECRET_FALLBACK
    return ""


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = get_settings().supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True)


def decode_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e

    alg = header.get("alg")
    try:
        if alg == "HS256":
            secret = _hs_secret()
            if not secret:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "HS256 token but SUPABASE_JWT_SECRET is not set")
            return jwt.decode(token, secret, algorithms=["HS256"], audience=AUDIENCE)
        if alg in ("ES256", "RS256"):
            if not get_settings().supabase_url:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "SUPABASE_URL is not set")
            key = _jwks_client().get_signing_key_from_jwt(token).key
            return jwt.decode(token, key, algorithms=[alg], audience=AUDIENCE)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please log in again") from e
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Unsupported token algorithm: {alg}")


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    claims = decode_token(creds.credentials)
    sub = claims.get("sub")
    try:
        uuid.UUID(str(sub))
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has no valid user id") from e
    return CurrentUser(id=str(sub), email=claims.get("email"))


def mint_dev_token(user_id: str, email: str, ttl_seconds: int = 7 * 24 * 3600) -> str:
    """Only used by POST /dev/token when DEV_AUTH=true."""
    now = int(time.time())
    claims = {"sub": user_id, "email": email, "aud": AUDIENCE, "role": "authenticated", "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(claims, _hs_secret(), algorithm="HS256")
