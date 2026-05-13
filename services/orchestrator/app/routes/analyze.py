import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.analysis import run_adhoc_ask, run_analysis_cycle, run_geo_prediction
from app.context import fetch_company_profile
from app.db import get_session_factory
from app.models import ActorLikelihood, Correlation, CveRelevance, Report
from app.schemas import (
    ActorLikelihoodOut,
    AnalysisJobResponse,
    AskRequest,
    CorrelationOut,
    CveRelevanceOut,
    ReportOut,
)

router = APIRouter(tags=["analyze"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.post(
    "/analyze",
    response_model=AnalysisJobResponse,
    status_code=202,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def trigger_analysis(request: Request, background: BackgroundTasks):
    ai = request.app.state.ai_client
    settings = request.app.state.settings
    service_jwt = getattr(request.app.state, "service_jwt", "")
    run_id = uuid.uuid4()

    async def _run():
        await run_analysis_cycle(ai, settings, service_jwt)

    background.add_task(_run)
    return AnalysisJobResponse(run_id=run_id)


@router.post(
    "/analyze/geo",
    response_model=AnalysisJobResponse,
    status_code=202,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def trigger_geo(request: Request, background: BackgroundTasks):
    ai = request.app.state.ai_client
    settings = request.app.state.settings
    service_jwt = getattr(request.app.state, "service_jwt", "")
    run_id = uuid.uuid4()

    async def _run():
        await run_geo_prediction(ai, settings, service_jwt)

    background.add_task(_run)
    return AnalysisJobResponse(run_id=run_id)


@router.post(
    "/ask",
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def ask(body: AskRequest, request: Request):
    ai = request.app.state.ai_client
    settings = request.app.state.settings
    service_jwt = getattr(request.app.state, "service_jwt", "")

    profile = await fetch_company_profile(settings, service_jwt)
    context: dict = {}
    if body.cve_id:
        context["cve_id"] = body.cve_id
    if body.ioc:
        context["ioc"] = body.ioc
    if body.actor:
        context["actor"] = body.actor
    if body.text:
        context["additional_context"] = body.text

    return await run_adhoc_ask(ai, body.question, profile, context, settings)


@router.get(
    "/reports",
    response_model=list[ReportOut],
    dependencies=[Depends(require_permission("reports:read"))],
)
async def list_reports(
    session: SessionDep,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    stmt = select(Report).order_by(desc(Report.generated_at))
    if kind:
        stmt = stmt.where(Report.kind == kind)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get(
    "/reports/{report_id}",
    response_model=ReportOut,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_report(report_id: uuid.UUID, session: SessionDep):
    from fastapi import HTTPException, status
    report = await session.get(Report, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


@router.get(
    "/relevance/cves",
    response_model=list[CveRelevanceOut],
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_cve_relevance(session: SessionDep, limit: int = 20):
    from sqlalchemy import text
    result = await session.execute(
        select(CveRelevance)
        .order_by(desc(CveRelevance.scored_at), desc(CveRelevance.relevance_score))
        .limit(limit)
    )
    return result.scalars().all()


@router.get(
    "/relevance/actors",
    response_model=list[ActorLikelihoodOut],
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_actor_likelihood(session: SessionDep, limit: int = 10):
    result = await session.execute(
        select(ActorLikelihood)
        .order_by(desc(ActorLikelihood.scored_at), desc(ActorLikelihood.likelihood_score))
        .limit(limit)
    )
    return result.scalars().all()


@router.get(
    "/correlations",
    response_model=list[CorrelationOut],
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_correlations(session: SessionDep, since: str | None = None, limit: int = 50):
    stmt = select(Correlation).order_by(desc(Correlation.detected_at)).limit(limit)
    if since:
        from datetime import datetime
        dt = datetime.fromisoformat(since)
        stmt = stmt.where(Correlation.detected_at >= dt)
    result = await session.execute(stmt)
    return result.scalars().all()
