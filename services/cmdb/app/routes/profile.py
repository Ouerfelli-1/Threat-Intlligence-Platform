from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import AuthContext, current_user, require_permission
from tip_common import NotFoundError

from app.db import get_session
from app.models import OrgProfileVersion
from app.schemas import CompanyProfile, CompanyProfileOut, CompanyProfilePatch

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
    return CompanyProfileOut(
        **row.payload, version=row.version, edited_by=row.edited_by, edited_at=row.edited_at
    )


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
