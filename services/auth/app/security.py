import hashlib
import json
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from jwt.algorithms import RSAAlgorithm

_ph = PasswordHasher()
_private_key = None
_public_key = None
_public_pem: str = ""


def init_keys(private_pem: str, public_pem: str) -> None:
    global _private_key, _public_key, _public_pem
    _private_key = load_pem_private_key(private_pem.encode(), password=None)
    _public_key = load_pem_public_key(public_pem.encode())
    _public_pem = public_pem


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_refresh_token() -> str:
    return _secrets.token_urlsafe(48)


def create_access_token(user_id: UUID, username: str, role_name: str, permissions: list[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"user:{user_id}",
        "kind": "user",
        "username": username,
        "role": role_name,
        "perms": permissions,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, _private_key, algorithm="RS256")


def create_service_token(service_name: str, permissions: list[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"service:{service_name}",
        "kind": "service",
        "perms": permissions,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
    }
    return jwt.encode(payload, _private_key, algorithm="RS256")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _public_key, algorithms=["RS256"])


def get_jwks() -> dict:
    jwk = json.loads(RSAAlgorithm.to_jwk(_public_key))
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    jwk["kid"] = "tip-rs256-1"
    return {"keys": [jwk]}
