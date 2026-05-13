from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_common import NotFoundError

from app.db import get_session
from app.models import CVE, EPSS, KEV
from app.schemas import CVEDetail, CVEList, CVEOut, KEVOut

router = APIRouter(tags=["cves"])


@router.get(
    "/cves",
    response_model=CVEList,
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def list_cves(
    severity: str | None = None,
    product: str | None = None,
    since: datetime | None = None,
    kev: bool = False,
    epss_gte: float | None = Query(None, ge=0, le=1),
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> CVEList:
    stmt = select(CVE)
    if severity:
        stmt = stmt.where(CVE.severity == severity)
    if since:
        stmt = stmt.where(CVE.last_modified_at >= since)
    if product:
        stmt = stmt.where(CVE.affected_products.cast(str).ilike(f"%{product}%"))
    if kev:
        stmt = stmt.join(KEV, KEV.cve_id == CVE.cve_id)
    if epss_gte is not None:
        stmt = stmt.join(EPSS, EPSS.cve_id == CVE.cve_id).where(EPSS.epss >= epss_gte)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(CVE.last_modified_at.desc().nullslast()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return CVEList(items=[CVEOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/cves/{cve_id}",
    response_model=CVEDetail,
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def get_cve(cve_id: str, session: AsyncSession = Depends(get_session)) -> CVEDetail:
    cve = await session.get(CVE, cve_id)
    if cve is None:
        raise NotFoundError(f"CVE {cve_id} not found")
    epss = await session.get(EPSS, cve_id)
    kev = await session.get(KEV, cve_id)
    out = CVEDetail.model_validate(cve)
    if epss is not None:
        out.epss = float(epss.epss)
        out.epss_percentile = float(epss.percentile)
    if kev is not None:
        out.kev = True
        out.kev_date_added = kev.date_added
        out.kev_ransomware_use = kev.ransomware_use
    return out


@router.get(
    "/kev",
    response_model=list[KEVOut],
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def list_kev(session: AsyncSession = Depends(get_session)) -> list[KEVOut]:
    rows = (
        await session.execute(select(KEV).order_by(KEV.date_added.desc().nullslast()))
    ).scalars().all()
    return [KEVOut.model_validate(r) for r in rows]
