from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tip_common.correlation import CorrelationIdMiddleware
from tip_common.errors import register_error_handlers
from tip_common.logging_setup import configure_logging
from tip_common.settings import BaseServiceSettings


Hook = Callable[[FastAPI], Awaitable[None]]


def create_service_app(
    *,
    settings: BaseServiceSettings,
    title: str,
    description: str = "",
    on_startup: list[Hook] | None = None,
    on_shutdown: list[Hook] | None = None,
) -> FastAPI:
    """Create a FastAPI app with logging, correlation IDs, and error handlers wired in.

    Auth middleware is NOT added here — each service installs it conditionally so the
    public key can be fetched at startup rather than at import time.
    """
    configure_logging(settings.service_name, settings.log_level)

    startup_hooks = on_startup or []
    shutdown_hooks = on_shutdown or []

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for hook in startup_hooks:
            await hook(app)
        try:
            yield
        finally:
            for hook in reversed(shutdown_hooks):
                try:
                    await hook(app)
                except Exception:
                    pass

    app = FastAPI(
        title=title,
        description=description,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return app
