import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import current_user, require_permission
from tip_db import get_session

from app.crypto import decrypt, encrypt
from app.db import get_session_factory
from app.models import AccessLog, Secret
from app.schemas import SecretCreate, SecretMeta, SecretPreview, SecretRotate, SecretValue

router = APIRouter(prefix="/secrets", tags=["secrets"])


async def _session_dep():
    # FastAPI's dependency injection treats async generators specially: it
    # iterates exactly once, yielding the session into the endpoint. Wrapping
    # tip_db.get_session inside another async generator preserves that
    # contract (returning the generator object directly would land an
    # async_generator inside the endpoint).
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


def _actor(request: Request) -> str:
    user = getattr(request.state, "auth", None)
    return getattr(user, "subject", "unknown") if user else "unknown"


async def _log(session: AsyncSession, name: str, actor: str, action: str, ip: str | None) -> None:
    entry = AccessLog(
        id=uuid.uuid4(),
        secret_name=name,
        actor=actor,
        action=action,
        at=datetime.now(timezone.utc),
        source_ip=ip,
    )
    session.add(entry)


@router.get("", response_model=list[SecretMeta], dependencies=[Depends(require_permission("secrets:read"))])
async def list_secrets(session: SessionDep):
    result = await session.execute(select(Secret).order_by(Secret.name))
    return [
        SecretMeta(name=s.name, version=s.version, metadata=s.metadata_, created_at=s.created_at, updated_at=s.updated_at)
        for s in result.scalars().all()
    ]


@router.get(
    "/{name}/preview",
    response_model=SecretPreview,
    dependencies=[Depends(require_permission("secrets:read"))],
)
async def preview_secret(name: str, request: Request, session: SessionDep):
    """Admin-safe preview of a secret. Returns first 8 chars + bullets, never
    the full value. Lets admins confirm which key is currently configured
    without exposing the material itself to the browser or its caches."""
    from tip_common import NotFoundError

    result = await session.execute(select(Secret).where(Secret.name == name))
    secret = result.scalar_one_or_none()
    if not secret:
        raise NotFoundError(f"Secret '{name}' not found")

    fernet = request.app.state.fernet
    raw = decrypt(fernet, secret.value_encrypted) or ""
    visible = raw[:8] if len(raw) >= 8 else raw
    masked = f"{visible}{'•' * 12}" if visible else "(empty)"

    await _log(session, name, _actor(request), "preview", request.client.host if request.client else None)
    await session.commit()

    return SecretPreview(
        name=secret.name,
        version=secret.version,
        metadata=secret.metadata_,
        created_at=secret.created_at,
        updated_at=secret.updated_at,
        preview=masked,
        length=len(raw),
    )


@router.get("/{name}", response_model=SecretValue, dependencies=[Depends(require_permission("secrets:read"))])
async def get_secret(name: str, request: Request, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Secret).where(Secret.name == name))
    secret = result.scalar_one_or_none()
    if not secret:
        raise NotFoundError(f"Secret '{name}' not found")

    fernet = request.app.state.fernet
    value = decrypt(fernet, secret.value_encrypted)
    await _log(session, name, _actor(request), "read", request.client.host if request.client else None)
    await session.commit()
    return SecretValue(name=secret.name, version=secret.version, metadata=secret.metadata_, created_at=secret.created_at, updated_at=secret.updated_at, value=value)


@router.post("", response_model=SecretMeta, status_code=201, dependencies=[Depends(require_permission("secrets:write"))])
async def create_or_update_secret(body: SecretCreate, request: Request, session: SessionDep):
    fernet = request.app.state.fernet
    encrypted = encrypt(fernet, body.value)
    now = datetime.now(timezone.utc)

    result = await session.execute(select(Secret).where(Secret.name == body.name))
    existing = result.scalar_one_or_none()

    if existing:
        existing.value_encrypted = encrypted
        existing.version += 1
        existing.metadata_ = body.metadata
        existing.updated_at = now
        action = "write"
    else:
        existing = Secret(name=body.name, value_encrypted=encrypted, version=1, metadata_=body.metadata, created_at=now, updated_at=now)
        session.add(existing)
        action = "write"

    await _log(session, body.name, _actor(request), action, request.client.host if request.client else None)
    await session.commit()
    return SecretMeta(name=existing.name, version=existing.version, metadata=existing.metadata_, created_at=existing.created_at, updated_at=existing.updated_at)


@router.post("/{name}/rotate", response_model=SecretMeta, dependencies=[Depends(require_permission("secrets:write"))])
async def rotate_secret(name: str, body: SecretRotate, request: Request, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Secret).where(Secret.name == name))
    secret = result.scalar_one_or_none()
    if not secret:
        raise NotFoundError(f"Secret '{name}' not found")

    fernet = request.app.state.fernet
    secret.value_encrypted = encrypt(fernet, body.new_value)
    secret.version += 1
    secret.updated_at = datetime.now(timezone.utc)
    await _log(session, name, _actor(request), "rotate", request.client.host if request.client else None)
    await session.commit()
    return SecretMeta(name=secret.name, version=secret.version, metadata=secret.metadata_, created_at=secret.created_at, updated_at=secret.updated_at)


@router.delete("/{name}", status_code=204, dependencies=[Depends(require_permission("secrets:write"))])
async def delete_secret(name: str, request: Request, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Secret).where(Secret.name == name))
    secret = result.scalar_one_or_none()
    if not secret:
        raise NotFoundError(f"Secret '{name}' not found")
    await _log(session, name, _actor(request), "delete", request.client.host if request.client else None)
    await session.delete(secret)
    await session.commit()
