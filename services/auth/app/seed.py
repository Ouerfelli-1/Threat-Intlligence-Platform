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

# Resource-level read permissions enforced across the API. Names must EXACTLY
# match what require_permission("<name>") checks for in each service. The
# original seed used schema-style names like `news:read` / `vuln:read` which
# don't match any endpoint — viewers ended up with effectively no access.
# Recipe used to compile this list: grep -r 'require_permission("[a-z_]+:read"'
_ALL_READS = [
    "intelligence:read",  # news + cves + feeds + orchestrator /ask
    "threats:read",       # threat-intel /threats /hibp
    "iocs:read",          # ioc-collector /indicators
    "actors:read",        # threat-actors /actors /tools /ttps /ransomware
    "assets:read",        # cmdb /assets /tags
    "profile:read",       # cmdb /profile/*
    "asm:read",           # asm /scopes /targets /findings /jobs
    "domainwatch:read",   # domainwatch /domains /snapshots /screenshot
    "integrations:read",  # wazuh + misp
    "flowviz:read",       # flowviz /flows
    "indicator:read",     # indicator-intel /investigations
    "reports:read",       # orchestrator /reports /relevance /correlations /policies
    "scheduling:read",    # scheduler /jobs /runs
]

_ROLES = [
    {
        "name": "admin",
        "permissions": ["*"],
    },
    {
        # Analyst can read everything + write user-driven CRUD on the analyst
        # layer (notes, status overrides, manual tags, manual IOCs/actors).
        "name": "analyst",
        "permissions": [
            *_ALL_READS,
            "intelligence:write",   # mark articles/CVEs as relevant, add notes
            "threats:write",        # manual threat creation
            "iocs:write",           # manual IOC + lookup
            "actors:write",         # manual actor creation
            "assets:write",         # tag editing, asset notes
            "indicator:write",      # trigger deep investigations
        ],
    },
    {
        # Viewer = read-only across the WHOLE platform. Mirrors what an
        # auditor / SOC manager / read-only stakeholder should see — every
        # page renders real data, but every mutate button 403s.
        "name": "viewer",
        "permissions": list(_ALL_READS),
    },
    {
        "name": "service",
        "permissions": [],
    },
]

_SERVICE_ACCOUNTS = [
    ("news-collector", ["news:read", "news:write"]),
    ("vuln-intel", ["vuln:read", "vuln:write"]),
    # threat-intel's /threats/{id}/analyze calls flowviz inline to embed an
    # attack-flow in the insight payload — needs flowviz:read on its JWT.
    # Auto-promotes high-confidence extracted IOCs into the IOC library
    # so the analyst doesn't have to manually copy them — needs iocs:write.
    ("threat-intel", ["threat:read", "threat:write", "flowviz:read", "iocs:write", "ioc:write"]),
    ("ioc-collector", ["ioc:read", "ioc:write"]),
    # threat-actors /actors/{id}/analyze calls flowviz inline to embed an
    # attack-flow in the insight payload — needs flowviz:read on its JWT.
    # Also pushes high-confidence extracted IOCs into the IOC library
    # (auto-promote) — needs iocs:write + ioc:write.
    ("threat-actors", ["actors:read", "actors:write", "flowviz:read", "iocs:write", "ioc:write"]),
    # threat-intel also auto-promotes high-confidence IOCs from threat
    # analysis into the IOC library — needs iocs:write + ioc:write.
    # (The earlier line already grants threat:* and flowviz:read.)
    ("integrations", ["integrations:read", "integrations:write", "ioc:read"]),
    ("cmdb", ["assets:read", "assets:write", "profile:read", "profile:write"]),
    ("flowviz", ["flowviz:read", "flowviz:write"]),
    ("asm", ["asm:read", "asm:write"]),
    ("domainwatch", ["domainwatch:read", "domainwatch:write", "ioc:read"]),
    (
        # The scheduler TRIGGERS write operations on every other service
        # (POST /ingest/run, /refresh/*, /scan/run, /check/run, /analyze).
        # Without these write perms every scheduled fire 401s and the
        # entire ingest pipeline silently stops. We had this bug live:
        # every job in scheduler.job_run_history returned "missing bearer
        # token" because outbound calls had no JWT AND the scheduler had
        # no write perms anyway.
        "scheduler",
        [
            "scheduling:read",
            "scheduling:write",
            "news:read",            "news:write",
            "vuln:read",
            "threat:read",          "threat:write",
            "ioc:read",             "ioc:write",        "iocs:write",
            "actors:read",          "actors:write",
            "integrations:read",    "integrations:write",
            "asm:read",             "asm:write",
            "domainwatch:read",     "domainwatch:write",
            "indicator:read",
            "intelligence:read",    "intelligence:write",  # vuln /refresh/*
            "reports:read",         "reports:write",       # orchestrator /analyze*
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
        else:
            # Reconcile permissions on every boot so the seeded role list is
            # the source of truth. Without this, fixing a typo in `_ROLES`
            # (e.g. news:read -> intelligence:read) needs a manual DB UPDATE
            # because the role row already exists. Idempotent — does nothing
            # if the permission set already matches.
            new_perms = list(role_def["permissions"])
            if sorted(role.permissions or []) != sorted(new_perms):
                role.permissions = new_perms
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
        else:
            # Reconcile supplementary_permissions the same way we do roles —
            # so when we add a new perm to _SERVICE_ACCOUNTS (e.g.
            # flowviz:read for threat-intel) an `auth` restart picks it up
            # instead of needing a manual UPDATE. Idempotent.
            if sorted(svc.supplementary_permissions or []) != sorted(perms):
                svc.supplementary_permissions = list(perms)

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
