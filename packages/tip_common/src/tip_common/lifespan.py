from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

Hook = Callable[[FastAPI], Awaitable[None]]


def build_lifespan(
    *,
    on_startup: list[Hook] | None = None,
    on_shutdown: list[Hook] | None = None,
):
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

    return lifespan
