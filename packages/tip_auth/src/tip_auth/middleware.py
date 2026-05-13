from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from tip_common.logging_setup import get_logger

logger = get_logger("tip_auth")


@dataclass
class AuthContext:
    subject: str
    kind: str
    perms: set[str] = field(default_factory=set)
    role: str | None = None
    raw_claims: dict | None = None

    def has(self, *required: str) -> bool:
        return all(p in self.perms for p in required)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Validates RS256 JWTs locally with the public key. Skips when disabled.

    If `public_key` is empty at construction time, the key is resolved lazily from
    `request.app.state.auth_public_key` per request. This sidesteps the timing problem
    where the middleware is added at module import but the key is fetched in the
    async startup hook.
    """

    def __init__(
        self,
        app,
        *,
        public_key: str | None = None,
        disable_auth: bool,
        tip_env: str,
        open_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._public_key = public_key or ""
        self._disable_auth = disable_auth
        self._tip_env = tip_env
        self._open_paths = set(
            (open_paths or [])
            + ["/health", "/docs", "/openapi.json", "/redoc", "/health/sources"]
        )
        if disable_auth and tip_env == "production":
            raise RuntimeError(
                "DISABLE_AUTH=true is forbidden when TIP_ENV=production. Refusing to start."
            )

    def _resolve_public_key(self, request: Request) -> str:
        if self._public_key:
            return self._public_key
        return getattr(request.app.state, "auth_public_key", "") or ""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if self._disable_auth or path in self._open_paths or path.startswith("/internal/bootstrap"):
            if self._disable_auth:
                request.state.auth = AuthContext(
                    subject="dev:anonymous", kind="dev", perms={"*"}
                )
            return await call_next(request)
        token = self._extract_bearer(request)
        if token is None:
            return _unauthorized("missing bearer token")
        public_key = self._resolve_public_key(request)
        if not public_key:
            return _unauthorized("auth public key not yet available")
        try:
            claims = jwt.decode(token, public_key, algorithms=["RS256"])
        except jwt.PyJWTError as e:
            return _unauthorized(f"invalid token: {e}")
        ctx = AuthContext(
            subject=str(claims.get("sub", "")),
            kind=str(claims.get("kind", "user")),
            perms=set(claims.get("perms", []) or []),
            role=claims.get("role"),
            raw_claims=claims,
        )
        request.state.auth = ctx
        return await call_next(request)

    @staticmethod
    def _extract_bearer(request: Request) -> str | None:
        header = request.headers.get("Authorization")
        if not header or not header.lower().startswith("bearer "):
            return None
        return header[7:].strip()


def _unauthorized(detail: str) -> Response:
    return Response(
        content=f'{{"code":"unauthorized","message":"{detail}"}}',
        status_code=status.HTTP_401_UNAUTHORIZED,
        media_type="application/json",
    )


def current_user(request: Request) -> AuthContext:
    ctx: AuthContext | None = getattr(request.state, "auth", None)
    if ctx is None:
        raise HTTPException(status_code=401, detail="missing auth context")
    return ctx


def require_permission(*permissions: str):
    def _dep(ctx: AuthContext = Depends(current_user)) -> AuthContext:
        if "*" in ctx.perms:
            return ctx
        missing = [p for p in permissions if p not in ctx.perms]
        if missing:
            raise HTTPException(status_code=403, detail=f"missing permissions: {missing}")
        return ctx

    return _dep
