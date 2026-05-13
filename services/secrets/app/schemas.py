from datetime import datetime

from pydantic import BaseModel


class SecretCreate(BaseModel):
    name: str
    value: str
    metadata: dict = {}


class SecretRotate(BaseModel):
    new_value: str


class SecretMeta(BaseModel):
    name: str
    version: int
    metadata: dict
    created_at: datetime
    updated_at: datetime


class SecretValue(SecretMeta):
    value: str


class BootstrapFetchRequest(BaseModel):
    service_name: str
    bootstrap_token: str
    secret_name: str | None = None  # if provided, return single secret value
