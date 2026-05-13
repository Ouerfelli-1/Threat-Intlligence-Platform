from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class ServiceLoginRequest(BaseModel):
    service_name: str
    bootstrap_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ServiceTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RoleOut(BaseModel):
    id: UUID
    name: str
    permissions: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[list[str]] = None


class UserOut(BaseModel):
    id: UUID
    username: str
    role: RoleOut
    supplementary_permissions: list[str]
    active: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    password: str
    role_id: UUID
    supplementary_permissions: list[str] = []
    active: bool = True


class UserUpdate(BaseModel):
    password: Optional[str] = None
    role_id: Optional[UUID] = None
    supplementary_permissions: Optional[list[str]] = None
    active: Optional[bool] = None


class PermissionGrant(BaseModel):
    permissions: list[str]


class ServiceAccountOut(BaseModel):
    id: UUID
    name: str
    role: RoleOut
    supplementary_permissions: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: UUID
    user_id: UUID
    issued_at: datetime
    expires_at: datetime
    revoked: bool
    user_agent: Optional[str]
    ip: Optional[str]

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    id: UUID
    username: str
    role: str
    permissions: list[str]
