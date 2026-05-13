import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

HEADER = "X-Correlation-ID"


def get_correlation_id() -> str | None:
    return correlation_id_var.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(HEADER)
        cid = incoming or uuid.uuid4().hex
        token = correlation_id_var.set(cid)
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers[HEADER] = cid
        return response
