import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session_factory
from app.deps import require_admin
from app.models import Role
from app.schemas import RoleCreate, RoleOut, RoleUpdate

router = APIRouter(prefix="/roles", tags=["roles"])


async def _get_session() -> AsyncSession:
    async with get_session_factory()() as s:
        yield s


SessionDep = Annotated[AsyncSession, Depends(_get_session)]


@router.get("", response_model=list[RoleOut], dependencies=[Depends(require_admin)])
async def list_roles(session: SessionDep):
    result = await session.execute(select(Role))
    return result.scalars().all()


@router.post("", response_model=RoleOut, status_code=201, dependencies=[Depends(require_admin)])
async def create_role(body: RoleCreate, session: SessionDep):
    role = Role(id=uuid.uuid4(), name=body.name, permissions=body.permissions)
    session.add(role)
    await session.commit()
    return role


@router.patch("/{role_id}", response_model=RoleOut, dependencies=[Depends(require_admin)])
async def update_role(role_id: uuid.UUID, body: RoleUpdate, session: SessionDep):
    role = await session.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    if body.name is not None:
        role.name = body.name
    if body.permissions is not None:
        role.permissions = body.permissions
    await session.commit()
    return role


@router.delete("/{role_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_role(role_id: uuid.UUID, session: SessionDep):
    role = await session.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    await session.delete(role)
    await session.commit()
