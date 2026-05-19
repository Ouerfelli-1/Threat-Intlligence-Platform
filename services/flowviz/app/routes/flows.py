import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_ai import (
    LiteLLMError,
    LiteLLMRateLimitError,
    LiteLLMRequestTooLargeError,
    build_ai_client,
)
from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import Flow
from app.prompts import DIRECT_FLOW_PROMPT, PROMPT_VERSION
from app.schemas import FlowOut, FlowOutput, FlowRequest

router = APIRouter(prefix="/flows", tags=["flows"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


def _cache_key(input_text: str, model: str | None = None) -> str:
    # Include the model in the cache key — different models can produce
    # different flow JSON, and a stale gpt-4o-mini result shouldn't shadow
    # a fresh gpt-4o one (or vice versa).
    suffix = f"|{model}" if model else ""
    return hashlib.sha256(f"{input_text}{PROMPT_VERSION}{suffix}".encode()).hexdigest()


def _client_for(request: Request, override_model: str | None):
    """Return the global client, or a one-off client pinned to `override_model`.

    Lets callers (notably threat-intel) request the same smart-tier model
    they used for the hunting hypothesis, so the whole insight shares one
    quota pool. Falls back silently to the global client if the secrets
    bag isn't on app.state (legacy code path).
    """
    if not override_model:
        return request.app.state.ai_client
    from copy import copy
    settings = request.app.state.settings
    secrets = getattr(request.app.state, "ai_secrets", {}) or {}
    smart_settings = copy(settings)
    smart_settings.ai_primary_model = override_model
    return build_ai_client(secrets, smart_settings)


@router.post("", response_model=FlowOut, dependencies=[Depends(require_permission("flowviz:read"))])
async def generate_flow(body: FlowRequest, request: Request, session: SessionDep):
    cache_key = _cache_key(body.input, body.model)

    # Cache hit ONLY when the cached entry actually has nodes — an empty
    # output usually means the upstream model failed/quota'd; don't poison
    # the cache with that, let the next call try fresh.
    result = await session.execute(select(Flow).where(Flow.input_hash == cache_key))
    cached = result.scalar_one_or_none()
    if cached and (cached.output or {}).get("nodes"):
        return _to_out(cached)

    client = _client_for(request, body.model)

    # Wrap the LLM call so upstream rate limits / oversize payloads / generic
    # failures surface to the client as proper HTTP statuses with actionable
    # messages, instead of leaking a 500 traceback.
    try:
        output = await _call_ai(client, body.input, body.system)
    except LiteLLMRateLimitError as exc:
        retry = exc.retry_after_seconds
        detail = "AI provider is rate-limited; please retry in a moment."
        if retry:
            detail = f"AI provider is rate-limited (retry in ~{retry}s)."
        headers = {"Retry-After": str(retry)} if retry else None
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail, headers=headers) from exc
    except LiteLLMRequestTooLargeError as exc:
        # Flowviz prompts can hit this if the user pastes a huge description.
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            "Threat description is too long for the configured AI model. "
                            "Shorten the input or switch to a larger model.") from exc
    except LiteLLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            f"AI provider failed: {str(exc)[:200]}") from exc

    # Only persist when the AI actually returned a graph — caching empty
    # results means a transient provider failure permanently shadows the
    # real flow on every retry.
    has_nodes = bool((output or {}).get("nodes"))
    if has_nodes:
        flow = Flow(
            id=uuid.uuid4(),
            input_hash=cache_key,
            input_text=body.input[:10000],
            output=output,
            model_name=client.model,
            generated_at=datetime.now(timezone.utc),
        )
        session.add(flow)
        await session.commit()
        return _to_out(flow)

    # Empty result — return an ephemeral envelope so the client still gets
    # something to render (the threat-intel caller looks for `error` or
    # `output.nodes`), but DON'T commit to the cache.
    return FlowOut(
        id=uuid.uuid4(),
        input_hash=cache_key,
        output=FlowOutput(nodes=[], edges=[]),
        model_name=client.model,
        generated_at=datetime.now(timezone.utc),
    )


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


async def _call_ai(client, input_text: str, system_override: str | None) -> dict:
    from tip_ai import OpenRouterMessage

    system = system_override or DIRECT_FLOW_PROMPT
    # System prompt goes as a proper system message; input as user message
    messages = [
        OpenRouterMessage(role="system", content=system),
        OpenRouterMessage(role="user", content=input_text),
    ]
    # Attack flows are large JSON objects (15+ nodes, 15+ edges); need ample token budget
    raw = await client.chat(messages, response_format_json=True, max_tokens=4000)
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
