from fastapi import FastAPI

from tip_auth import JWTAuthMiddleware
from tip_common import create_service_app

from app.crypto import build_fernet
from app.db import close_engine, get_session_factory, init_engine
from app.routes import bootstrap, secrets
from app.settings import get_settings

settings = get_settings()

if not settings.fernet_key:
    raise RuntimeError("FERNET_KEY is required for the secrets service")


async def _startup(app: FastAPI) -> None:
    init_engine(settings)
    app.state.fernet = build_fernet(settings.fernet_key)
    app.state.session_factory = get_session_factory()


async def _shutdown(app: FastAPI) -> None:
    await close_engine()


app = create_service_app(
    settings=settings,
    title="TIP Secrets",
    description="Fernet-encrypted credential vault with access logging",
    on_startup=[_startup],
    on_shutdown=[_shutdown],
)
app.add_middleware(
    JWTAuthMiddleware,
    public_key=settings.auth_public_key,
    disable_auth=settings.disable_auth,
    tip_env=settings.tip_env,
)

app.include_router(secrets.router)
app.include_router(bootstrap.router)
