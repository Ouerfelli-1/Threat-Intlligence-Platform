import hashlib
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import AuthContext, current_user, require_permission
from tip_common import NotFoundError

from app.db import get_session
from app.models import OrgProfileVersion, ProfileChangeLog
from app.schemas import (
    AutoAddRequest,
    CompanyProfile,
    CompanyProfileOut,
    CompanyProfilePatch,
    ProfileChangeLogOut,
)
from app.settings import get_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get(
    "/latest",
    response_model=CompanyProfileOut,
    dependencies=[Depends(require_permission("profile:read"))],
)
async def get_latest_profile(session: AsyncSession = Depends(get_session)) -> CompanyProfileOut:
    row = await session.scalar(
        select(OrgProfileVersion).order_by(OrgProfileVersion.version.desc()).limit(1)
    )
    if row is None:
        raise NotFoundError("no company profile has been set yet")
    return CompanyProfileOut(
        **row.payload, version=row.version, edited_by=row.edited_by, edited_at=row.edited_at
    )


@router.patch(
    "",
    response_model=CompanyProfileOut,
    dependencies=[Depends(require_permission("profile:write"))],
)
async def patch_profile(
    body: CompanyProfilePatch,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(current_user),
) -> CompanyProfileOut:
    latest = await session.scalar(
        select(OrgProfileVersion).order_by(OrgProfileVersion.version.desc()).limit(1)
    )
    base_payload = latest.payload if latest else None
    patch = body.model_dump(exclude_unset=True)
    if base_payload is None:
        if "identity" not in patch:
            raise NotFoundError(
                "no profile exists yet; first PATCH must include 'identity'"
            )
        merged = patch
    else:
        merged = {**base_payload}
        for key, value in patch.items():
            if value is not None:
                merged[key] = value
    new_profile = CompanyProfile.model_validate(merged)
    row = OrgProfileVersion(
        payload=new_profile.model_dump(),
        edited_by=auth.subject,
    )
    session.add(row)
    await session.flush()

    # Schedule ASM auto-sync in background
    settings = get_settings()
    service_jwt = getattr(request.app.state, "service_jwt", "") or ""
    background_tasks.add_task(
        _run_asm_sync, base_payload, new_profile.model_dump(), settings.asm_url, service_jwt
    )

    return CompanyProfileOut(
        **row.payload, version=row.version, edited_by=row.edited_by, edited_at=row.edited_at
    )


async def _run_asm_sync(old_payload, new_payload, asm_url, service_jwt):
    """Wrapper that imports lazily to avoid circular deps."""
    from app.asm_sync import sync_to_asm
    try:
        await sync_to_asm(old_payload, new_payload, asm_url, service_jwt)
    except Exception:
        log.exception("ASM sync background task failed")


@router.post(
    "/auto-add",
    response_model=ProfileChangeLogOut,
    status_code=201,
    dependencies=[Depends(require_permission("profile:write"))],
)
async def auto_add_to_profile(
    body: AutoAddRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProfileChangeLogOut:
    """Idempotent auto-add of a product/actor to the company profile.

    Called by other services when an analyst marks a resource as 'relevant'.
    Adds the product_name to technology.software (or actor to risk.threat_concerns)
    if not already present.
    """
    if not body.product_name and not body.actor:
        raise NotFoundError("either product_name or actor must be provided")

    latest = await session.scalar(
        select(OrgProfileVersion).order_by(OrgProfileVersion.version.desc()).limit(1)
    )
    if latest is None:
        raise NotFoundError("no company profile exists yet; cannot auto-add")

    payload = dict(latest.payload)
    changed = False
    added_value = ""
    change_type = ""

    if body.product_name:
        tech = payload.get("technology", {})
        software = list(tech.get("software", []))
        if body.product_name not in software:
            software.append(body.product_name)
            tech["software"] = software
            payload["technology"] = tech
            changed = True
            added_value = body.product_name
            change_type = "auto_add_software"
        else:
            change_type = "auto_add_software_duplicate"
            added_value = body.product_name

    if body.actor:
        risk = payload.get("risk", {})
        concerns = list(risk.get("threat_concerns", []))
        if body.actor not in concerns:
            concerns.append(body.actor)
            risk["threat_concerns"] = concerns
            payload["risk"] = risk
            changed = True
            added_value = added_value or body.actor
            change_type = change_type or "auto_add_actor"
        else:
            change_type = change_type or "auto_add_actor_duplicate"
            added_value = added_value or body.actor

    version_num = latest.version
    if changed:
        new_profile = CompanyProfile.model_validate(payload)
        row = OrgProfileVersion(
            payload=new_profile.model_dump(),
            edited_by=f"auto:{body.source_resource_type}",
        )
        session.add(row)
        await session.flush()
        version_num = row.version

    log_entry = ProfileChangeLog(
        id=uuid.uuid4(),
        version=version_num,
        change_type=change_type,
        source_resource_type=body.source_resource_type,
        source_resource_id=body.source_resource_id,
        added_value=added_value,
        added_by_analyst=f"auto:{body.source_resource_type}",
    )
    session.add(log_entry)
    await session.flush()
    return ProfileChangeLogOut.model_validate(log_entry)


@router.get(
    "/change-log",
    response_model=list[ProfileChangeLogOut],
    dependencies=[Depends(require_permission("profile:read"))],
)
async def list_change_log(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[ProfileChangeLogOut]:
    rows = (
        await session.execute(
            select(ProfileChangeLog)
            .order_by(ProfileChangeLog.recorded_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [ProfileChangeLogOut.model_validate(r) for r in rows]


@router.get(
    "/versions",
    response_model=list[CompanyProfileOut],
    dependencies=[Depends(require_permission("profile:read"))],
)
async def list_versions(
    session: AsyncSession = Depends(get_session),
) -> list[CompanyProfileOut]:
    rows = (
        await session.execute(
            select(OrgProfileVersion).order_by(OrgProfileVersion.version.desc())
        )
    ).scalars().all()
    return [
        CompanyProfileOut(**r.payload, version=r.version, edited_by=r.edited_by, edited_at=r.edited_at)
        for r in rows
    ]


@router.get(
    "/versions/{version}",
    response_model=CompanyProfileOut,
    dependencies=[Depends(require_permission("profile:read"))],
)
async def get_version(
    version: int, session: AsyncSession = Depends(get_session)
) -> CompanyProfileOut:
    row = await session.get(OrgProfileVersion, version)
    if row is None:
        raise NotFoundError(f"profile version {version} not found")
    return CompanyProfileOut(
        **row.payload, version=row.version, edited_by=row.edited_by, edited_at=row.edited_at
    )
