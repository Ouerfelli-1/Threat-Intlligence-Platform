"""Seed roles, service accounts, and admin user on first boot."""
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role, ServiceAccount, User
from app.security import hash_password, hash_token
from app.settings import get_settings

settings = get_settings()

TokenResolver = Callable[[str], Awaitable[str | None]]

_ROLES = [
    {
        "name": "admin",
        "permissions": ["*"],
    },
    {
        "name": "analyst",
        "permissions": [
            "intelligence:read",
            "actors:read",
            "iocs:read",
            "assets:read",
            "asm:read",
            "domainwatch:read",
            "reports:read",
            "news:read",
            "vuln:read",
            "threat:read",
            "indicator:read",
        ],
    },
    {
        "name": "viewer",
        "permissions": [
            "news:read",
            "vuln:read",
            "threat:read",
            "actors:read",
            "iocs:read",
            "assets:read",
            "reports:read",
        ],
    },
    {
        "name": "service",
        "permissions": [],
    },
]

_SERVICE_ACCOUNTS = [
    ("news-collector", ["news:read", "news:write"]),
    ("vuln-intel", ["vuln:read", "vuln:write"]),
    ("threat-intel", ["threat:read", "threat:write"]),
    ("ioc-collector", ["ioc:read", "ioc:write"]),
    ("threat-actors", ["actors:read", "actors:write"]),
    ("integrations", ["integrations:read", "integrations:write", "ioc:read"]),
    ("cmdb", ["assets:read", "assets:write", "profile:read", "profile:write"]),
    ("flowviz", ["flowviz:read", "flowviz:write"]),
    ("asm", ["asm:read", "asm:write"]),
    ("domainwatch", ["domainwatch:read", "domainwatch:write", "ioc:read"]),
    (
        "scheduler",
        [
            "scheduling:read",
            "scheduling:write",
            "news:read",
            "vuln:read",
            "threat:read",
            "ioc:read",
            "actors:read",
            "integrations:read",
            "asm:read",
            "domainwatch:read",
            "indicator:read",
        ],
    ),
    ("secrets", ["secrets:read", "secrets:write"]),
    ("indicator-intel", ["ioc:read", "actors:read", "news:read", "indicator:read", "indicator:write"]),
    (
        "orchestrator",
        [
            "intelligence:read",
            "actors:read",
            "ioc:read",
            "vuln:read",
            "threat:read",
            "integrations:read",
            "assets:read",
            "asm:read",
            "domainwatch:read",
            "reports:read",
            "reports:write",
            "flowviz:read",
            "flowviz:write",
            "indicator:read",
        ],
    ),
]


async def seed(session: AsyncSession, token_resolver: TokenResolver | None = None) -> None:
    role_map: dict[str, uuid.UUID] = {}

    for role_def in _ROLES:
        result = await session.execute(select(Role).where(Role.name == role_def["name"]))
        role = result.scalar_one_or_none()
        if not role:
            role = Role(id=uuid.uuid4(), **role_def)
            session.add(role)
            await session.flush()
        role_map[role.name] = role.id

    service_role_id = role_map["service"]
    for svc_name, perms in _SERVICE_ACCOUNTS:
        result = await session.execute(select(ServiceAccount).where(ServiceAccount.name == svc_name))
        svc = result.scalar_one_or_none()
        if not svc:
            svc = ServiceAccount(
                id=uuid.uuid4(),
                name=svc_name,
                role_id=service_role_id,
                supplementary_permissions=perms,
            )
            session.add(svc)

        if token_resolver is not None:
            token = await token_resolver(svc_name)
            if token:
                svc.bootstrap_token_hash = hash_token(token)

    admin_role_id = role_map["admin"]
    result = await session.execute(select(User).where(User.username == settings.bootstrap_admin_username))
    if not result.scalar_one_or_none():
        admin = User(
            id=uuid.uuid4(),
            username=settings.bootstrap_admin_username,
            password_hash=hash_password(settings.bootstrap_admin_password),
            role_id=admin_role_id,
        )
        session.add(admin)
        print(f"[auth] Created admin user: {settings.bootstrap_admin_username}")

    await session.commit()
