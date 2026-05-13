# ── stdlib ──
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

# ── 3rd-party ──
from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# ── local ──
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data.database import get_db, init_db, verify_password
from scripts.jobs import monitor_domain


# ---------------------------------------------------------------------------
#  Config helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    with open(_PROJECT_ROOT / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
#  Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    import asyncio
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from scripts.jobs import check_all_domains

    config = _load_config()
    interval = config.get("scheduler_interval_seconds", 3600)

    async def _run_checks():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, check_all_domains)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_checks, "interval", seconds=interval, id="domain_check")
    scheduler.start()
    print(f"[DomainWatch] Scheduler started — checking every {interval}s")

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

_config_for_secret = _load_config()
_secret = os.environ.get("DOMAINWATCH_SESSION_SECRET") or _config_for_secret.get("session_secret") or secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
#  Fernet-encrypted session middleware
# ---------------------------------------------------------------------------

def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte URL-safe base64 Fernet key from an arbitrary secret."""
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


class EncryptedSessionMiddleware:
    """AES-128 encrypted + HMAC-SHA256 authenticated session cookies via Fernet."""

    def __init__(self, app: ASGIApp, secret_key: str, session_cookie: str = "session",
                 max_age: int = 3600, path: str = "/", same_site: str = "lax",
                 https_only: bool = False):
        self.app = app
        self.fernet = Fernet(_derive_fernet_key(secret_key))
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.path = path
        self.same_site = same_site
        self.https_only = https_only

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        session_data: dict = {}

        # Decrypt existing session cookie
        raw_cookie = connection.cookies.get(self.session_cookie)
        if raw_cookie:
            try:
                decrypted = self.fernet.decrypt(raw_cookie.encode(), ttl=self.max_age)
                session_data = json.loads(decrypted)
            except (InvalidToken, json.JSONDecodeError):
                session_data = {}

        scope["session"] = session_data
        initial_session = dict(session_data)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Only set cookie if session changed
                if scope["session"] != initial_session:
                    headers = MutableHeaders(scope=message)
                    if scope["session"]:
                        encrypted = self.fernet.encrypt(
                            json.dumps(scope["session"]).encode()
                        ).decode()
                        cookie = (
                            f"{self.session_cookie}={encrypted}; path={self.path}; "
                            f"Max-Age={self.max_age}; httponly; samesite={self.same_site}"
                        )
                        if self.https_only:
                            cookie += "; secure"
                        headers.append("set-cookie", cookie)
                    else:
                        # Session cleared — delete cookie
                        headers.append(
                            "set-cookie",
                            f"{self.session_cookie}=; path={self.path}; Max-Age=0; httponly; "
                            f"samesite={self.same_site}",
                        )
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(EncryptedSessionMiddleware, secret_key=_secret, max_age=3600)


# ---------------------------------------------------------------------------
#  Security headers middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        # Remove uvicorn's default server header and set our own
        if "server" in response.headers:
            del response.headers["server"]
        response.headers["server"] = "DomainWatch"
        return response

app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
#  Login rate limiter (per-IP)
# ---------------------------------------------------------------------------

_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_WINDOW = 300  # seconds (5 minutes)
_MAX_TRACKED_IPS = 10_000  # prevent unbounded memory growth

# Server-side session revocation (logout invalidation)
_revoked_sessions: set[str] = set()
_revoked_timestamps: dict[str, float] = {}  # sid -> revocation time
_SESSION_MAX_AGE = 3600  # must match middleware max_age


def _prune_rate_limiter():
    """Evict expired entries and cap total tracked IPs."""
    now = time.time()
    expired = [ip for ip, ts in _login_attempts.items() if all(now - t >= _LOGIN_WINDOW for t in ts)]
    for ip in expired:
        del _login_attempts[ip]
    # Hard cap: if still too large, drop oldest entries
    if len(_login_attempts) > _MAX_TRACKED_IPS:
        sorted_ips = sorted(_login_attempts, key=lambda ip: max(_login_attempts[ip], default=0))
        for ip in sorted_ips[:len(_login_attempts) - _MAX_TRACKED_IPS]:
            del _login_attempts[ip]


def _revoke_session(sid: str):
    """Mark a session ID as revoked."""
    if sid:
        _revoked_sessions.add(sid)
        _revoked_timestamps[sid] = time.time()
    # Prune revocations older than session max_age (they're expired anyway)
    cutoff = time.time() - _SESSION_MAX_AGE
    stale = [s for s, t in _revoked_timestamps.items() if t < cutoff]
    for s in stale:
        _revoked_sessions.discard(s)
        _revoked_timestamps.pop(s, None)


# ---------------------------------------------------------------------------
#  Static files & templates
# ---------------------------------------------------------------------------

SCREENSHOTS_DIR = _PROJECT_ROOT / "data" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")

templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
#  Auth helpers
# ---------------------------------------------------------------------------

def is_logged_in(request: Request) -> bool:
    sid = request.session.get("sid")
    if not sid or sid in _revoked_sessions:
        return False
    user_id = request.session.get("user_id")
    if not user_id:
        return False
    with get_db() as conn:
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    return user is not None


# ---------------------------------------------------------------------------
#  Routes — pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if is_logged_in(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None},
    )


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    # Rate limit check
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    _prune_rate_limiter()
    _login_attempts[client_ip] = [t for t in _login_attempts[client_ip] if now - t < _LOGIN_WINDOW]
    if len(_login_attempts[client_ip]) >= _MAX_LOGIN_ATTEMPTS:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Too many login attempts. Please wait 5 minutes."},
            status_code=429,
        )

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not user or not verify_password(password, user["password"]):
        _login_attempts[client_ip].append(now)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password"},
            status_code=400,
        )

    # Clear rate limit on success
    _login_attempts.pop(client_ip, None)

    # Session regeneration: clear old session, set fresh data
    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["sid"] = secrets.token_hex(16)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)

    with get_db() as conn:
        domains = conn.execute(
            """SELECT d.*, s.name as source_name
               FROM domains d LEFT JOIN sources s ON d.source_id = s.id
               ORDER BY d.id DESC"""
        ).fetchall()
        sources = conn.execute("SELECT * FROM sources ORDER BY name").fetchall()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "username": request.session.get("username"),
            "domains": domains,
            "sources": sources,
        },
    )


_DOMAIN_RE = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
)


@app.post("/domains/add")
def add_domain(request: Request, name: str = Form(...), case_id: str = Form(""), source_id: str = Form("")):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)

    domain_name = name.strip().lower()
    if not domain_name or not _DOMAIN_RE.match(domain_name) or len(domain_name) > 253:
        return RedirectResponse(url="/dashboard", status_code=303)

    # Sanitize case_id: strip whitespace, cap length
    safe_case_id = case_id.strip()[:100]

    now = datetime.now().isoformat()
    try:
        src_id = int(source_id) if source_id.strip() else None
    except (ValueError, TypeError):
        src_id = None

    # Validate source_id exists in DB if provided
    if src_id is not None:
        with get_db() as conn:
            if not conn.execute("SELECT id FROM sources WHERE id = ?", (src_id,)).fetchone():
                src_id = None

    username = request.session.get("username", "")
    new_domain_id = None

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM domains WHERE name = ?",
            (domain_name,),
        ).fetchone()

        if not existing:
            conn.execute(
                """
                INSERT INTO domains (name, case_id, source_id, status, created_at, last_checked, last_modified, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (domain_name, safe_case_id, src_id, "unknown", now, now, now, username),
            )
            entry = conn.execute("SELECT id FROM domains WHERE name = ?", (domain_name,)).fetchone()
            if entry:
                new_domain_id = entry["id"]

    # Start monitoring outside DB context to avoid holding the lock
    if new_domain_id:
        def _monitor():
            try:
                monitor_domain(domain_name, new_domain_id, safe_case_id)
            except Exception as e:
                print(f"[DomainWatch] Background monitor error for {domain_name}: {e}")

        threading.Thread(target=_monitor, daemon=True).start()

    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/status/")
def status(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)

    with get_db() as conn:
        loading = conn.execute(
            "SELECT COUNT(*) as cnt FROM domains WHERE status = 'unknown' AND archived = 0"
        ).fetchone()["cnt"]

    return {"status": "loading" if loading > 0 else "idle"}


@app.post("/domains/archive/{domain_id}")
def archive_domain(request: Request, domain_id: int):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    with get_db() as conn:
        conn.execute("UPDATE domains SET archived = 1 WHERE id = ?", (domain_id,))
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/domains/restore/{domain_id}")
def restore_domain(request: Request, domain_id: int):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    with get_db() as conn:
        conn.execute("UPDATE domains SET archived = 0 WHERE id = ?", (domain_id,))
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/domains/{domain_id}", response_class=HTMLResponse)
def domain_detail(request: Request, domain_id: int):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    _revoke_session(request.session.get("sid"))
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ---------------------------------------------------------------------------
#  JSON API (SPA)
# ---------------------------------------------------------------------------

@app.get("/api/domains")
def api_domains(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT d.*, s.name as source_name
               FROM domains d LEFT JOIN sources s ON d.source_id = s.id
               ORDER BY d.id DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/domains/{domain_id}")
def api_domain_detail(request: Request, domain_id: int):
    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    with get_db() as conn:
        domain = conn.execute(
            """SELECT d.*, s.name as source_name
               FROM domains d LEFT JOIN sources s ON d.source_id = s.id
               WHERE d.id = ?""", (domain_id,)
        ).fetchone()
        if not domain:
            return JSONResponse({"error": "not found"}, status_code=404)
        history = conn.execute(
            "SELECT * FROM domain_history WHERE domain_id = ? ORDER BY changed_at DESC", (domain_id,)
        ).fetchall()
        subdomain_rows = conn.execute(
            """SELECT subdomain, first_seen_at, a_records_json, aaaa_records_json, cname_target,
                      ns_records_json, soa_record, is_delegated, is_resolving,
                      wildcard_match, last_checked_at, last_error
               FROM domain_subdomains
               WHERE domain_id = ?
               ORDER BY first_seen_at DESC""",
            (domain_id,),
        ).fetchall()
        iocs = conn.execute(
            "SELECT ioc_value, ioc_type, first_seen_at FROM domain_iocs WHERE domain_id = ? ORDER BY first_seen_at DESC", (domain_id,)
        ).fetchall()

    details = {}
    if domain["details_json"]:
        try:
            details = json.loads(domain["details_json"])
        except (json.JSONDecodeError, TypeError):
            details = {}
    screenshot_url = None
    if domain["screenshot_path"]:
        screenshot_url = f"/static/screenshots/{Path(domain['screenshot_path']).name}"

    subdomains = []
    for row in subdomain_rows:
        item = dict(row)
        for source_key, target_key in (
            ("a_records_json", "a_records"),
            ("aaaa_records_json", "aaaa_records"),
            ("ns_records_json", "ns_records"),
        ):
            raw_value = item.pop(source_key, None)
            try:
                item[target_key] = json.loads(raw_value) if raw_value else []
            except (json.JSONDecodeError, TypeError):
                item[target_key] = []
        item["is_delegated"] = bool(item.get("is_delegated"))
        item["is_resolving"] = bool(item.get("is_resolving"))
        item["wildcard_match"] = bool(item.get("wildcard_match"))
        subdomains.append(item)

    return {
        "domain": dict(domain),
        "details": details,
        "history": [dict(h) for h in history],
        "subdomains": subdomains,
        "iocs": [dict(i) for i in iocs],
        "screenshot_url": screenshot_url,
    }


@app.get("/api/sources")
def api_sources(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM sources ORDER BY name").fetchall()
    return [dict(r) for r in rows]