"""Cognito JWT authentication for administrator-only write operations.

No client secrets are deployed or accepted. Read-only endpoints remain public.
"""
import os
import re
from functools import lru_cache

import jwt
from fastapi import Header

from .errors import ApiProblem

ADMIN_GROUP = "envirosync-admin"


def uploads_enabled():
    return os.getenv("ENVIROSYNC_UPLOADS_ENABLED", "false").lower() == "true"


@lru_cache(maxsize=4)
def jwks_client(issuer):
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=5, lifespan=300)


def require_admin(authorization: str | None = Header(default=None)):
    if not uploads_enabled():
        raise ApiProblem(503, "UPLOADS_DISABLED", "Administrator uploads have not been enabled.")

    user_pool = os.getenv("ENVIROSYNC_COGNITO_USER_POOL_ID", "").strip()
    client_id = os.getenv("ENVIROSYNC_COGNITO_CLIENT_ID", "").strip()
    region = os.getenv("INDIA_REGION", "ap-south-1")
    if not re.fullmatch(r"[a-z]{2}-[a-z]+-\d_[A-Za-z0-9]+", user_pool) or not client_id or region != "ap-south-1":
        raise ApiProblem(503, "AUTH_NOT_CONFIGURED", "Administrator authentication is not configured.")

    if not authorization or not authorization.startswith("Bearer "):
        raise ApiProblem(401, "AUTH_REQUIRED", "Sign in as an EnviroSync administrator.")
    token = authorization[7:].strip()
    if len(token) > 8192 or not token:
        raise ApiProblem(401, "INVALID_TOKEN", "Invalid administrator access token.")

    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool}"
    try:
        key = jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False, "require": ["exp", "iat", "iss", "sub", "client_id", "token_use"]},
            leeway=30,
        )
    except (jwt.PyJWTError, ValueError, OSError) as exc:
        raise ApiProblem(401, "INVALID_TOKEN", "Invalid or expired administrator access token.") from exc

    if claims.get("token_use") != "access" or claims.get("client_id") != client_id:
        raise ApiProblem(401, "INVALID_TOKEN", "A valid Cognito access token is required.")
    groups = claims.get("cognito:groups", [])
    if not isinstance(groups, list) or ADMIN_GROUP not in groups:
        raise ApiProblem(403, "ADMIN_REQUIRED", "Only EnviroSync administrators can upload datasets.")
    return claims
