import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session_factory
from app.deps import require_admin
from app.models import Role, User
from app.schemas import PermissionGrant, UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


async def _get_session() -> AsyncSession:
    async with get_session_factory()() as s:
        yield s


SessionDep = Annotated[AsyncSession, Depends(_get_session)]
AdminDep = Annotated[dict, Depends(require_admin)]


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_admin)])
async def list_users(session: SessionDep):
    result = await session.execute(select(User).options(selectinload(User.role)))
    return result.scalars().all()


@router.post("", response_model=UserOut, status_code=201, dependencies=[Depends(require_admin)])
async def create_user(body: UserCreate, session: SessionDep):
    role = await session.get(Role, body.role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

    user = User(
        id=uuid.uuid4(),
        username=body.username,
        password_hash=hash_password(body.password),
        role_id=body.role_id,
        supplementary_permissions=body.supplementary_permissions,
        active=body.active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user, ["role"])
    return user


@router.patch("/{user_id}", response_model=UserOut, dependencies=[Depends(require_admin)])
async def update_user(user_id: uuid.UUID, body: UserUpdate, session: SessionDep):
    result = await session.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.role_id is not None:
        role = await session.get(Role, body.role_id)
        if not role:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
        user.role_id = body.role_id
    if body.supplementary_permissions is not None:
        user.supplementary_permissions = body.supplementary_permissions
    if body.active is not None:
        user.active = body.active

    await session.commit()
    await session.refresh(user, ["role"])
    return user


@router.delete("/{user_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_user(user_id: uuid.UUID, session: SessionDep):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await session.delete(user)
    await session.commit()


@router.post("/{user_id}/permissions", response_model=UserOut, dependencies=[Depends(require_admin)])
async def grant_permissions(user_id: uuid.UUID, body: PermissionGrant, session: SessionDep):
    result = await session.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    existing = set(user.supplementary_permissions)
    existing.update(body.permissions)
    user.supplementary_permissions = list(existing)
    await session.commit()
    return user
