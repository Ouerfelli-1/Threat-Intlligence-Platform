from fastapi import FastAPI

from tip_auth import JWTAuthMiddleware
from tip_common import create_service_app, wire_auth

from app.db import close_engine, init_engine
from app.routes import assets, profile, tags
from app.settings import get_settings

settings = get_settings()


async def _startup(app: FastAPI) -> None:
    init_engine(settings)
    await wire_auth(app, settings, settings.service_name)


async def _shutdown(_: FastAPI) -> None:
    await close_engine()


app = create_service_app(
    settings=settings,
    title="TIP CMDB",
    description="Asset inventory + versioned company profile",
    on_startup=[_startup],
    on_shutdown=[_shutdown],
)

app.add_middleware(
    JWTAuthMiddleware,
    public_key=settings.auth_public_key,
    disable_auth=settings.disable_auth,
    tip_env=settings.tip_env,
)

app.include_router(assets.router)
app.include_router(profile.router)
app.include_router(tags.router)
