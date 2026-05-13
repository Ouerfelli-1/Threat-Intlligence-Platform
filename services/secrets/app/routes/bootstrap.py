"""
Bootstrap endpoint — allows services to fetch credentials without a JWT.
Called during the startup bootstrap dance (before the service has obtained a service JWT).
"""
import logging

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.crypto import decrypt
from app.db import get_session_factory
from app.models import Secret
from app.schemas import BootstrapFetchRequest

log = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["bootstrap"])


@router.post("/bootstrap-fetch")
async def bootstrap_fetch(body: BootstrapFetchRequest, request: Request):
    """
    Validates the service's bootstrap token then returns the requested secret(s).

    Two modes:
    - body.secret_name provided → single-secret mode: returns {"value": "<plaintext>"}
    - body.secret_name absent  → bulk mode (auth only): returns RS256 keypair dict
    """
    from tip_common import ValidationError

    fernet = request.app.state.fernet
    bootstrap_token_key = f"SVC_{body.service_name.upper().replace('-', '_')}_BOOTSTRAP_TOKEN"

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(Secret).where(Secret.name == bootstrap_token_key))
        token_secret = result.scalar_one_or_none()

    if not token_secret:
        # Per-service token not in DB — fall back to the shared SECRETS_BOOTSTRAP_TOKEN.
        # This covers the common case where all services use the shared bootstrap token
        # from the .env during initial startup (before per-service tokens are provisioned).
        from app.settings import get_settings as _gs
        shared_token = _gs().secrets_bootstrap_token
        if shared_token and body.bootstrap_token == shared_token:
            stored_token = body.bootstrap_token  # validated via shared token
        else:
            log.warning("bootstrap_fetch service=%s token_key=%s not found", body.service_name, bootstrap_token_key)
            raise ValidationError("Invalid bootstrap token")
    else:
        stored_token = decrypt(fernet, token_secret.value_encrypted)

    if stored_token != body.bootstrap_token:
        # Per-service token mismatch — also accept the shared SECRETS_BOOTSTRAP_TOKEN
        # so services can bootstrap before per-service token rotation is set up.
        from app.settings import get_settings as _gs
        shared_token = _gs().secrets_bootstrap_token
        if not (shared_token and body.bootstrap_token == shared_token):
            log.warning("bootstrap_fetch service=%s token_mismatch", body.service_name)
            raise ValidationError("Invalid bootstrap token")

    log.info("bootstrap_fetch service=%s secret_name=%s", body.service_name, body.secret_name)

    async with session_factory() as session:
        if body.secret_name:
            result = await session.execute(select(Secret).where(Secret.name == body.secret_name))
            secret = result.scalar_one_or_none()
            value = decrypt(fernet, secret.value_encrypted) if secret else None
            return {"value": value}

        # Bulk mode: return RS256 keypair for the auth service
        result = await session.execute(
            select(Secret).where(Secret.name.in_(["AUTH_RS256_PUBLIC_KEY", "AUTH_RS256_PRIVATE_KEY"]))
        )
        secrets = {s.name: decrypt(fernet, s.value_encrypted) for s in result.scalars().all()}
        return {"secrets": secrets}
