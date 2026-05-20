import { NextRequest, NextResponse } from 'next/server';

/**
 * BFF catch-all proxy.
 * Maps the first path segment to a backend service URL,
 * forwards the request with auth headers intact.
 */

const SERVICE_MAP: Record<string, string> = {
  // Auth
  login:          process.env.API_AUTH_URL          || 'http://auth:8000',
  refresh:        process.env.API_AUTH_URL          || 'http://auth:8000',
  logout:         process.env.API_AUTH_URL          || 'http://auth:8000',
  me:             process.env.API_AUTH_URL          || 'http://auth:8000',
  users:          process.env.API_AUTH_URL          || 'http://auth:8000',
  roles:          process.env.API_AUTH_URL          || 'http://auth:8000',
  sessions:       process.env.API_AUTH_URL          || 'http://auth:8000',
  'service-login':process.env.API_AUTH_URL          || 'http://auth:8000',
  // News
  articles:       process.env.API_NEWS_URL          || 'http://news-collector:8001',
  feeds:          process.env.API_NEWS_URL          || 'http://news-collector:8001',
  // Vuln
  cves:           process.env.API_VULN_URL          || 'http://vuln-intel:8002',
  kev:            process.env.API_VULN_URL          || 'http://vuln-intel:8002',
  // Threat
  threats:        process.env.API_THREAT_URL        || 'http://threat-intel:8003',
  'hibp-breaches':process.env.API_THREAT_URL        || 'http://threat-intel:8003',
  // IOC
  indicators:     process.env.API_IOC_URL           || 'http://ioc-collector:8004',
  // Actors
  actors:         process.env.API_ACTORS_URL        || 'http://threat-actors:8005',
  ransomware:     process.env.API_ACTORS_URL        || 'http://threat-actors:8005',
  tools:          process.env.API_ACTORS_URL        || 'http://threat-actors:8005',
  ttps:           process.env.API_ACTORS_URL        || 'http://threat-actors:8005',
  // Integrations
  wazuh:          process.env.API_INTEGRATIONS_URL  || 'http://integrations:8006',
  misp:           process.env.API_INTEGRATIONS_URL  || 'http://integrations:8006',
  // CMDB
  assets:         process.env.API_CMDB_URL          || 'http://cmdb:8007',
  profile:        process.env.API_CMDB_URL          || 'http://cmdb:8007',
  tags:           process.env.API_CMDB_URL          || 'http://cmdb:8007',
  // Flowviz
  flows:          process.env.API_FLOWVIZ_URL       || 'http://flowviz:8008',
  // ASM
  scopes:         process.env.API_ASM_URL           || 'http://asm:8009',
  targets:        process.env.API_ASM_URL           || 'http://asm:8009',
  findings:       process.env.API_ASM_URL           || 'http://asm:8009',
  scan:           process.env.API_ASM_URL           || 'http://asm:8009',
  // DomainWatch
  domains:        process.env.API_DOMAINWATCH_URL   || 'http://domainwatch:8010',
  check:          process.env.API_DOMAINWATCH_URL   || 'http://domainwatch:8010',
  // Scheduler
  jobs:           process.env.API_SCHEDULER_URL     || 'http://scheduler:8011',
  runs:           process.env.API_SCHEDULER_URL     || 'http://scheduler:8011',
  // Secrets
  secrets:        process.env.API_SECRETS_URL       || 'http://secrets:8012',
  // Indicator Intel
  investigate:    process.env.API_INDICATOR_URL     || 'http://indicator-intel:8013',
  investigations: process.env.API_INDICATOR_URL     || 'http://indicator-intel:8013',
  dorks:          process.env.API_INDICATOR_URL     || 'http://indicator-intel:8013',
  // Orchestrator
  actions:        process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014',
  policies:       process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014',
  notifications:  process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014',
  analyze:        process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014',
  reports:        process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014',
  relevance:      process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014',
  correlations:   process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014',
  ask:            process.env.API_ORCHESTRATOR_URL  || 'http://orchestrator:8014',
  // Health (all services)
  health:         process.env.API_AUTH_URL           || 'http://auth:8000',
};

function resolveUpstream(pathSegments: string[]): { baseUrl: string; backendPath: string } | null {
  const first = pathSegments[0];
  const baseUrl = SERVICE_MAP[first];
  if (!baseUrl) return null;
  // Reconstruct the path: /first/rest/of/path
  const backendPath = '/' + pathSegments.join('/');
  return { baseUrl, backendPath };
}

async function proxyRequest(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const resolved = resolveUpstream(path);

  if (!resolved) {
    return NextResponse.json({ error: 'Unknown API route' }, { status: 404 });
  }

  const { baseUrl, backendPath } = resolved;
  const targetUrl = new URL(backendPath, baseUrl);

  // Forward query params
  req.nextUrl.searchParams.forEach((val, key) => {
    targetUrl.searchParams.set(key, val);
  });

  // Build headers — forward auth + content-type
  const headers: Record<string, string> = {};
  const auth = req.headers.get('authorization');
  if (auth) headers['Authorization'] = auth;
  const ct = req.headers.get('content-type');
  if (ct) headers['Content-Type'] = ct;
  const corr = req.headers.get('x-correlation-id');
  if (corr) headers['X-Correlation-ID'] = corr;

  try {
    const fetchOpts: RequestInit = {
      method: req.method,
      headers,
    };

    if (req.method !== 'GET' && req.method !== 'HEAD') {
      const body = await req.text();
      if (body) fetchOpts.body = body;
    }

    const upstream = await fetch(targetUrl.toString(), fetchOpts);

    // Stream the response back
    const responseHeaders = new Headers();
    upstream.headers.forEach((val, key) => {
      if (!['transfer-encoding', 'content-encoding', 'connection'].includes(key.toLowerCase())) {
        responseHeaders.set(key, val);
      }
    });

    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (err) {
    console.error(`BFF proxy error → ${targetUrl}:`, err);
    return NextResponse.json(
      { error: 'Backend service unavailable', target: targetUrl.toString() },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
