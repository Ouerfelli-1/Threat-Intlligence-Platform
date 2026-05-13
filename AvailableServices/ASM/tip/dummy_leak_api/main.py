"""
Dummy Data Leak API – POC endpoint for simulating a dark-web
monitoring feed.  Pre-loaded with sample leaks; new ones can be
POSTed at runtime for demo purposes.
"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Dummy Leak API",
    description="POC endpoint for simulating data-leak feeds",
    version="1.0.0",
)

# ── Sample data ──────────────────────────────────────────────────

LEAKS: List[Dict] = [
    {
        "id": "leak-001",
        "source": "DarkMarket Forums",
        "type": "credentials",
        "discovered_date": "2026-02-10T10:00:00Z",
        "affected_domains": ["acmecorp.com", "mail.acmecorp.com"],
        "affected_emails": [
            "admin@acmecorp.com",
            "ceo@acmecorp.com",
            "hr@acmecorp.com",
        ],
        "record_count": 1500,
        "contains_passwords": True,
        "contains_pii": False,
        "severity": "HIGH",
        "sample": [
            {"email": "admin@acmecorp.com", "password_hash": "5f4dcc3b5aa765d61d8327deb882cf99"},
            {"email": "ceo@acmecorp.com", "password_hash": "e99a18c428cb38d5f260853678922e03"},
        ],
    },
    {
        "id": "leak-002",
        "source": "Paste Site",
        "type": "database_dump",
        "discovered_date": "2026-02-15T14:30:00Z",
        "affected_domains": ["acmecorp.com"],
        "affected_emails": ["dev@acmecorp.com", "ops@acmecorp.com"],
        "record_count": 5000,
        "contains_passwords": True,
        "contains_pii": True,
        "severity": "CRITICAL",
        "sample": [
            {"name": "Jane Doe", "email": "dev@acmecorp.com", "ssn_last4": "5678"},
        ],
    },
    {
        "id": "leak-003",
        "source": "Telegram Channel",
        "type": "credentials",
        "discovered_date": "2026-02-20T08:15:00Z",
        "affected_domains": ["widgets-inc.io", "api.widgets-inc.io"],
        "affected_emails": [
            "support@widgets-inc.io",
            "billing@widgets-inc.io",
        ],
        "record_count": 320,
        "contains_passwords": True,
        "contains_pii": False,
        "severity": "MEDIUM",
        "sample": [
            {"email": "support@widgets-inc.io", "password_hash": "ab56b4d92b40713acc5af89985d4b786"},
        ],
    },
    {
        "id": "leak-004",
        "source": "Ransomware Blog",
        "type": "documents",
        "discovered_date": "2026-02-22T19:45:00Z",
        "affected_domains": ["globalbank.example.com"],
        "affected_emails": ["ciso@globalbank.example.com"],
        "record_count": 120,
        "contains_passwords": False,
        "contains_pii": True,
        "severity": "HIGH",
        "sample": [
            {"filename": "employee_list_2025.xlsx", "size_kb": 2048},
        ],
    },
    {
        "id": "leak-005",
        "source": "Dark Web Market",
        "type": "credentials",
        "discovered_date": "2026-02-24T12:00:00Z",
        "affected_domains": ["testhost.local"],
        "affected_emails": ["root@testhost.local"],
        "record_count": 50,
        "contains_passwords": True,
        "contains_pii": False,
        "severity": "LOW",
        "sample": [],
    },
]


# ── Pydantic schemas ─────────────────────────────────────────────

class LeakQuery(BaseModel):
    domains: Optional[List[str]] = None
    since: Optional[str] = None  # ISO-8601


class NewLeak(BaseModel):
    source: str
    type: str
    affected_domains: List[str]
    affected_emails: List[str] = []
    record_count: int = 0
    contains_passwords: bool = False
    contains_pii: bool = False
    severity: str = "MEDIUM"
    sample: Optional[List[Dict]] = None


# ── Endpoints ────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "service": "Dummy Leak API", "version": "1.0.0"}


@app.get("/api/v1/leaks")
def get_all_leaks():
    return {"leaks": LEAKS, "total": len(LEAKS)}


@app.get("/api/v1/leaks/{leak_id}")
def get_leak(leak_id: str):
    for leak in LEAKS:
        if leak["id"] == leak_id:
            return leak
    raise HTTPException(status_code=404, detail="Leak not found")


@app.post("/api/v1/leaks/search")
def search_leaks(query: LeakQuery):
    results = list(LEAKS)

    if query.domains:
        results = [
            l
            for l in results
            if any(d in l.get("affected_domains", []) for d in query.domains)
        ]

    if query.since:
        try:
            since_dt = datetime.fromisoformat(query.since.replace("Z", "+00:00"))
            results = [
                l
                for l in results
                if datetime.fromisoformat(
                    l["discovered_date"].replace("Z", "+00:00")
                )
                >= since_dt
            ]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'since' date format")

    return {"leaks": results, "total": len(results)}


@app.post("/api/v1/leaks", status_code=201)
def add_leak(leak: NewLeak):
    new = leak.model_dump()
    new["id"] = f"leak-{len(LEAKS) + 1:03d}"
    new["discovered_date"] = datetime.utcnow().isoformat() + "Z"
    LEAKS.append(new)
    return {"status": "created", "leak": new}


# ── entrypoint ───────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
