from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security import decode_token
from app.settings import get_settings

_bearer = HTTPBearer(auto_error=False)
settings = get_settings()


def _get_token_payload(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if settings.disable_auth:
        return {"kind": "user", "role": "admin", "perms": ["*"], "sub": "user:00000000-0000-0000-0000-000000000000", "username": "dev"}
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        return decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    payload = _get_token_payload(credentials)
    if payload.get("kind") != "user" or payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return payload


def get_current_user_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    return _get_token_payload(credentials)
