import httpx
from fastapi import FastAPI

from tip_common import create_service_app

from app.db import close_engine, get_session_factory, init_engine
from app.routes import auth, jwks, roles, sessions, users
from app.seed import seed
from app.security import init_keys
from app.settings import get_settings

settings = get_settings()


async def _fetch_keys(client: httpx.AsyncClient) -> tuple[str, str]:
    resp = await client.post(
        f"{settings.secrets_url}/internal/bootstrap-fetch",
        json={
            "service_name": "auth",
            "bootstrap_token": settings.secrets_bootstrap_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    secrets = data.get("secrets", {})
    return secrets["AUTH_RS256_PRIVATE_KEY"], secrets["AUTH_RS256_PUBLIC_KEY"]


def _build_token_resolver(client: httpx.AsyncClient):
    async def _resolve(svc_name: str) -> str | None:
        secret_name = f"SVC_{svc_name.upper().replace('-', '_')}_BOOTSTRAP_TOKEN"
        resp = await client.post(
            f"{settings.secrets_url}/internal/bootstrap-fetch",
            json={
                "service_name": "auth",
                "bootstrap_token": settings.secrets_bootstrap_token,
                "secret_name": secret_name,
            },
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("value")
    return _resolve


async def _startup(app: FastAPI) -> None:
    if settings.tip_env == "production" and settings.disable_auth:
        raise RuntimeError("DISABLE_AUTH cannot be true in production")

    init_engine(settings)

    async with httpx.AsyncClient(timeout=30.0) as client:
        private_pem, public_pem = await _fetch_keys(client)
        init_keys(private_pem, public_pem)

        resolver = _build_token_resolver(client)
        async with get_session_factory()() as session:
            await seed(session, resolver)


async def _shutdown(app: FastAPI) -> None:
    await close_engine()


app = create_service_app(
    settings=settings,
    title="TIP Auth Service",
    description="JWT issuance, RBAC, sessions, and service identity",
    on_startup=[_startup],
    on_shutdown=[_shutdown],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(sessions.router)
app.include_router(jwks.router)
