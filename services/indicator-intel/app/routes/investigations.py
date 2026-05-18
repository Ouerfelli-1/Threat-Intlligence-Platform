import asyncio
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session
from tip_schemas import normalize_indicator

from app.db import get_session_factory
from app.investigate import auto_detect_type, run_investigation, synthesize_verdict
from app.models import Investigation
from app.schemas import AsyncInvestigateResponse, InvestigateRequest, InvestigationOut

router = APIRouter(tags=["investigations"])


async def _session_dep():
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]

_SYNC_TIMEOUT = 30.0


def _resolve_type(raw_type: str | None, raw_value: str) -> str:
    if not raw_type or raw_type == "auto":
        return auto_detect_type(raw_value)
    return raw_type


@router.post(
    "/investigate",
    response_model=InvestigationOut,
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def investigate(
    body: InvestigateRequest,
    request: Request,
    session: SessionDep,
    run_ai: bool = Query(
        False,
        description=(
            "When false (default) the AI synthesizer is skipped; only passive "
            "sources run. Call POST /investigations/{id}/synthesize later if "
            "you want a verdict."
        ),
    ),
):
    settings = request.app.state.settings
    service_jwt = getattr(request.app.state, "service_jwt", "")

    resolved_type = _resolve_type(body.type, body.value)
    try:
        normalized = normalize_indicator(resolved_type, body.value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    inv = Investigation(
        id=uuid.uuid4(),
        indicator_type=resolved_type,
        normalized_value=normalized,
        raw_value=body.value,
        status="running",
    )
    session.add(inv)
    await session.commit()

    start = time.monotonic()
    try:
        raw = await asyncio.wait_for(
            run_investigation(resolved_type, body.value, settings, service_jwt),
            timeout=_SYNC_TIMEOUT,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        inv.status = "complete"
        inv.payload = raw
        inv.duration_ms = elapsed_ms

        if run_ai:
            ai_client = request.app.state.ai_client
            verdict = await synthesize_verdict(resolved_type, body.value, raw, ai_client)
            inv.verdict = verdict.get("verdict")
            inv.confidence = verdict.get("confidence")
            inv.risk_score = verdict.get("risk_score")
            inv.summary = verdict.get("summary")
            inv.model_name = getattr(ai_client, "model", None)
            inv.payload = {**raw, "ai_result": verdict}

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
    run_ai: bool = Query(
        False,
        description="When true, automatically synthesize an AI verdict after passive sources complete.",
    ),
):
    """Kicks off an investigation and returns a job_id. Poll GET /investigations/{job_id}.
    AI verdict synthesis is OFF by default — call POST /investigations/{id}/synthesize on demand."""
    settings = request.app.state.settings
    ai_client = request.app.state.ai_client
    service_jwt = getattr(request.app.state, "service_jwt", "")

    resolved_type = _resolve_type(body.type, body.value)
    try:
        normalized = normalize_indicator(resolved_type, body.value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    inv = Investigation(
        id=uuid.uuid4(),
        indicator_type=resolved_type,
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
                raw = await run_investigation(resolved_type, body.value, settings, service_jwt)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                record = await bg_session.get(Investigation, inv_id)
                if record is None:
                    return
                record.status = "complete"
                record.payload = raw
                record.duration_ms = elapsed_ms

                if run_ai:
                    try:
                        verdict = await synthesize_verdict(resolved_type, body.value, raw, ai_client)
                        record.verdict = verdict.get("verdict")
                        record.confidence = verdict.get("confidence")
                        record.risk_score = verdict.get("risk_score")
                        record.summary = verdict.get("summary")
                        record.model_name = getattr(ai_client, "model", None)
                        record.payload = {**raw, "ai_result": verdict}
                    except Exception as ai_exc:
                        # AI failure should not fail the whole investigation
                        record.payload = {**raw, "ai_error": str(ai_exc)}

                await bg_session.commit()
            except Exception as exc:
                record = await bg_session.get(Investigation, inv_id)
                if record:
                    record.status = "failed"
                    record.payload = {"error": str(exc)}
                    await bg_session.commit()

    background.add_task(_run)
    return AsyncInvestigateResponse(job_id=inv_id)


@router.post(
    "/investigations/{investigation_id}/synthesize",
    response_model=InvestigationOut,
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def synthesize(
    investigation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
):
    """On-demand AI verdict for a previously-completed investigation.
    Reads the stored passive payload (no new HTTP calls) and asks the LLM
    to synthesize a verdict + recommendations. Cheap to retry."""
    inv = await session.get(Investigation, investigation_id)
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    if inv.status != "complete":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Investigation status is '{inv.status}'. Synthesis is only valid for completed investigations.",
        )

    ai_client = request.app.state.ai_client
    # Strip any prior ai_result so we don't feed the model its own output
    raw_findings = {k: v for k, v in (inv.payload or {}).items() if k != "ai_result"}
    try:
        verdict = await synthesize_verdict(inv.indicator_type, inv.raw_value, raw_findings, ai_client)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"AI synthesis failed: {exc}") from exc

    inv.verdict = verdict.get("verdict")
    inv.confidence = verdict.get("confidence")
    inv.risk_score = verdict.get("risk_score")
    inv.summary = verdict.get("summary")
    inv.model_name = getattr(ai_client, "model", None)
    inv.payload = {**raw_findings, "ai_result": verdict}
    await session.commit()
    return inv


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
