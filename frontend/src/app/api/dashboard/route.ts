import { NextRequest, NextResponse } from 'next/server';

/**
 * Dashboard aggregation BFF endpoint.
 * Fans out to multiple backend services in parallel and returns a unified payload
 * so the dashboard renders with one network call.
 */

const NEWS_URL   = process.env.API_NEWS_URL          || 'http://news-collector:8001';
const VULN_URL   = process.env.API_VULN_URL          || 'http://vuln-intel:8002';
const THREAT_URL = process.env.API_THREAT_URL        || 'http://threat-intel:8003';
const IOC_URL    = process.env.API_IOC_URL           || 'http://ioc-collector:8004';
const ACTORS_URL = process.env.API_ACTORS_URL        || 'http://threat-actors:8005';
const SCHED_URL  = process.env.API_SCHEDULER_URL     || 'http://scheduler:8011';
const ORCH_URL   = process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014';

const ALL_SERVICES: { name: string; url: string }[] = [
  { name: 'auth',            url: process.env.API_AUTH_URL          || 'http://auth:8000' },
  { name: 'news-collector',  url: NEWS_URL },
  { name: 'vuln-intel',      url: VULN_URL },
  { name: 'threat-intel',    url: THREAT_URL },
  { name: 'ioc-collector',   url: IOC_URL },
  { name: 'threat-actors',   url: ACTORS_URL },
  { name: 'integrations',    url: process.env.API_INTEGRATIONS_URL  || 'http://integrations:8006' },
  { name: 'cmdb',            url: process.env.API_CMDB_URL          || 'http://cmdb:8007' },
  { name: 'flowviz',         url: process.env.API_FLOWVIZ_URL       || 'http://flowviz:8008' },
  { name: 'asm',             url: process.env.API_ASM_URL           || 'http://asm:8009' },
  { name: 'domainwatch',     url: process.env.API_DOMAINWATCH_URL   || 'http://domainwatch:8010' },
  { name: 'scheduler',       url: SCHED_URL },
  { name: 'secrets',         url: process.env.API_SECRETS_URL       || 'http://secrets:8012' },
  { name: 'indicator-intel', url: process.env.API_INDICATOR_URL     || 'http://indicator-intel:8013' },
  { name: 'orchestrator',    url: ORCH_URL },
];

async function safeFetch(url: string, headers: HeadersInit, label: string): Promise<unknown> {
  try {
    const res = await fetch(url, { headers, signal: AbortSignal.timeout(8_000) });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn(`[dashboard] ${label} failed:`, (err as Error).message);
    return null;
  }
}

export async function GET(req: NextRequest) {
  const auth = req.headers.get('authorization') ?? '';
  const headers: HeadersInit = auth ? { Authorization: auth } : {};

  // Run everything in parallel
  const [
    articles, cves, threats, iocs, actors, runs, briefs, topCVEs, topActors, geo, ...healths
  ] = await Promise.all([
    safeFetch(`${NEWS_URL}/articles?limit=1`,        headers, 'articles'),
    safeFetch(`${VULN_URL}/cves?limit=1`,            headers, 'cves'),
    safeFetch(`${THREAT_URL}/threats?limit=1`,       headers, 'threats'),
    safeFetch(`${IOC_URL}/indicators?limit=1`,       headers, 'indicators'),
    safeFetch(`${ACTORS_URL}/actors?limit=500`,      headers, 'actors'),
    safeFetch(`${SCHED_URL}/runs?limit=10`,          headers, 'runs'),
    safeFetch(`${ORCH_URL}/reports?kind=analysis_cycle&limit=1`, headers, 'briefs'),
    safeFetch(`${ORCH_URL}/relevance/cves?limit=5`,  headers, 'top-cves'),
    safeFetch(`${ORCH_URL}/relevance/actors?limit=5`,headers, 'top-actors'),
    safeFetch(`${ORCH_URL}/reports?kind=geo_prediction&limit=1`, headers, 'geo'),
    ...ALL_SERVICES.map(s => safeFetch(`${s.url}/health`, {}, `health-${s.name}`)),
  ]);

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const totalOrLen = (v: any): number => {
    if (!v) return 0;
    if (typeof v.total === 'number') return v.total;
    if (Array.isArray(v)) return v.length;
    if (Array.isArray(v.items)) return v.items.length;
    return 0;
  };
  const items = (v: any): any[] => {
    if (!v) return [];
    if (Array.isArray(v)) return v;
    if (Array.isArray(v.items)) return v.items;
    return [];
  };

  const healthyCount = healths.filter(h => h !== null).length;

  return NextResponse.json({
    iocs_total:     totalOrLen(iocs),
    cves_total:     totalOrLen(cves),
    threats_total:  totalOrLen(threats),
    articles_total: totalOrLen(articles),
    actors_total:   totalOrLen(actors),
    services_healthy: healthyCount,
    services_total:   ALL_SERVICES.length,
    top_cves: items(topCVEs).slice(0, 5).map((c: any) => ({
      cve_id: c.cve_id,
      severity: c.severity ?? 'unknown',
      cvss_v3_score: c.cvss_v3_score ?? null,
      relevance: c.relevance_score ?? c.relevance ?? 0,
      kev: !!c.kev,
      description: c.description ?? c.rationale ?? null,
    })),
    top_actors: (() => {
      const actorList = items(actors);
      return items(topActors).slice(0, 5).map((a: any) => {
        const actorId = a.actor_id ?? a.id;
        const full = actorList.find((ac: any) => ac.id === actorId);
        return {
          id: actorId,
          name: full?.name ?? a.name ?? 'Unknown actor',
          origin_country: full?.origin_country ?? a.origin_country ?? null,
          likelihood: a.likelihood_score ?? a.likelihood ?? 0,
          target_sectors: full?.target_sectors ?? a.target_sectors ?? [],
          motivation: full?.motivation ?? a.motivation ?? [],
        };
      });
    })(),
    recent_runs: items(runs).slice(0, 10),
    latest_brief: items(briefs)[0] ?? null,
    // Geopolitical outlook (orchestrator runs this daily via /analyze/geo).
    // Payload shape from GEO_PREDICTION_PROMPT: outlook, summary,
    // emerging_threats[{threat,probability,timeframe}], affected_sectors[],
    // recommended_monitoring[]. May be null if the daily job hasn't run yet.
    latest_geo: items(geo)[0] ?? null,
  });
}
