from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class TIPError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(TIPError):
    status_code = 404
    code = "not_found"


class ConflictError(TIPError):
    status_code = 409
    code = "conflict"


class ValidationError(TIPError):
    status_code = 422
    code = "validation_error"


class UpstreamError(TIPError):
    status_code = 502
    code = "upstream_error"


async def _tip_error_handler(_: Request, exc: TIPError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(TIPError, _tip_error_handler)
