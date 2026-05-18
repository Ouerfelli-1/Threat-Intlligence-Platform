"""4-step analysis cycle.

Each step produces structured output independently. A failed step is logged
and skipped; remaining steps continue running.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from tip_ai import OpenRouterClient, generate_structured
from tip_common import get_logger

from app.context import (
    fetch_actors,
    fetch_company_profile,
    fetch_cves,
    fetch_ransomware_victims,
    fetch_trending_signals,
    fetch_wazuh_alerts,
    generate_flow_for_finding,
)
from app.db import get_session_factory
from app.models import ActorLikelihood, Correlation, CveRelevance, Report
from app.prompts import (
    ACTOR_LIKELIHOOD_PROMPT,
    BRIEF_SYNTHESIS_PROMPT,
    CVE_RELEVANCE_PROMPT,
    DETECTION_CORRELATION_PROMPT,
    GEO_PREDICTION_PROMPT,
    PROMPT_VERSION,
)
from app.settings import Settings

logger = get_logger("orchestrator.analysis")


# ─── Step output schemas ───────────────────────────────────────────────────────

class RankedCVE(BaseModel):
    cve_id: str
    relevance_score: float
    rationale: str
    recommended_action: str


class CVERelevanceOutput(BaseModel):
    ranked_cves: list[RankedCVE]


class RankedActor(BaseModel):
    actor_id: str
    actor_name: str
    likelihood_score: float
    ttps_overlap: list[str] = []
    rationale: str


class ActorLikelihoodOutput(BaseModel):
    ranked_actors: list[RankedActor]


class DetectedCorrelation(BaseModel):
    kind: str
    severity: str
    description: str
    alert_ids: list[str] = []
    ioc_values: list[str] = []
    actor_name: str = ""
    recommended_action: str


class CorrelationOutput(BaseModel):
    correlations: list[DetectedCorrelation]


class ExpandedFinding(BaseModel):
    title: str
    summary: str
    attack_flow_input: str
    priority: str


class BriefOutput(BaseModel):
    headline: str
    threat_level: str
    top_3_actions: list[str]
    expanded_findings: list[ExpandedFinding]


class GeoPredictionOutput(BaseModel):
    outlook: str
    summary: str
    emerging_threats: list[dict] = []
    affected_sectors: list[str] = []
    recommended_monitoring: list[str] = []


class AskOutput(BaseModel):
    answer: str
    confidence: str
    supporting_evidence: list[str] = []
    caveats: list[str] = []
    recommended_actions: list[str] = []


# ─── Individual steps ─────────────────────────────────────────────────────────

# Helpers shared across steps — keep token budget tight for gpt-4o-mini (8K cap).
def _shrink_profile(p: dict) -> dict:
    if not isinstance(p, dict):
        return {}
    return {
        "identity": p.get("identity") or {},
        "technology": p.get("technology") or {},
        "risk": p.get("risk") or {},
    }


def _shrink_cve(c: dict) -> dict:
    """Drop fields the LLM doesn't need for relevance ranking."""
    return {
        "cve_id": c.get("cve_id"),
        "cvss_v3_score": c.get("cvss_v3_score"),
        "epss": c.get("epss"),
        "kev": c.get("kev"),
        "kev_ransomware_use": c.get("kev_ransomware_use"),
        "published_at": c.get("published_at"),
        "description": (c.get("description") or "")[:200],
    }


def _shrink_actor(a: dict) -> dict:
    return {
        "id": str(a.get("id", "")),
        "name": a.get("name"),
        "mitre_id": a.get("mitre_id"),
        "origin_country": a.get("origin_country"),
        "motivation": a.get("motivation"),
        "target_sectors": (a.get("target_sectors") or [])[:6],
        "target_countries": (a.get("target_countries") or [])[:6],
        "last_seen": a.get("last_seen"),
    }


async def _step_cve_relevance(
    ai: OpenRouterClient,
    cves: list[dict],
    profile: dict,
    settings: Settings,
) -> CVERelevanceOutput | None:
    try:
        return await generate_structured(
            ai,
            system_prompt=CVE_RELEVANCE_PROMPT,
            user_payload={
                "cves": [_shrink_cve(c) for c in cves[:20]],
                "company_profile": _shrink_profile(profile),
            },
            schema=CVERelevanceOutput,
            prompt_version=PROMPT_VERSION,
            max_tokens=1500,
        )
    except Exception as exc:
        logger.error("step_cve_relevance_failed", error=str(exc))
        return None


async def _step_actor_likelihood(
    ai: OpenRouterClient,
    actors: list[dict],
    victims: list[dict],
    profile: dict,
    settings: Settings,
) -> ActorLikelihoodOutput | None:
    try:
        return await generate_structured(
            ai,
            system_prompt=ACTOR_LIKELIHOOD_PROMPT,
            user_payload={
                "actors": [_shrink_actor(a) for a in actors[:20]],
                "recent_victims": [
                    {"victim_name": v.get("victim_name"), "sector": v.get("sector"),
                     "country": v.get("country"), "disclosed_at": v.get("disclosed_at"),
                     "group_name": v.get("group_name")}
                    for v in victims[:12]
                ],
                "company_profile": _shrink_profile(profile),
            },
            schema=ActorLikelihoodOutput,
            prompt_version=PROMPT_VERSION,
            max_tokens=1500,
        )
    except Exception as exc:
        logger.error("step_actor_likelihood_failed", error=str(exc))
        return None


async def _step_correlation(
    ai: OpenRouterClient,
    alerts: list[dict],
    actors: list[dict],
    profile: dict,
) -> CorrelationOutput | None:
    # Trim aggressively to stay under gpt-4o-mini's 8K request ceiling.
    # Wazuh alert blobs in particular include full rule + payload JSON; just
    # keep the SOC-actionable fields. Actor list shrunk to 15 with TTPs capped.
    trimmed_alerts = [
        {
            "alert_id": a.get("alert_id") or a.get("id"),
            "severity": a.get("severity") or a.get("level"),
            "rule_id": a.get("rule_id"),
            "rule_description": (a.get("rule_description") or a.get("description") or "")[:160],
            "agent_name": a.get("agent_name"),
            "timestamp": a.get("timestamp"),
        }
        for a in alerts[:40]
    ]
    trimmed_actors = [
        {"name": a.get("name"), "ttps": (a.get("ttps") or [])[:8]}
        for a in actors[:15]
    ]
    try:
        return await generate_structured(
            ai,
            system_prompt=DETECTION_CORRELATION_PROMPT,
            user_payload={
                "wazuh_alerts": trimmed_alerts,
                "known_actors": trimmed_actors,
                "company_profile": _shrink_profile(profile),
            },
            schema=CorrelationOutput,
            prompt_version=PROMPT_VERSION,
            max_tokens=1500,
        )
    except Exception as exc:
        logger.error("step_correlation_failed", error=str(exc))
        return None


async def _step_brief(
    ai: OpenRouterClient,
    cve_output: CVERelevanceOutput | None,
    actor_output: ActorLikelihoodOutput | None,
    corr_output: CorrelationOutput | None,
    profile: dict,
    trending: dict | None = None,
) -> BriefOutput | None:
    """Synthesize the daily threat briefing.

    Inputs are two layers:
      * Analysis outputs (cve_relevance, actor_likelihood, correlations) — what
        the platform thinks matters TO US based on the profile.
      * `trending` signals (recent threats/articles/KEV/victims/IOCs from the
        last few days) — what's hot RIGHT NOW across the threat landscape.

    The prompt is instructed to ground the brief in `trending` first (with
    dates + specific names) and use the analysis outputs to filter for
    relevance. This makes the briefing actually read like "what's happening
    today" instead of a static profile summary.
    """
    # Only the top-ranked items add signal to the brief; gpt-4o-mini caps
    # requests at 8K tokens so we trim aggressively.
    def _trim_cve_out(co) -> dict:
        if co is None:
            return {}
        d = co.model_dump()
        d["ranked_cves"] = (d.get("ranked_cves") or [])[:8]
        return d

    def _trim_actor_out(ao) -> dict:
        if ao is None:
            return {}
        d = ao.model_dump()
        d["ranked_actors"] = (d.get("ranked_actors") or [])[:6]
        return d

    try:
        return await generate_structured(
            ai,
            system_prompt=BRIEF_SYNTHESIS_PROMPT,
            user_payload={
                "company_profile": _shrink_profile(profile),
                "trending": trending or {},
                "cve_relevance": _trim_cve_out(cve_output),
                "actor_likelihood": _trim_actor_out(actor_output),
                "correlations": corr_output.model_dump() if corr_output else {},
            },
            schema=BriefOutput,
            prompt_version=PROMPT_VERSION,
            max_tokens=1800,   # leaves ~6K room for input under gpt-4o-mini's 8K ceiling
        )
    except Exception as exc:
        logger.error("step_brief_failed", error=str(exc))
        return None


def _synthesize_degraded_brief(trending: dict) -> dict:
    """Build a non-AI brief from trending data when AI synthesis failed.

    Used when GitHub Models / OpenRouter quotas are exhausted or all steps
    failed for other upstream reasons. Better to show "here are the 8 newest
    KEV CVEs and 12 newest ransomware victims" than a blank card.

    The shape matches what BriefOutput would produce (`headline`,
    `threat_level`, `top_3_actions`, `expanded_findings`) plus a `degraded`
    flag the frontend can check to render a "AI unavailable" banner.
    """
    kev = trending.get("recent_kev_additions") or []
    victims = trending.get("recent_ransomware_victims") or []
    threats = trending.get("recent_threats") or []
    iocs = trending.get("recent_high_confidence_iocs") or []

    # Headline: pick the strongest signal we have.
    if kev:
        first = kev[0]
        headline = (f"{len(kev)} CVE{'s' if len(kev) != 1 else ''} added to CISA KEV recently "
                    f"(top: {first.get('cve_id', '?')})")
        threat_level = "high"
    elif victims:
        first = victims[0]
        headline = (f"{len(victims)} ransomware disclosure{'s' if len(victims) != 1 else ''} "
                    f"in the last week (most recent: {first.get('victim_name', '?')})")
        threat_level = "high"
    elif threats:
        first = threats[0]
        headline = (f"{len(threats)} new threat reports observed recently "
                    f"(top: {(first.get('title') or '')[:60]})")
        threat_level = "medium"
    else:
        headline = "Quiet day — no new high-priority signals in the trending window."
        threat_level = "low"

    actions: list[str] = []
    if kev:
        ids = [c.get("cve_id") for c in kev[:3] if c.get("cve_id")]
        if ids:
            actions.append(f"Review the {len(kev)} recent KEV additions; prioritize: {', '.join(ids)}.")
    if victims:
        sectors = sorted({v.get("sector") for v in victims if v.get("sector")})[:3]
        if sectors:
            actions.append(f"Brief leadership on ransomware activity in: {', '.join(sectors)}.")
    if iocs:
        actions.append(f"Sweep SIEM for the {len(iocs)} new high-confidence IOCs ingested in the last 24h.")
    if not actions:
        actions = ["Nothing actionable in the trending window — keep monitoring."]
    actions = actions[:3]

    # Synthesize up to 3 findings from the most relevant raw signals.
    findings: list[dict] = []
    for c in kev[:2]:
        cid = c.get("cve_id") or "Unknown CVE"
        findings.append({
            "title": f"{cid} added to CISA KEV",
            "summary": (
                f"{cid} (CVSS {c.get('cvss_v3_score', '?')}, EPSS {c.get('epss', '?')}) "
                f"was added to KEV on {c.get('kev_date_added', '?')}. "
                f"{(c.get('description') or '')[:160]}"
            ).strip(),
            "attack_flow_input": f"Exploitation of {cid} against internet-facing infrastructure.",
            "priority": "critical" if c.get("kev_ransomware_use") else "high",
        })
    for v in victims[:1]:
        findings.append({
            "title": f"Ransomware: {v.get('group_name', 'Unknown group')} → {v.get('victim_name', 'unknown victim')}",
            "summary": (
                f"{v.get('group_name', 'Unknown group')} claimed {v.get('victim_name', 'unknown')} "
                f"({v.get('sector', 'sector unknown')}, {v.get('country', 'country unknown')}) "
                f"on {v.get('disclosed_at', 'unknown date')}."
            ),
            "attack_flow_input": (
                f"{v.get('group_name', 'A ransomware group')} compromise of a "
                f"{v.get('sector', 'finance')} organization."
            ),
            "priority": "high",
        })

    return {
        "headline": headline,
        "threat_level": threat_level,
        "top_3_actions": actions,
        "expanded_findings": findings,
        "degraded": True,
        "degraded_reason": (
            "AI synthesis unavailable (quota exhausted, model error, or rate-limited). "
            "This brief was generated from raw trending data without LLM analysis."
        ),
    }


# ─── Full analysis cycle ───────────────────────────────────────────────────────

async def run_analysis_cycle(
    ai: OpenRouterClient,
    settings: Settings,
    service_jwt: str = "",
) -> uuid.UUID:
    """Run the 4-step analysis cycle and return the report ID."""
    logger.info("analysis_cycle_start")

    # Fetch the long-form context (profile + full catalogs) AND the trending
    # signals (recent threats/articles/KEV/victims/IOCs) in one parallel batch.
    # The trending bundle is what gives the brief its "what's hot right now"
    # character — without it the brief is just a static profile summary.
    profile, cves, actors, victims, alerts, trending = await asyncio.gather(
        fetch_company_profile(settings, service_jwt),
        fetch_cves(settings, service_jwt),
        fetch_actors(settings, service_jwt),
        fetch_ransomware_victims(settings, service_jwt),
        fetch_wazuh_alerts(settings, service_jwt),
        fetch_trending_signals(settings, service_jwt),
        return_exceptions=True,
    )
    profile = profile if isinstance(profile, dict) else {}
    cves = cves if isinstance(cves, list) else []
    actors = actors if isinstance(actors, list) else []
    victims = victims if isinstance(victims, list) else []
    alerts = alerts if isinstance(alerts, list) else []
    trending = trending if isinstance(trending, dict) else {}
    logger.info(
        "analysis_cycle_trending_loaded",
        threats=len(trending.get("recent_threats", [])),
        articles=len(trending.get("recent_articles", [])),
        kev_recent=len(trending.get("recent_kev_additions", [])),
        victims_recent=len(trending.get("recent_ransomware_victims", [])),
        iocs_recent=len(trending.get("recent_high_confidence_iocs", [])),
    )

    cve_out = await _step_cve_relevance(ai, cves, profile, settings)
    actor_out = await _step_actor_likelihood(ai, actors, victims, profile, settings)
    corr_out = await _step_correlation(ai, alerts, actors, profile)
    brief_out = await _step_brief(ai, cve_out, actor_out, corr_out, profile, trending)

    # Persist step results
    now = datetime.now(timezone.utc)
    async with get_session_factory()() as session:
        if cve_out:
            for ranked in cve_out.ranked_cves:
                session.add(CveRelevance(
                    cve_id=ranked.cve_id,
                    relevance_score=ranked.relevance_score,
                    rationale=ranked.rationale,
                    scored_at=now,
                ))

        if actor_out:
            for ranked in actor_out.ranked_actors:
                try:
                    actor_uuid = uuid.UUID(ranked.actor_id)
                except ValueError:
                    continue
                session.add(ActorLikelihood(
                    actor_id=actor_uuid,
                    likelihood_score=ranked.likelihood_score,
                    ttps_overlap=ranked.ttps_overlap,
                    rationale=ranked.rationale,
                    scored_at=now,
                ))

        if corr_out:
            for c in corr_out.correlations:
                session.add(Correlation(
                    id=uuid.uuid4(),
                    kind=c.kind,
                    payload=c.model_dump(),
                    detected_at=now,
                ))

        # Enrich brief with attack flows for top findings
        final_payload: dict[str, Any] = {
            "cve_relevance": cve_out.model_dump() if cve_out else None,
            "actor_likelihood": actor_out.model_dump() if actor_out else None,
            "correlations": corr_out.model_dump() if corr_out else None,
            "brief": None,
        }

        if brief_out:
            findings_with_flows = []
            for finding in brief_out.expanded_findings[:3]:
                flow = await generate_flow_for_finding(finding.attack_flow_input, settings, service_jwt)
                findings_with_flows.append({**finding.model_dump(), "attack_flow": flow})
            brief_dict = brief_out.model_dump()
            brief_dict["expanded_findings"] = findings_with_flows
            final_payload["brief"] = brief_dict
        else:
            # AI brief failed (most likely rate-limit / quota / context). Don't
            # leave the dashboard empty — synthesize a "degraded" brief from
            # the trending data we already pulled, so analysts still get the
            # latest hot CVEs / ransomware victims at a glance even when AI is
            # unavailable. Marked degraded=True so the UI can render a banner.
            final_payload["brief"] = _synthesize_degraded_brief(trending)

        report_id = uuid.uuid4()
        session.add(Report(
            id=report_id,
            kind="analysis_cycle",
            payload=final_payload,
            model_name=ai.model,
            prompt_version=PROMPT_VERSION,
            generated_at=now,
        ))
        await session.commit()

    logger.info("analysis_cycle_complete", report_id=str(report_id))
    return report_id


# ─── Geo prediction ────────────────────────────────────────────────────────────

async def run_geo_prediction(
    ai: OpenRouterClient,
    settings: Settings,
    service_jwt: str = "",
) -> uuid.UUID:
    logger.info("geo_prediction_start")
    profile = await fetch_company_profile(settings, service_jwt)
    actors = await fetch_actors(settings, service_jwt)

    try:
        result = await generate_structured(
            ai,
            system_prompt=GEO_PREDICTION_PROMPT,
            user_payload={
                "company_profile": _shrink_profile(profile),
                # Trim to top 15 actors, shrunk to essentials. The full profile
                # blew past the 8K request limit on gpt-4o-mini before.
                "active_actors": [_shrink_actor(a) for a in actors[:15]],
            },
            schema=GeoPredictionOutput,
            prompt_version=PROMPT_VERSION,
            max_tokens=1500,
        )
    except Exception as exc:
        logger.error("geo_prediction_failed", error=str(exc))
        result = None

    now = datetime.now(timezone.utc)
    async with get_session_factory()() as session:
        report_id = uuid.uuid4()
        session.add(Report(
            id=report_id,
            kind="geo_prediction",
            payload=result.model_dump() if result else {"error": "failed"},
            model_name=ai.model,
            prompt_version=PROMPT_VERSION,
            generated_at=now,
        ))
        await session.commit()

    return report_id


# ─── Ad-hoc ask ────────────────────────────────────────────────────────────────

async def run_adhoc_ask(
    ai: OpenRouterClient,
    question: str,
    profile: dict,
    context: dict,
    settings: Settings,
    service_jwt: str = "",
) -> dict[str, Any]:
    """Handle a free-text intelligence question.

    Before calling the LLM we fan out across the platform (actors / articles /
    threats / CVEs / IOCs) using terms extracted from `question`, then inject
    the results as `platform_data`. This is what lets the assistant answer
    "do we have info about Lazarus?" with our actual rows instead of training-
    data trivia. If nothing matches, platform_data is just empty arrays and
    the LLM is instructed to say so plainly.
    """
    from app.context import search_platform
    from app.prompts import ASK_PROMPT

    platform_data: dict[str, list[dict]] = {}
    try:
        platform_data = await search_platform(question, settings, service_jwt)
        totals = {k: len(v) for k, v in platform_data.items()}
        logger.info("adhoc_ask_platform_search", question=question[:120], totals=totals)
    except Exception as exc:
        logger.warning("adhoc_ask_platform_search_failed", error=str(exc))

    from tip_ai import LiteLLMRateLimitError, LiteLLMRequestTooLargeError

    try:
        result = await generate_structured(
            ai,
            system_prompt=ASK_PROMPT,
            user_payload={
                "question": question,
                "company_profile": profile,
                "platform_data": platform_data,
                **context,
            },
            schema=AskOutput,
            prompt_version=PROMPT_VERSION,
            max_tokens=2000,
        )
        out = result.model_dump()
        # Expose the matched IDs so the frontend can render "View source" links
        # without needing a second query.
        out["matched_resources"] = {
            kind: [item.get("id") or item.get("cve_id") for item in items if item.get("id") or item.get("cve_id")]
            for kind, items in platform_data.items()
        }
        return out
    except LiteLLMRateLimitError as exc:
        # Quota error — give the analyst a useful answer instead of an empty
        # "Unable to process request" string. They can still see which
        # platform resources we matched against the question.
        logger.warning("adhoc_ask_rate_limited", retry_after=exc.retry_after_seconds)
        retry = f" Try again in ~{exc.retry_after_seconds}s." if exc.retry_after_seconds else ""
        return {
            "answer": (
                "AI provider is rate-limited right now, but I found these matching "
                f"records in the platform for your question (counts below).{retry}"
            ),
            "confidence": "low",
            "supporting_evidence": [
                f"{k}: {len(v)} match{'es' if len(v)!=1 else ''}"
                for k, v in platform_data.items() if v
            ],
            "caveats": ["Rate-limited AI response — try again once quota resets."],
            "recommended_actions": [],
            "rate_limited": True,
            "retry_after_seconds": exc.retry_after_seconds,
            "matched_resources": {
                kind: [item.get("id") or item.get("cve_id") for item in items if item.get("id") or item.get("cve_id")]
                for kind, items in platform_data.items()
            },
        }
    except LiteLLMRequestTooLargeError as exc:
        logger.warning("adhoc_ask_too_large", error=str(exc))
        return {
            "answer": "Your question matched too many platform records to fit in one AI request. "
                      "Try narrowing it (mention specific actor names, CVE ids, or dates).",
            "confidence": "low",
            "supporting_evidence": [],
            "caveats": ["Prompt exceeded the AI model's context window."],
            "recommended_actions": [],
        }
    except Exception as exc:
        logger.error("adhoc_ask_failed", error=str(exc))
        return {"answer": "Unable to process request", "confidence": "low", "error": str(exc)}
