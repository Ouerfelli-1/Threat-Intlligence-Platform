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


class SecretPreview(SecretMeta):
    """Safe-to-display version of a secret. Shows the first 8 characters of
    the decrypted value followed by `••••`, plus the total length so the
    admin UI can confirm 'yes, that's still the right key' without ever
    seeing the secret material."""
    preview: str
    length: int


class BootstrapFetchRequest(BaseModel):
    service_name: str
    bootstrap_token: str
    secret_name: str | None = None  # if provided, return single secret value
