import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_ai import LiteLLMError, LiteLLMRateLimitError, LiteLLMRequestTooLargeError
from tip_auth import require_permission
from tip_common import NotFoundError, resolve_sort

from app.db import get_session
from app.models import CVE, CVEInsight, EPSS, KEV
from app.schemas import (
    AnalystStatusUpdate,
    AnalyzeRequest,
    CVEDetail,
    CVEList,
    CVEOut,
    InsightOut,
    InsightOverrideIn,
    KEVOut,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["cves"])


_CVE_SORT_COLS = {
    "last_modified_at": CVE.last_modified_at,
    "published_at":     CVE.published_at,
    "cve_id":           CVE.cve_id,
    "cvss_v3_score":    CVE.cvss_v3_score,
    "severity":         CVE.severity,
    "analyst_status":   CVE.analyst_status,
}


@router.get(
    "/cves",
    response_model=CVEList,
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def list_cves(
    q: str | None = Query(None, description="Free-text search on CVE-ID or description"),
    severity: str | None = None,
    product: str | None = None,
    since: datetime | None = None,
    kev: bool = False,
    epss_gte: float | None = Query(None, ge=0, le=1),
    include_not_relevant: bool = Query(False),
    sort_by: str | None = Query(None, description=f"One of: {', '.join(sorted(_CVE_SORT_COLS))}"),
    sort_dir: str | None = Query(None, description="asc | desc"),
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> CVEList:
    stmt = select(CVE)
    if not include_not_relevant:
        stmt = stmt.where(CVE.analyst_status != "not_relevant")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(CVE.cve_id.ilike(like), CVE.description.ilike(like)))
    if severity:
        stmt = stmt.where(CVE.severity == severity)
    if since:
        stmt = stmt.where(CVE.last_modified_at >= since)
    if product:
        stmt = stmt.where(CVE.affected_products.cast(str).ilike(f"%{product}%"))
    if kev:
        stmt = stmt.join(KEV, KEV.cve_id == CVE.cve_id)
    if epss_gte is not None:
        stmt = stmt.join(EPSS, EPSS.cve_id == CVE.cve_id).where(EPSS.epss >= epss_gte)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(
        resolve_sort(sort_by, sort_dir, _CVE_SORT_COLS, default="last_modified_at")
    ).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return CVEList(items=[CVEOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/cves/{cve_id}",
    response_model=CVEDetail,
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def get_cve(cve_id: str, session: AsyncSession = Depends(get_session)) -> CVEDetail:
    cve = await session.get(CVE, cve_id)
    if cve is None:
        raise NotFoundError(f"CVE {cve_id} not found")
    epss = await session.get(EPSS, cve_id)
    kev = await session.get(KEV, cve_id)
    out = CVEDetail.model_validate(cve)
    if epss is not None:
        out.epss = float(epss.epss)
        out.epss_percentile = float(epss.percentile)
    if kev is not None:
        out.kev = True
        out.kev_date_added = kev.date_added
        out.kev_ransomware_use = kev.ransomware_use
    return out


@router.get(
    "/kev",
    response_model=list[KEVOut],
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def list_kev(session: AsyncSession = Depends(get_session)) -> list[KEVOut]:
    rows = (
        await session.execute(select(KEV).order_by(KEV.date_added.desc().nullslast()))
    ).scalars().all()
    return [KEVOut.model_validate(r) for r in rows]


@router.patch(
    "/cves/{cve_id}/status",
    response_model=CVEOut,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def update_cve_status(
    cve_id: str,
    body: AnalystStatusUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> CVEOut:
    cve = await session.get(CVE, cve_id)
    if cve is None:
        raise NotFoundError(f"CVE {cve_id} not found")
    old_status = cve.analyst_status
    cve.analyst_status = body.analyst_status
    await session.flush()

    # When marked 'relevant', auto-add affected products to CMDB profile
    if body.analyst_status == "relevant" and old_status != "relevant":
        products = _extract_products_from_cve(cve)
        if products:
            from app.settings import get_settings
            settings = get_settings()
            jwt = getattr(request.app.state, "service_jwt", "") or ""
            for product in products:
                background_tasks.add_task(
                    _auto_add_product, settings.cmdb_url, jwt, "cve", cve_id, product
                )

    return CVEOut.model_validate(cve)


def _extract_products_from_cve(cve: CVE) -> list[str]:
    """Extract product names from CVE affected_products (CPE data).

    Handles both formats:
      - {"cpes": ["cpe:2.3:a:vendor:product:..."]}
      - [{"vendor": "...", "product": "..."}]
    """
    products: list[str] = []
    affected = cve.affected_products
    if not affected:
        return products

    # Handle {"cpes": [...]} format
    cpe_list: list[str] = []
    if isinstance(affected, dict):
        cpe_list = affected.get("cpes", [])
        if not cpe_list:
            # Also check for direct vendor/product in the dict
            v = affected.get("vendor", "")
            p = affected.get("product", "")
            if v and p:
                products.append(f"{v} {p}")
                return products
    elif isinstance(affected, list):
        for entry in affected:
            if isinstance(entry, str):
                cpe_list.append(entry)
            elif isinstance(entry, dict):
                v = entry.get("vendor", "")
                p = entry.get("product", "")
                if v and p and f"{v} {p}" not in products:
                    products.append(f"{v} {p}")

    for cpe in cpe_list:
        if isinstance(cpe, str) and cpe.startswith("cpe:"):
            parts = cpe.split(":")
            if len(parts) >= 5:
                vendor = parts[3]
                product = parts[4]
                if vendor != "*" and product != "*":
                    name = f"{vendor} {product}"
                    if name not in products:
                        products.append(name)

    return products[:5]


async def _auto_add_product(
    cmdb_url: str, jwt: str, resource_type: str, resource_id: str, product_name: str
) -> None:
    """Post an auto-add request to the CMDB service."""
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as c:
            r = await c.post(
                f"{cmdb_url}/profile/auto-add",
                json={
                    "source_resource_type": resource_type,
                    "source_resource_id": resource_id,
                    "product_name": product_name,
                },
            )
            if r.status_code < 300:
                log.info("Auto-added product '%s' from %s %s", product_name, resource_type, resource_id)
            else:
                log.warning("CMDB auto-add returned %d: %s", r.status_code, r.text[:200])
    except Exception:
        log.exception("Failed to auto-add product '%s' to CMDB", product_name)


@router.get(
    "/cves/{cve_id}/insight",
    response_model=InsightOut,
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def get_cve_insight(
    cve_id: str, session: AsyncSession = Depends(get_session)
) -> InsightOut:
    insight = await session.get(CVEInsight, cve_id)
    if insight is None:
        raise NotFoundError(f"no insight for CVE {cve_id}")
    return InsightOut.model_validate(insight)


@router.put(
    "/cves/{cve_id}/insight/override",
    response_model=InsightOut,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def override_cve_insight(
    cve_id: str,
    body: InsightOverrideIn,
    session: AsyncSession = Depends(get_session),
) -> InsightOut:
    insight = await session.get(CVEInsight, cve_id)
    if insight is None:
        raise NotFoundError(f"no insight for CVE {cve_id}")
    insight.analyst_override = body.analyst_override
    await session.flush()
    return InsightOut.model_validate(insight)


async def _fetch_company_profile(settings, jwt: str) -> dict:
    """Pull the company profile from CMDB. Empty dict if anything goes wrong."""
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=8) as c:
            r = await c.get(f"{settings.cmdb_url}/profile/latest")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return {}


def _extract_company_software(profile: dict) -> list[str]:
    """Return a flat list of product names the org runs (for CVE asset matching)."""
    tech = (profile or {}).get("technology") or {}
    sw: list[str] = []
    for key in ("software", "os", "cloud", "security_tools"):
        for item in (tech.get(key) or []):
            if isinstance(item, str) and item.strip():
                sw.append(item.strip())
            elif isinstance(item, dict):
                # Some profile shapes store {vendor, product} dicts
                name = item.get("product") or item.get("name") or ""
                if name:
                    sw.append(str(name).strip())
    return sw


def _match_affected_products(cve_row: CVE, company_software: list[str]) -> list[str]:
    """Compute the intersection between the CVE's affected_products and our stack.

    Both sides are lowercased and substring-matched in either direction so
    "T24" matches "Temenos T24 Core Banking" and vice versa. This intentionally
    over-matches — the LLM gets the final say on relevance via the prompt.
    """
    ap = cve_row.affected_products or {}
    products: list[str] = []
    items = ap.get("items") if isinstance(ap, dict) else ap
    if isinstance(items, list):
        for p in items:
            if isinstance(p, dict):
                name = " ".join(filter(None, [p.get("vendor"), p.get("product")])).strip()
                if name:
                    products.append(name)
            elif isinstance(p, str):
                products.append(p)

    matches: list[str] = []
    sw_lower = [s.lower() for s in company_software]
    for prod in products:
        p_low = prod.lower()
        for sw in sw_lower:
            if not sw:
                continue
            if sw in p_low or p_low in sw:
                matches.append(prod)
                break
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for m in matches:
        if m.lower() in seen:
            continue
        seen.add(m.lower())
        out.append(m)
    return out


@router.post(
    "/cves/{cve_id}/analyze",
    response_model=InsightOut,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def analyze_cve(
    cve_id: str,
    request: Request,
    body: AnalyzeRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Generate the structured AI insight for a single CVE.

    Runs synchronously (~3-8s) and persists the payload to vuln.cve_insights so
    the GET endpoint and the analyst-override flow can read it without another
    round-trip. Returns the persisted InsightOut shape the frontend already
    knows how to render.

    Why not the orchestrator action pipeline? Per-CVE insight is a single LLM
    call against data we already have locally + one CMDB hop. Going through
    /actions/run added latency, never persisted to cve_insights, and made the
    GET endpoint always 404. Doing it inline here keeps the loop tight.
    """
    from app.prompts import CVE_INSIGHT_PROMPT, PROMPT_VERSION
    from app.settings import get_settings
    from tip_ai import generate_structured
    from pydantic import BaseModel

    cve = await session.get(CVE, cve_id)
    if cve is None:
        raise NotFoundError(f"CVE {cve_id} not found")

    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")
    ai = getattr(request.app.state, "ai_client", None)
    if ai is None:
        raise NotFoundError("AI client not configured on vuln-intel")

    # Profile + asset-match pre-computed in code so the LLM doesn't have to
    # guess; it just rationalizes the decision in the rendered output.
    profile = await _fetch_company_profile(settings, jwt)
    company_software = _extract_company_software(profile)
    matched_software = _match_affected_products(cve, company_software)

    # Pull EPSS + KEV companions so the prompt sees them; they live in
    # separate tables (cve_id-keyed).
    epss_row = await session.get(EPSS, cve_id)
    kev_row = await session.get(KEV, cve_id)

    cve_payload = {
        "cve_id": cve.cve_id,
        "description": cve.description,
        "cvss_v3_score": cve.cvss_v3_score,
        "cvss_v3_vector": cve.cvss_v3_vector,
        "severity": cve.severity,
        "cwe": cve.cwe or [],
        "affected_products": cve.affected_products,
        "references": (cve.references or [])[:8],
        "published_at": cve.published_at.isoformat() if cve.published_at else None,
        "last_modified_at": cve.last_modified_at.isoformat() if cve.last_modified_at else None,
        "epss": float(epss_row.epss) if epss_row and epss_row.epss is not None else None,
        "epss_percentile": float(epss_row.percentile) if epss_row and epss_row.percentile is not None else None,
        "kev": bool(kev_row),
        "kev_ransomware_use": bool(kev_row.ransomware_use) if kev_row else False,
        "kev_date_added": kev_row.date_added.isoformat() if kev_row and kev_row.date_added else None,
    }

    # Pydantic schema mirrors the prompt contract — generate_structured will
    # validate and one-shot-repair on bad JSON.
    class ExploitedInWild(BaseModel):
        value: bool
        evidence: str

    class RelevantToUs(BaseModel):
        value: bool
        rationale: str
        matched_assets: list[str] = []

    class CVEInsightPayload(BaseModel):
        description: str
        impact: str
        affected_versions: str
        recommendations: list[str]
        status: str
        exploited_in_the_wild: ExploitedInWild
        relevant_to_us: RelevantToUs
        severity_summary: str

    log.info("cve_analyze_start cve_id=%s matched=%d", cve_id, len(matched_software))
    try:
        result = await generate_structured(
            ai,
            system_prompt=CVE_INSIGHT_PROMPT,
            user_payload={
                "cve": cve_payload,
                "company_profile": {
                    "identity": (profile or {}).get("identity") or {},
                    "technology": (profile or {}).get("technology") or {},
                    "risk": (profile or {}).get("risk") or {},
                },
                "matched_software": matched_software,
            },
            schema=CVEInsightPayload,
            prompt_version=PROMPT_VERSION,
            max_tokens=1500,
        )
    except LiteLLMRateLimitError as exc:
        # Provider daily/minute quota exhausted. Surface as a real 429 so the
        # frontend can show "rate-limited, try again in N s" instead of a
        # generic failure card.
        retry = exc.retry_after_seconds
        detail = "AI provider is rate-limited; please retry shortly."
        if retry:
            detail = f"AI provider is rate-limited (retry in ~{retry}s)."
        headers = {"Retry-After": str(retry)} if retry else None
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail, headers=headers) from exc
    except LiteLLMRequestTooLargeError as exc:
        log.error("cve_analyze_too_large cve_id=%s error=%s", cve_id, exc)
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            "This CVE's data exceeds the AI model's context limit; "
                            "switch to a larger model in Settings.") from exc
    except LiteLLMError as exc:
        log.error("cve_analyze_failed cve_id=%s error=%s", cve_id, exc)
        # 502: upstream AI failure (auth, network, schema), not our bug.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            f"AI provider failed: {str(exc)[:200]}") from exc
    except Exception as exc:
        log.error("cve_analyze_failed cve_id=%s error=%s", cve_id, exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            f"AI insight generation failed: {exc}") from exc

    payload_dict = result.model_dump()
    # Force the matched_assets list to the computed value (LLM might omit/dedup).
    payload_dict["relevant_to_us"]["matched_assets"] = matched_software
    if not matched_software:
        payload_dict["relevant_to_us"]["value"] = False

    # Upsert into cve_insights (preserves any existing analyst_override).
    existing = await session.get(CVEInsight, cve_id)
    now = datetime.now(__import__("datetime").timezone.utc)
    if existing:
        existing.payload = payload_dict
        existing.model_name = ai.model
        existing.prompt_version = PROMPT_VERSION
        existing.generated_at = now
        row = existing
    else:
        row = CVEInsight(
            cve_id=cve_id,
            payload=payload_dict,
            model_name=ai.model,
            prompt_version=PROMPT_VERSION,
            generated_at=now,
        )
        session.add(row)
    await session.commit()
    await session.refresh(row)
    log.info("cve_analyze_done cve_id=%s model=%s", cve_id, ai.model)
    return InsightOut.model_validate(row)
