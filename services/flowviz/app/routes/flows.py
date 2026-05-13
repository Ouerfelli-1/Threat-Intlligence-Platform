import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import Flow
from app.prompts import DIRECT_FLOW_PROMPT, PROMPT_VERSION
from app.schemas import FlowOut, FlowRequest

router = APIRouter(prefix="/flows", tags=["flows"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


def _cache_key(input_text: str) -> str:
    return hashlib.sha256(f"{input_text}{PROMPT_VERSION}".encode()).hexdigest()


@router.post("", response_model=FlowOut, dependencies=[Depends(require_permission("flowviz:read"))])
async def generate_flow(body: FlowRequest, request: Request, session: SessionDep):
    cache_key = _cache_key(body.input)

    result = await session.execute(select(Flow).where(Flow.input_hash == cache_key))
    cached = result.scalar_one_or_none()
    if cached:
        return _to_out(cached)

    output = await _call_ai(request, body.input, body.system)
    flow = Flow(
        id=uuid.uuid4(),
        input_hash=cache_key,
        input_text=body.input[:10000],
        output=output,
        model_name=request.app.state.ai_client.model,
        generated_at=datetime.now(timezone.utc),
    )
    session.add(flow)
    await session.commit()
    return _to_out(flow)


@router.post("/stream", dependencies=[Depends(require_permission("flowviz:read"))])
async def stream_flow(body: FlowRequest, request: Request):
    """Returns a Server-Sent Events stream of the raw AI output."""
    from tip_ai import OpenRouterMessage

    client = request.app.state.ai_client
    system_prompt = body.system or DIRECT_FLOW_PROMPT
    messages = [OpenRouterMessage(role="user", content=f"{system_prompt}{body.input}")]

    async def _event_stream():
        buffer = ""
        async for chunk in client.stream(messages):
            buffer += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.get("/{flow_id}", response_model=FlowOut, dependencies=[Depends(require_permission("flowviz:read"))])
async def get_flow(flow_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Flow).where(Flow.id == flow_id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise NotFoundError(f"Flow {flow_id} not found")
    return _to_out(flow)


async def _call_ai(request: Request, input_text: str, system_override: str | None) -> dict:
    from tip_ai import OpenRouterMessage

    client = request.app.state.ai_client
    system = system_override or DIRECT_FLOW_PROMPT
    messages = [OpenRouterMessage(role="user", content=f"{system}{input_text}")]
    raw = await client.chat(messages, response_format_json=True)
    return client.extract_json(raw)


def _to_out(flow: Flow) -> FlowOut:
    from app.schemas import FlowEdge, FlowNode, FlowOutput

    output = flow.output
    nodes = [FlowNode(**n) for n in output.get("nodes", [])]
    edges = [FlowEdge(**e) for e in output.get("edges", [])]
    return FlowOut(
        id=flow.id,
        input_hash=flow.input_hash,
        output=FlowOutput(nodes=nodes, edges=edges),
        model_name=flow.model_name,
        generated_at=flow.generated_at,
    )
