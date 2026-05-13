import asyncio
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session
from tip_schemas import normalize_indicator

from app.db import get_session_factory
from app.investigate import run_investigation, synthesize_verdict
from app.models import Investigation
from app.schemas import AsyncInvestigateResponse, InvestigateRequest, InvestigationOut

router = APIRouter(tags=["investigations"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]

_SYNC_TIMEOUT = 30.0


@router.post(
    "/investigate",
    response_model=InvestigationOut,
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def investigate(body: InvestigateRequest, request: Request, session: SessionDep):
    settings = request.app.state.settings
    ai_client = request.app.state.ai_client
    service_jwt = getattr(request.app.state, "service_jwt", "")

    normalized = normalize_indicator(body.type, body.value)

    inv = Investigation(
        id=uuid.uuid4(),
        indicator_type=body.type,
        normalized_value=normalized,
        raw_value=body.value,
        status="running",
    )
    session.add(inv)
    await session.commit()

    start = time.monotonic()
    try:
        raw = await asyncio.wait_for(
            run_investigation(body.type, body.value, settings, service_jwt),
            timeout=_SYNC_TIMEOUT,
        )
        result = await synthesize_verdict(body.type, body.value, raw, ai_client)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        inv.status = "complete"
        inv.verdict = result.get("verdict")
        inv.confidence = result.get("confidence")
        inv.risk_score = result.get("risk_score")
        inv.summary = result.get("summary")
        inv.payload = {**raw, "ai_result": result}
        inv.model_name = getattr(ai_client, "model", None)
        inv.duration_ms = elapsed_ms
        await session.commit()
    except asyncio.TimeoutError:
        inv.status = "failed"
        inv.payload = {"error": "investigation timed out"}
        await session.commit()
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "Investigation timed out; use /investigate/async")
    except Exception as exc:
        inv.status = "failed"
        inv.payload = {"error": str(exc)}
        await session.commit()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    return inv


@router.post(
    "/investigate/async",
    response_model=AsyncInvestigateResponse,
    status_code=202,
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def investigate_async(
    body: InvestigateRequest,
    request: Request,
    background: BackgroundTasks,
    session: SessionDep,
):
    settings = request.app.state.settings
    ai_client = request.app.state.ai_client
    service_jwt = getattr(request.app.state, "service_jwt", "")

    normalized = normalize_indicator(body.type, body.value)
    inv = Investigation(
        id=uuid.uuid4(),
        indicator_type=body.type,
        normalized_value=normalized,
        raw_value=body.value,
        status="running",
    )
    session.add(inv)
    await session.commit()
    inv_id = inv.id

    async def _run():
        async with get_session_factory()() as bg_session:
            start = time.monotonic()
            try:
                raw = await run_investigation(body.type, body.value, settings, service_jwt)
                result = await synthesize_verdict(body.type, body.value, raw, ai_client)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                record = await bg_session.get(Investigation, inv_id)
                if record:
                    record.status = "complete"
                    record.verdict = result.get("verdict")
                    record.confidence = result.get("confidence")
                    record.risk_score = result.get("risk_score")
                    record.summary = result.get("summary")
                    record.payload = {**raw, "ai_result": result}
                    record.model_name = getattr(ai_client, "model", None)
                    record.duration_ms = elapsed_ms
                    await bg_session.commit()
            except Exception as exc:
                record = await bg_session.get(Investigation, inv_id)
                if record:
                    record.status = "failed"
                    record.payload = {"error": str(exc)}
                    await bg_session.commit()

    background.add_task(_run)
    return AsyncInvestigateResponse(job_id=inv_id)


@router.get(
    "/investigations",
    response_model=list[InvestigationOut],
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def list_investigations(
    session: SessionDep,
    value: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(Investigation).order_by(desc(Investigation.investigated_at))
    if value:
        stmt = stmt.where(Investigation.raw_value == value)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get(
    "/investigations/{investigation_id}",
    response_model=InvestigationOut,
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def get_investigation(investigation_id: uuid.UUID, session: SessionDep):
    inv = await session.get(Investigation, investigation_id)
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    return inv
