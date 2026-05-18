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


def _flatten(user: User) -> dict:
    """Convert a User+Role row into the flat shape the frontend expects.
    Resolves `role` to the role's NAME (string), surfaces the role.id as
    `role_id`, and merges role permissions with supplementary into an effective
    `permissions` list."""
    role_name = user.role.name if user.role else ""
    role_id = user.role.id if user.role else user.role_id
    role_perms = list(user.role.permissions or []) if user.role else []
    supp = list(user.supplementary_permissions or [])
    effective = list(dict.fromkeys(role_perms + supp))
    return {
        "id": user.id,
        "username": user.username,
        "email": None,  # users table has no email column today; reserved for future migration
        "role": role_name,
        "role_id": role_id,
        "permissions": effective,
        "supplementary_permissions": supp,
        "active": user.active,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_admin)])
async def list_users(session: SessionDep):
    result = await session.execute(select(User).options(selectinload(User.role)))
    return [_flatten(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=201, dependencies=[Depends(require_admin)])
async def create_user(body: UserCreate, session: SessionDep):
    role = await session.get(Role, body.role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

    # Normalize username — trim + lowercase so login can match
    # case-insensitively without needing a functional index. Pre-flight a
    # uniqueness check so we return a clean 409 instead of a raw IntegrityError.
    username_norm = (body.username or "").strip().lower()
    if not username_norm:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username is required")
    from sqlalchemy import func
    exists = await session.execute(
        select(User).where(func.lower(User.username) == username_norm)
    )
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"User '{username_norm}' already exists")

    user = User(
        id=uuid.uuid4(),
        username=username_norm,
        password_hash=hash_password(body.password),
        role_id=body.role_id,
        supplementary_permissions=body.supplementary_permissions,
        active=body.active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user, ["role"])
    return _flatten(user)


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
    return _flatten(user)


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
    await session.refresh(user, ["role"])
    return _flatten(user)
