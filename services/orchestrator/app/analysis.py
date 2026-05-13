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
            user_payload={"cves": cves[:50], "company_profile": profile},
            schema=CVERelevanceOutput,
            prompt_version=PROMPT_VERSION,
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
                "actors": actors[:50],
                "recent_victims": victims[:20],
                "company_profile": profile,
            },
            schema=ActorLikelihoodOutput,
            prompt_version=PROMPT_VERSION,
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
    try:
        return await generate_structured(
            ai,
            system_prompt=DETECTION_CORRELATION_PROMPT,
            user_payload={
                "wazuh_alerts": alerts[:100],
                "known_actors": [{"name": a.get("name"), "ttps": a.get("ttps", [])} for a in actors[:20]],
                "company_profile": profile,
            },
            schema=CorrelationOutput,
            prompt_version=PROMPT_VERSION,
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
) -> BriefOutput | None:
    try:
        return await generate_structured(
            ai,
            system_prompt=BRIEF_SYNTHESIS_PROMPT,
            user_payload={
                "company_profile": profile,
                "cve_relevance": cve_output.model_dump() if cve_output else {},
                "actor_likelihood": actor_output.model_dump() if actor_output else {},
                "correlations": corr_output.model_dump() if corr_output else {},
            },
            schema=BriefOutput,
            prompt_version=PROMPT_VERSION,
        )
    except Exception as exc:
        logger.error("step_brief_failed", error=str(exc))
        return None


# ─── Full analysis cycle ───────────────────────────────────────────────────────

async def run_analysis_cycle(
    ai: OpenRouterClient,
    settings: Settings,
    service_jwt: str = "",
) -> uuid.UUID:
    """Run the 4-step analysis cycle and return the report ID."""
    logger.info("analysis_cycle_start")

    profile, cves, actors, victims, alerts = await asyncio.gather(
        fetch_company_profile(settings, service_jwt),
        fetch_cves(settings, service_jwt),
        fetch_actors(settings, service_jwt),
        fetch_ransomware_victims(settings, service_jwt),
        fetch_wazuh_alerts(settings, service_jwt),
        return_exceptions=True,
    )
    profile = profile if isinstance(profile, dict) else {}
    cves = cves if isinstance(cves, list) else []
    actors = actors if isinstance(actors, list) else []
    victims = victims if isinstance(victims, list) else []
    alerts = alerts if isinstance(alerts, list) else []

    cve_out = await _step_cve_relevance(ai, cves, profile, settings)
    actor_out = await _step_actor_likelihood(ai, actors, victims, profile, settings)
    corr_out = await _step_correlation(ai, alerts, actors, profile)
    brief_out = await _step_brief(ai, cve_out, actor_out, corr_out, profile)

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
            user_payload={"company_profile": profile, "active_actors": actors[:30]},
            schema=GeoPredictionOutput,
            prompt_version=PROMPT_VERSION,
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
) -> dict[str, Any]:
    from app.prompts import ASK_PROMPT
    try:
        result = await generate_structured(
            ai,
            system_prompt=ASK_PROMPT,
            user_payload={"question": question, "company_profile": profile, **context},
            schema=AskOutput,
            prompt_version=PROMPT_VERSION,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("adhoc_ask_failed", error=str(exc))
        return {"answer": "Unable to process request", "confidence": "low", "error": str(exc)}
