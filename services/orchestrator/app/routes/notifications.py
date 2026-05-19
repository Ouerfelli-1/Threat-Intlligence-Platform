"""Notification management + dispatch endpoints.

Routes:
  GET    /notifications/rules                — list configured rules
  POST   /notifications/rules                — create
  PATCH  /notifications/rules/{rule_id}      — toggle/update
  DELETE /notifications/rules/{rule_id}      — remove
  GET    /notifications/dispatches?limit=    — recent dispatch history
  POST   /notifications/test                 — fire a synthetic event to a target
  POST   /internal/notify                    — event-source emit endpoint
                                               (no auth — services in
                                                docker network)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import NotificationDispatch, NotificationRule
from app.notify import dispatch_event

router = APIRouter(prefix="/notifications", tags=["notifications"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])


async def _session_dep():
    async for s in get_session(get_session_factory()):
        yield s

SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


# ── Schemas ────────────────────────────────────────────────────────────────

class RuleIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    event_type: str = Field(..., pattern=r"^[a-z_]+\.[a-z_]+$")
    channel: str = Field(..., pattern=r"^(smtp|telegram|webhook)$")
    target: str = Field(..., min_length=1)
    filter: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = None
    target: str | None = None
    filter: dict[str, Any] | None = None
    active: bool | None = None


class RuleOut(BaseModel):
    id: uuid.UUID
    name: str
    event_type: str
    channel: str
    target: str
    filter: dict[str, Any]
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class DispatchOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID | None
    event_type: str
    event_ref: str | None
    channel: str
    target: str
    status: str
    error: str | None
    payload: dict[str, Any]
    sent_at: datetime
    model_config = {"from_attributes": True}


class TestEventIn(BaseModel):
    """Body for POST /notifications/test — sends a synthetic event so the
    operator can verify their SMTP config + rule filter before the real
    event source fires."""
    event_type: str
    target: str | None = None  # if given, sends ONLY to this target (skip rules)
    payload: dict[str, Any] = Field(default_factory=dict)


class NotifyEventIn(BaseModel):
    """Internal — event sources POST this to /internal/notify."""
    event_type: str
    event_ref: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ── Rule CRUD ──────────────────────────────────────────────────────────────

@router.get(
    "/rules", response_model=list[RuleOut],
    dependencies=[Depends(require_permission("reports:read"))],
)
async def list_rules(session: SessionDep) -> list[RuleOut]:
    rows = (await session.execute(
        select(NotificationRule).order_by(NotificationRule.created_at.desc())
    )).scalars().all()
    return [RuleOut.model_validate(r) for r in rows]


@router.post(
    "/rules", response_model=RuleOut, status_code=201,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def create_rule(body: RuleIn, session: SessionDep) -> RuleOut:
    rule = NotificationRule(
        id=uuid.uuid4(),
        name=body.name,
        event_type=body.event_type,
        channel=body.channel,
        target=body.target,
        filter=body.filter,
        active=body.active,
    )
    session.add(rule)
    await session.flush()
    await session.commit()
    return RuleOut.model_validate(rule)


@router.patch(
    "/rules/{rule_id}", response_model=RuleOut,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def update_rule(rule_id: uuid.UUID, body: RuleUpdate, session: SessionDep) -> RuleOut:
    rule = await session.get(NotificationRule, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rule not found")
    if body.name is not None:    rule.name = body.name
    if body.target is not None:  rule.target = body.target
    if body.filter is not None:  rule.filter = body.filter
    if body.active is not None:  rule.active = body.active
    rule.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.commit()
    return RuleOut.model_validate(rule)


@router.delete(
    "/rules/{rule_id}", status_code=204,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def delete_rule(rule_id: uuid.UUID, session: SessionDep) -> None:
    rule = await session.get(NotificationRule, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rule not found")
    await session.delete(rule)
    await session.commit()


# ── Dispatch history ───────────────────────────────────────────────────────

@router.get(
    "/dispatches", response_model=list[DispatchOut],
    dependencies=[Depends(require_permission("reports:read"))],
)
async def list_dispatches(session: SessionDep, limit: int = 50) -> list[DispatchOut]:
    rows = (await session.execute(
        select(NotificationDispatch)
        .order_by(NotificationDispatch.sent_at.desc())
        .limit(max(1, min(limit, 200)))
    )).scalars().all()
    return [DispatchOut.model_validate(r) for r in rows]


# ── Synthetic test send ────────────────────────────────────────────────────

@router.post(
    "/test",
    dependencies=[Depends(require_permission("reports:write"))],
)
async def test_notify(body: TestEventIn, request: Request, session: SessionDep) -> dict:
    """Send a test notification. Two modes:
      * No `target` -> evaluates against all rules for the event_type
        (lets you preview what would fire for a real event).
      * `target` given -> bypasses rules; sends a one-off to that address
        using the SMTP channel. Good for "does my SMTP config even work".
    """
    smtp_config = getattr(request.app.state, "smtp_config", None)
    payload = {**body.payload}
    payload.setdefault("title", "TIP test notification")
    payload.setdefault("summary",
        "If you see this, your SMTP config and rule are working. "
        "This was sent from /notifications/test.")
    payload.setdefault("severity", "info")

    if body.target:
        # One-off send, bypassing rules. We still log it to dispatches.
        from app.notify.dispatcher import _render_email
        from app.notify.smtp import send_email
        if not smtp_config or not smtp_config.configured:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                "SMTP not configured (set SMTP_HOST + SMTP_FROM in secrets vault)")
        subject, text_body, html_body = _render_email(body.event_type, payload)
        ok, err = await send_email(
            smtp_config, to_addr=body.target,
            subject=subject, body_text=text_body, body_html=html_body,
        )
        session.add(NotificationDispatch(
            id=uuid.uuid4(), rule_id=None, event_type=body.event_type,
            event_ref="test", channel="smtp", target=body.target,
            status="sent" if ok else "failed", error=err, payload=payload,
        ))
        await session.commit()
        return {"sent": int(ok), "failed": int(not ok), "error": err}

    tally = await dispatch_event(
        session=session, smtp_config=smtp_config,
        event_type=body.event_type, event_ref="test", payload=payload,
    )
    return tally


# ── Internal emit endpoint ─────────────────────────────────────────────────

@internal_router.post("/notify")
async def emit_event(body: NotifyEventIn, request: Request, session: SessionDep) -> dict:
    """Event sources (domainwatch, vuln-intel, threat-intel, etc.) POST
    here to fan out an event to all matching rules. No auth — services
    inside the docker network are trusted (see auth simplification commit).
    """
    smtp_config = getattr(request.app.state, "smtp_config", None)
    tally = await dispatch_event(
        session=session, smtp_config=smtp_config,
        event_type=body.event_type, event_ref=body.event_ref,
        payload=body.payload,
    )
    return tally
