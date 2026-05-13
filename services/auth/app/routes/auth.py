import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session_factory
from app.deps import get_current_user_payload
from app.models import AuditLog, Session, ServiceAccount, User
from app.schemas import (
    LoginRequest,
    MeOut,
    RefreshRequest,
    ServiceLoginRequest,
    ServiceTokenResponse,
    TokenResponse,
)
from app.security import (
    create_access_token,
    create_service_token,
    generate_refresh_token,
    hash_token,
    verify_password,
)

router = APIRouter(tags=["auth"])


async def _get_session():
    async with get_session_factory()() as s:
        yield s


SessionDep = Annotated[AsyncSession, Depends(_get_session)]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, session: SessionDep):
    result = await session.execute(
        select(User).options(selectinload(User.role)).where(User.username == body.username, User.active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    perms = list(user.role.permissions) + list(user.supplementary_permissions)
    access_token = create_access_token(user.id, user.username, user.role.name, perms)
    refresh_raw = generate_refresh_token()

    db_session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        user_agent=request.headers.get("User-Agent"),
        ip=_client_ip(request),
    )
    session.add(db_session)

    await session.execute(
        update(User).where(User.id == user.id).values(last_login_at=datetime.now(timezone.utc))
    )

    session.add(AuditLog(id=uuid.uuid4(), actor=user.username, action="login", details={}))
    await session.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_raw)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request, session: SessionDep):
    token_hash = hash_token(body.refresh_token)
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(Session)
        .options(selectinload(Session.user).selectinload(User.role))
        .where(
            Session.refresh_token_hash == token_hash,
            Session.revoked == False,
            Session.expires_at > now,
        )
    )
    db_session = result.scalar_one_or_none()
    if not db_session or not db_session.user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")

    user = db_session.user
    perms = list(user.role.permissions) + list(user.supplementary_permissions)
    access_token = create_access_token(user.id, user.username, user.role.name, perms)

    new_refresh_raw = generate_refresh_token()
    db_session.refresh_token_hash = hash_token(new_refresh_raw)
    db_session.user_agent = request.headers.get("User-Agent")
    db_session.ip = _client_ip(request)
    await session.commit()

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_raw)


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest, session: SessionDep):
    token_hash = hash_token(body.refresh_token)
    result = await session.execute(select(Session).where(Session.refresh_token_hash == token_hash))
    db_session = result.scalar_one_or_none()
    if db_session:
        db_session.revoked = True
        await session.commit()


@router.post("/service-login", response_model=ServiceTokenResponse)
async def service_login(body: ServiceLoginRequest, session: SessionDep):
    result = await session.execute(
        select(ServiceAccount)
        .options(selectinload(ServiceAccount.role))
        .where(ServiceAccount.name == body.service_name)
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown service")

    if svc.bootstrap_token_hash is None or svc.bootstrap_token_hash != hash_token(body.bootstrap_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid bootstrap token")

    perms = list(svc.role.permissions) + list(svc.supplementary_permissions)
    token = create_service_token(svc.name, perms)

    session.add(AuditLog(
        id=uuid.uuid4(),
        actor=f"service:{svc.name}",
        action="service_login",
        details={},
    ))
    await session.commit()

    return ServiceTokenResponse(access_token=token)


@router.get("/me", response_model=MeOut)
async def me(payload: Annotated[dict, Depends(get_current_user_payload)]):
    sub = payload.get("sub", "")
    user_id_str = sub.replace("user:", "") if sub.startswith("user:") else "00000000-0000-0000-0000-000000000000"
    return MeOut(
        id=uuid.UUID(user_id_str),
        username=payload.get("username", "dev"),
        role=payload.get("role", "admin"),
        permissions=payload.get("perms", ["*"]),
    )
