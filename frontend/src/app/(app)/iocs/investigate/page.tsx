'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Flag from '@/components/shared/Flag';
import Bar from '@/components/shared/Bar';
import {
  Refresh, Download, Sparkles, AlertTriangle, Globe, Server, Shield,
  FileText, Crosshair, Users, Network, Search, Plus, Activity,
  ChevronDown, ChevronRight, ExternalLink, Check, Play,
} from '@/components/icons';
import { useStore } from '@/lib/store';
import { useList } from '@/lib/hooks';
import { api } from '@/lib/api';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface Investigation {
  id: string;
  indicator_type: string;
  normalized_value: string;
  raw_value: string;
  status: string;
  verdict: string | null;
  confidence: number | null;
  risk_score: number | null;
  summary: string | null;
  payload: Record<string, any> | null;
  model_name: string | null;
  investigated_at: string;
  duration_ms: number | null;
}

/* --- helpers --------------------------------------------------------------- */

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function riskColor(score: number | null) {
  if (score == null) return '#8b949e';
  if (score >= 80) return '#f85149';
  if (score >= 50) return '#d29922';
  if (score >= 30) return '#2dd4bf';
  return '#3fb950';
}

function verdictColor(v: string | null) {
  switch ((v ?? '').toLowerCase()) {
    case 'malicious':  return '#f85149';
    case 'suspicious': return '#d29922';
    case 'benign': case 'clean': return '#3fb950';
    default:           return '#8b949e';
  }
}

function verdictBg(v: string | null) {
  switch ((v ?? '').toLowerCase()) {
    case 'malicious':  return 'rgba(248,81,73,0.1)';
    case 'suspicious': return 'rgba(210,153,34,0.1)';
    case 'benign': case 'clean': return 'rgba(63,185,80,0.08)';
    default:           return 'rgba(139,148,158,0.08)';
  }
}

function inferType(v: string): string {
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(v)) return 'ip';
  return 'domain';
}

/* --- small UI primitives --------------------------------------------------- */

function Sec({
  icon: Ic, title, badge, danger, children,
}: {
  icon: React.FC<{ s?: number; style?: React.CSSProperties }>;
  title: string;
  badge?: React.ReactNode;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="card" style={{ marginBottom: 10, ...(danger ? { border: '1px solid rgba(248,81,73,0.35)' } : {}) }}>
      <div className="card-h" style={danger ? { background: 'rgba(248,81,73,0.04)', borderBottom: '1px solid rgba(248,81,73,0.15)' } : {}}>
        <Ic s={13} style={danger ? { color: '#f85149' } : {}} />
        <div className="t" style={danger ? { color: '#f85149' } : {}}>{title}</div>
        {badge && <span style={{ fontSize: 10.5, color: 'var(--text-4)', marginLeft: 4 }}>{badge}</span>}
      </div>
      {children}
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  if (v == null || v === '' || (Array.isArray(v) && v.length === 0)) return null;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--border-soft)' }}>
      <div style={{ fontSize: 11, color: 'var(--text-4)' }}>{k}</div>
      <div style={{ fontSize: 12, color: 'var(--text-2)', fontFamily: 'var(--mono)', wordBreak: 'break-all' }}>{v}</div>
    </div>
  );
}

function Tag({ children, color }: { children: React.ReactNode; color?: string }) {
  if (color) {
    return (
      <span className="mono" style={{
        fontSize: 11, padding: '2px 6px', borderRadius: 4,
        background: `${color}1f`, border: `1px solid ${color}3f`, color,
      }}>{children}</span>
    );
  }
  return <span className="tag" style={{ fontSize: 10.5 }}>{children}</span>;
}

/* --- AI panel (collapsed, on-demand) -------------------------------------- */

function AIPanel({
  inv, onRequest, requesting, requestError,
}: {
  inv: Investigation;
  onRequest: () => void;
  requesting: boolean;
  requestError: string | null;
}) {
  const [open, setOpen] = useState(false);
  const ai = (inv.payload?.ai_result ?? {}) as Record<string, any>;
  const verdict = inv.verdict ?? ai.verdict ?? null;
  const riskScore = inv.risk_score ?? ai.risk_score ?? null;
  const summary = inv.summary ?? ai.summary ?? null;
  const ttps: string[] = Array.isArray(ai.ttps) ? ai.ttps : [];
  const actions: string[] = Array.isArray(ai.recommended_actions) ? ai.recommended_actions : [];
  const aiAvailable = !!(verdict || summary || ttps.length > 0);

  return (
    <div className="card" style={{ marginBottom: 10, border: open ? '1px solid rgba(88,166,255,0.3)' : '1px solid var(--border)' }}>
      <div className="card-h" style={{ cursor: 'pointer' }} onClick={() => setOpen((v) => !v)}>
        <Sparkles s={13} style={{ color: 'var(--accent)' }} />
        <div className="t" style={{ color: 'var(--accent)' }}>AI Analysis</div>
        <span style={{ fontSize: 11, color: 'var(--text-4)', marginLeft: 4 }}>
          {aiAvailable ? '— click to view AI verdict & recommendations' : '— not run yet · click to run AI analysis'}
        </span>
        <div style={{ marginLeft: 'auto' }}>{open ? <ChevronDown s={13} /> : <ChevronRight s={13} />}</div>
      </div>

      {open && (
        <div style={{ padding: '14px 16px' }}>
          {!aiAvailable && (
            <div style={{ marginBottom: 14, padding: '12px 14px', background: 'var(--bg-page)', borderRadius: 8, fontSize: 12.5, color: 'var(--text-3)' }}>
              No AI verdict has been generated for this investigation yet. The passive enrichment
              above is the unbiased view. Click <strong>Run AI Analysis</strong> to ask the LLM to
              synthesize a verdict and recommended actions from the collected findings — this uses
              OpenRouter tokens.
            </div>
          )}

          {verdict && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16, padding: '12px 14px', borderRadius: 8, background: verdictBg(verdict), border: `1px solid ${verdictColor(verdict)}40` }}>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-4)', marginBottom: 3 }}>Verdict</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: verdictColor(verdict), textTransform: 'uppercase', letterSpacing: '0.05em' }}>{verdict}</div>
              </div>
              {riskScore != null && (
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', marginBottom: 3 }}>Risk score</div>
                  <div className="mono" style={{ fontSize: 20, fontWeight: 700, color: riskColor(riskScore) }}>
                    {riskScore}<span style={{ fontSize: 12, color: 'var(--text-4)' }}>/100</span>
                  </div>
                </div>
              )}
              {inv.model_name && (
                <div style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-4)' }}>{inv.model_name}</div>
              )}
            </div>
          )}

          {summary && (
            <div style={{ marginBottom: 14, padding: '10px 12px', background: 'var(--bg-page)', borderRadius: 6, fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.7 }}>
              {summary}
            </div>
          )}

          {ttps.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>MITRE ATT&amp;CK Techniques</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {ttps.map((t) => <Tag key={t} color="#2dd4bf">{t}</Tag>)}
              </div>
            </div>
          )}

          {actions.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Recommended Actions</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {actions.map((a, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>
                    <span style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 1 }}>{'>'}</span>{a}
                  </div>
                ))}
              </div>
            </div>
          )}

          {requestError && (
            <div style={{ marginBottom: 10, padding: '8px 10px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>
              {requestError}
            </div>
          )}

          <button className="btn primary sm" onClick={onRequest} disabled={requesting}>
            {requesting
              ? <><Refresh s={11} style={{ animation: 'spin 1s linear infinite' }} />Running AI analysis…</>
              : <><Sparkles s={11} />{aiAvailable ? 'Re-run AI analysis' : 'Run AI analysis'}</>}
          </button>
        </div>
      )}
    </div>
  );
}

/* --- main page ------------------------------------------------------------ */

const SOURCE_TILES_IP = [
  'DNS · A/AAAA/MX/PTR', 'ip-api · Geo', 'Shodan · Ports + CVEs', 'AbuseIPDB · Reputation',
  'crt.sh · Certificates',  'WHOIS / RDAP',    'IOC Library lookup',   'Threat actor cross-ref',
  'Article mentions',       'IntelOwl (optional)',
];
const SOURCE_TILES_DOMAIN = [
  'DNS records · A/MX/NS/TXT', 'Passive DNS · HackerTarget',
  'crt.sh · Certificates',     'WHOIS / RDAP',
  'A-record IP enrichment',    'IOC Library lookup',
  'Threat actor cross-ref',    'Article mentions',
  'IntelOwl (optional)',
];


/* ── Dorking panel ─────────────────────────────────────────────────────────
 * Collapsed by default. When opened, fetches the catalog once and lets
 * the analyst pick categories then fires POST /dorks/run. Results are
 * grouped by category with the dork query that surfaced each link.
 */
interface DorkCatalogCategory { key: string; label: string; description: string; dorks: string[]; }
interface DorkCatalog { target_types: Record<string, Record<string, DorkCatalogCategory>>; }
interface DorkFinding { id: string; category: string; dork: string; title: string; url: string; snippet: string; source: string; discovered_at: string; }
interface DorkRun     { id: string; target: string; target_type: string; backend: string; status: string; total_findings: number; error_detail: string | null; started_at: string; finished_at: string | null; findings: DorkFinding[]; }

function DorksPanel({ target, targetType }: { target: string; targetType: string }) {
  const [open, setOpen] = useState(false);
  const [catalog, setCatalog] = useState<DorkCatalog | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<DorkRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Resolve which target_type to use for the dork catalog. We accept
  // "ip" / "domain" from the parent investigation; UI lets the analyst
  // override (e.g. treat a query that looks like an IP as a "company"
  // when investigating an org name).
  const effectiveType = (targetType === 'ip' || targetType === 'email' || targetType === 'company')
    ? targetType : 'domain';

  // Lazy-load catalog the first time we open.
  const ensureCatalog = useCallback(async () => {
    if (catalog) return;
    try {
      const data = await api.get<DorkCatalog>('/dorks/catalog');
      setCatalog(data);
      // Default selection: every category for the resolved type.
      const cats = Object.keys(data.target_types[effectiveType] ?? {});
      setSelected(new Set(cats));
    } catch (e) {
      setError(String(e));
    }
  }, [catalog, effectiveType]);

  useEffect(() => { if (open) ensureCatalog(); }, [open, ensureCatalog]);

  const toggleCat = (k: string) => {
    setSelected(s => {
      const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n;
    });
  };

  const runDorks = async () => {
    setRunning(true); setError(null); setRun(null);
    try {
      const body = {
        target, target_type: effectiveType,
        categories: Array.from(selected),
        limit_per_dork: 5,
      };
      const result = await api.post<DorkRun>('/dorks/run', body);
      setRun(result);
    } catch (e) {
      setError(String(e));
    } finally { setRunning(false); }
  };

  const cats = catalog?.target_types[effectiveType] ?? {};
  // Group findings by category for display.
  const grouped: Record<string, DorkFinding[]> = {};
  (run?.findings ?? []).forEach(f => {
    (grouped[f.category] = grouped[f.category] || []).push(f);
  });

  return (
    <div className="card" style={{ marginBottom: 10, border: open ? '1px solid rgba(45,212,191,0.3)' : '1px solid var(--border)' }}>
      <div className="card-h" style={{ cursor: 'pointer' }} onClick={() => setOpen(v => !v)}>
        <Search s={13} style={{ color: 'var(--accent)' }} />
        <div className="t" style={{ color: 'var(--accent)' }}>Google dorking</div>
        <span style={{ fontSize: 11, color: 'var(--text-4)', marginLeft: 4 }}>
          {run ? `— ${run.total_findings} finding${run.total_findings === 1 ? '' : 's'} via ${run.backend}` :
                 `— search engines (Google + DuckDuckGo fallback) targeting ${effectiveType}`}
        </span>
        <div style={{ marginLeft: 'auto' }}>{open ? <ChevronDown s={13} /> : <ChevronRight s={13} />}</div>
      </div>

      {open && (
        <div style={{ padding: '14px 16px' }}>
          {!catalog && !error && <div style={{ fontSize: 12, color: 'var(--text-4)' }}>Loading catalog…</div>}
          {error && (
            <div style={{ fontSize: 11.5, color: '#f85149', padding: '8px 10px',
                          background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.25)',
                          borderRadius: 4, marginBottom: 10 }}>
              {error}
            </div>
          )}

          {catalog && (
            <>
              <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                Categories
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 12 }}>
                {Object.entries(cats).map(([key, spec]) => (
                  <label key={key} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 8px',
                                              background: selected.has(key) ? 'rgba(45,212,191,0.08)' : 'var(--bg-elev)',
                                              border: '1px solid ' + (selected.has(key) ? 'rgba(45,212,191,0.3)' : 'var(--border-soft)'),
                                              borderRadius: 4, cursor: 'pointer', fontSize: 11.5 }}>
                    <input type="checkbox" checked={selected.has(key)} onChange={() => toggleCat(key)} style={{ marginTop: 2 }} />
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-2)' }}>{spec.label}</div>
                      <div style={{ fontSize: 10.5, color: 'var(--text-4)', marginTop: 2 }}>{spec.description}</div>
                      <div style={{ fontSize: 9.5, color: 'var(--text-mute)', marginTop: 3 }}>{spec.dorks.length} dork{spec.dorks.length === 1 ? '' : 's'}</div>
                    </div>
                  </label>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button className="btn primary sm" onClick={runDorks} disabled={running || selected.size === 0}>
                  {running ? <><Refresh s={11} /> Running…</> : <><Play s={11} /> Run {selected.size} categor{selected.size === 1 ? 'y' : 'ies'}</>}
                </button>
                <span style={{ fontSize: 10.5, color: 'var(--text-4)' }}>
                  Uses Google CSE if configured (Settings → Secrets: <span className="mono">GOOGLE_API_KEY</span> + <span className="mono">GOOGLE_CSE_ID</span>);
                  otherwise DuckDuckGo.
                </span>
              </div>
            </>
          )}

          {run && (
            <div style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, marginBottom: 8 }}>
                <span className={`badge ${run.status === 'success' ? 'low' : run.status === 'degraded' ? 'high' : 'crit'}`}>
                  {run.status}
                </span>
                <span style={{ color: 'var(--text-4)' }}>
                  {run.backend} backend · {run.total_findings} finding{run.total_findings === 1 ? '' : 's'}
                </span>
                {run.error_detail && (
                  <span style={{ color: 'var(--high)', fontSize: 10.5 }} title={run.error_detail}>
                    (with notes — hover for details)
                  </span>
                )}
              </div>
              {Object.keys(grouped).length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--text-4)', padding: 12, textAlign: 'center' }}>
                  No findings. The target may genuinely have no exposed content under these dorks,
                  or DuckDuckGo blocked us — try fewer categories or wait a few minutes.
                </div>
              )}
              {Object.entries(grouped).map(([cat, items]) => {
                const catLabel = cats[cat]?.label ?? cat;
                return (
                  <div key={cat} style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
                      {catLabel} <span style={{ color: 'var(--text-mute)' }}>· {items.length}</span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {items.map(f => (
                        <div key={f.id} style={{ padding: '8px 10px', background: 'var(--bg-elev)', borderRadius: 4, border: '1px solid var(--border-soft)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                            <a href={f.url} target="_blank" rel="noreferrer"
                               style={{ color: 'var(--accent)', fontSize: 12.5, fontWeight: 500, textDecoration: 'none', flex: 1, wordBreak: 'break-all' }}>
                              {f.title || f.url} <ExternalLink s={9} />
                            </a>
                            <span className="tag" style={{ fontSize: 9 }}>{f.source}</span>
                          </div>
                          {f.snippet && (
                            <div style={{ fontSize: 11, color: 'var(--text-3)', lineHeight: 1.4, marginBottom: 4 }}>{f.snippet}</div>
                          )}
                          <div className="mono" style={{ fontSize: 10, color: 'var(--text-mute)', wordBreak: 'break-all' }}>{f.dork}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


export default function InvestigatePage() {
  const token = useStore(s => s.token);
  const [query, setQuery]   = useState('');
  const [typeHint, setType] = useState('auto');
  const [error, setError]   = useState<string | null>(null);

  const [invId, setInvId]             = useState<string | null>(null);
  const [result, setResult]           = useState<Investigation | null>(null);
  const [invLoading, setInvLoading]   = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // AI request state
  const [aiRequesting, setAiRequesting] = useState(false);
  const [aiError, setAiError]           = useState<string | null>(null);

  // Add-to-domain-watch state
  const [addingDomain, setAddingDomain] = useState<string | null>(null);
  const [addedDomains, setAddedDomains] = useState<Set<string>>(new Set());

  const { items: history, isLoading: hLoading, mutate: refreshHistory } = useList<Investigation>('/investigations', { limit: 20 });

  const headers = useCallback(() => ({
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }), [token]);

  // Poll for completion
  useEffect(() => {
    if (!invId) return;
    const poll = async () => {
      try {
        const res = await fetch(`/api/investigations/${invId}`, { headers: headers() });
        if (!res.ok) {
          if (res.status >= 400 && res.status < 500) {
            setInvLoading(false);
            setError(`HTTP ${res.status}`);
            return;
          }
          pollRef.current = setTimeout(poll, 3000);
          return;
        }
        const data: Investigation = await res.json();
        if (data.status === 'complete' || data.status === 'failed') {
          setResult(data);
          setInvLoading(false);
          if (data.status === 'failed') {
            setError((data.payload && (data.payload as any).error) ? String((data.payload as any).error) : 'Investigation failed');
          }
          refreshHistory();
        } else {
          pollRef.current = setTimeout(poll, 3000);
        }
      } catch {
        pollRef.current = setTimeout(poll, 3000);
      }
    };
    pollRef.current = setTimeout(poll, 2000);
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
  }, [invId, headers, refreshHistory]);

  const doInvestigate = useCallback(async (value: string) => {
    if (!value.trim()) return;
    if (pollRef.current) clearTimeout(pollRef.current);
    setInvId(null); setResult(null); setError(null); setAiError(null);
    setHasSearched(true); setInvLoading(true);

    const type = typeHint !== 'auto' ? typeHint : inferType(value.trim());

    try {
      const res = await fetch('/api/investigate/async?run_ai=false', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ type, value: value.trim() }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`HTTP ${res.status}: ${t.slice(0, 200)}`);
      }
      const data = await res.json();
      if (data.job_id) setInvId(String(data.job_id));
      else throw new Error('No job_id in response');
    } catch (e) {
      setError(String(e));
      setInvLoading(false);
    }
  }, [headers, typeHint]);

  const requestAI = useCallback(async () => {
    if (!result) return;
    setAiRequesting(true); setAiError(null);
    try {
      const res = await fetch(`/api/investigations/${result.id}/synthesize`, {
        method: 'POST',
        headers: headers(),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`HTTP ${res.status}: ${t.slice(0, 200)}`);
      }
      const data: Investigation = await res.json();
      setResult(data);
      refreshHistory();
    } catch (e) {
      setAiError(String(e));
    } finally {
      setAiRequesting(false);
    }
  }, [result, headers, refreshHistory]);

  const handleAddToDomainWatch = useCallback(async (domain: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (addedDomains.has(domain)) return;
    setAddingDomain(domain);
    try { await api.post('/domains', { name: domain }); } catch { /* may already exist */ }
    setAddedDomains((prev) => new Set(prev).add(domain));
    setAddingDomain(null);
  }, [addedDomains]);

  const handleExport = useCallback(() => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `investigation-${result.normalized_value}-${result.id.slice(0, 8)}.json`;
    a.click();
  }, [result]);

  /* ---- parse payload ---- */
  const payload = (result?.payload ?? {}) as Record<string, any>;
  const ipApi          = payload.ip_api ?? null;
  const shodan         = payload.shodan ?? null;
  const crtsh          = payload.crtsh ?? null;
  const whois          = payload.whois ?? null;
  const passiveDns: string[] = Array.isArray(payload.passive_dns) ? payload.passive_dns : [];
  const localIocs      = payload.local_iocs ?? null;
  const relActors: any[] = Array.isArray(payload.related_actors) ? payload.related_actors : [];
  const relArticles: any[] = Array.isArray(payload.related_articles) ? payload.related_articles : [];
  const dnsRecords     = payload.dns_records ?? null;
  const reverseDns     = payload.reverse_dns ?? null;
  const abuseipdb      = payload.abuseipdb ?? null;
  const resolvedIp     = payload.resolved_ip ?? null;
  const resolvedIpEnr  = payload.resolved_ip_enrichment ?? null;

  const isComplete  = result?.status === 'complete' || result?.status === 'failed';
  const sourceTiles = (typeHint === 'ip' || (typeHint === 'auto' && /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(query))) ? SOURCE_TILES_IP : SOURCE_TILES_DOMAIN;

  // IOC library hits (passes through ioc-collector LookupResponse)
  const libHits = (localIocs?.hits ?? localIocs?.results ?? []) as any[];
  const libFound = libHits.filter((h: any) => h.found && h.indicator);
  const libMissed = libHits.filter((h: any) => !h.found);

  // Shodan vulns (sometimes from main shodan, sometimes from resolved_ip)
  const effectiveIpApi = ipApi ?? resolvedIpEnr?.ip_api ?? null;
  const effectiveShodan = shodan ?? resolvedIpEnr?.shodan ?? null;
  const effectiveAbuse  = abuseipdb ?? resolvedIpEnr?.abuseipdb ?? null;
  const effectivePtr    = reverseDns ?? resolvedIpEnr?.reverse_dns ?? null;
  const shodanPorts: number[] = Array.isArray(effectiveShodan?.ports) ? effectiveShodan.ports : [];
  const shodanVulns: string[] = Array.isArray(effectiveShodan?.vulns) ? effectiveShodan.vulns : [];
  const shodanHostnames: string[] = Array.isArray(effectiveShodan?.hostnames) ? effectiveShodan.hostnames : [];

  const crtshSubs: string[] = [...new Set<string>(Array.isArray(crtsh?.subdomains) ? (crtsh.subdomains as string[]) : [])];

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: '20px 28px' }}>
      {/* Search bar */}
      <div style={{ maxWidth: 900, margin: '0 auto 18px' }}>
        <div style={{ textAlign: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Deep investigation</div>
          <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.015em', marginTop: 2 }}>Passive enrichment for IPs &amp; domains</div>
          <div style={{ fontSize: 12, color: 'var(--text-4)', marginTop: 4 }}>
            DNS · rDNS · ASN · Shodan · AbuseIPDB · crt.sh · WHOIS · IOC library · Actor attribution — AI is opt-in
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ flex: 1, display: 'flex', gap: 6, background: 'var(--bg-card)', border: '1px solid var(--accent)', borderRadius: 8, padding: 5, boxShadow: '0 0 0 3px rgba(88,166,255,0.08)' }}>
            <select className="select" value={typeHint} onChange={(e) => setType(e.target.value)}
              style={{ border: 'none', background: 'transparent', height: 34, fontSize: 12.5, minWidth: 120 }}>
              <option value="auto">Auto-detect</option>
              <option value="ip">IP address</option>
              <option value="domain">Domain</option>
            </select>
            <div style={{ width: 1, background: 'var(--border)' }} />
            <input className="input mono" value={query} onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && doInvestigate(query)}
              placeholder="Enter an IP address or domain…"
              style={{ flex: 1, border: 'none', background: 'transparent', height: 34, fontSize: 13 }} />
            <button className="btn primary" style={{ height: 34, padding: '0 14px' }}
              onClick={() => doInvestigate(query)} disabled={invLoading}>
              {invLoading ? <Refresh s={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Search s={12} />}
              {invLoading ? 'Investigating…' : 'Investigate'}
            </button>
          </div>
          {result && <button className="btn" onClick={handleExport}><Download s={12} />Export</button>}
          {result?.indicator_type === 'domain' && !addedDomains.has(result.normalized_value) && (
            <button className="btn" onClick={(e) => handleAddToDomainWatch(result.normalized_value, e)}
              disabled={addingDomain === result.normalized_value}>
              <Globe s={12} />{addingDomain === result.normalized_value ? 'Adding…' : 'Domain Watch'}
            </button>
          )}
          {result?.indicator_type === 'domain' && addedDomains.has(result.normalized_value) && (
            <button className="btn" disabled style={{ color: '#3fb950' }}><Globe s={12} />Added</button>
          )}
        </div>
      </div>

      {error && (
        <div style={{ maxWidth: 900, margin: '0 auto 12px', padding: '10px 14px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 8, color: '#f85149', fontSize: 12.5 }}>
          <AlertTriangle s={12} style={{ marginRight: 6 }} />{error}
        </div>
      )}

      {/* Loading state */}
      {invLoading && !isComplete && (
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <div className="card" style={{ marginBottom: 10 }}>
            <div className="card-h">
              <Refresh s={13} style={{ animation: 'spin 1s linear infinite' }} />
              <div className="t">Running passive investigation</div>
              <span style={{ fontSize: 11, color: 'var(--text-4)', marginLeft: 4 }}>— no AI calls yet · querying sources in parallel…</span>
            </div>
            <div style={{ padding: '14px 16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {sourceTiles.map((s) => (
                  <div key={s} style={{ fontSize: 11, color: 'var(--text-4)', padding: '7px 10px', borderRadius: 5, background: 'var(--bg-page)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Refresh s={10} style={{ animation: 'spin 1.5s linear infinite', flexShrink: 0 }} />{s}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {isComplete && result && (
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, padding: '10px 14px', background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--border)' }}>
            <span className="mono" style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', flex: 1 }}>{result.normalized_value}</span>
            <span className="tag">{result.indicator_type}</span>
            {result.duration_ms != null && (
              <span style={{ fontSize: 10.5, color: 'var(--text-4)' }}>{result.duration_ms}ms · {fmtDate(result.investigated_at)}</span>
            )}
          </div>

          {/* 1. Network Intelligence (ip-api + Shodan + AbuseIPDB + rDNS) */}
          {(effectiveIpApi || effectiveShodan || effectiveAbuse || effectivePtr) && (
            <Sec icon={Globe} title="Network intelligence" danger={shodanVulns.length > 0 || (effectiveAbuse?.abuse_confidence_score ?? 0) >= 50}
              badge={shodanVulns.length > 0 ? `${shodanVulns.length} CVE(s) exposed` : null}>
              <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                {effectiveIpApi && (
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
                      Geolocation &amp; ASN {resolvedIp ? <span style={{ textTransform: 'none', color: 'var(--text-4)', marginLeft: 6 }}>(resolved A → {resolvedIp})</span> : null}
                    </div>
                    {effectiveIpApi.country && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <Flag code={effectiveIpApi.countryCode ?? ''} />
                        <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text)' }}>{effectiveIpApi.country}</span>
                        {effectiveIpApi.regionName && <span style={{ fontSize: 12, color: 'var(--text-4)' }}>· {effectiveIpApi.regionName}</span>}
                        {effectiveIpApi.city && <span style={{ fontSize: 12, color: 'var(--text-4)' }}>· {effectiveIpApi.city}</span>}
                      </div>
                    )}
                    <Row k="ISP" v={effectiveIpApi.isp} />
                    <Row k="Organisation" v={effectiveIpApi.org} />
                    <Row k="ASN" v={effectiveIpApi.as ?? effectiveIpApi.asname} />
                    {effectiveIpApi.lat && effectiveIpApi.lon && <Row k="Coordinates" v={`${effectiveIpApi.lat}, ${effectiveIpApi.lon}`} />}
                    {effectivePtr && <Row k="Reverse DNS" v={effectivePtr} />}
                    {effectiveIpApi.hosting && <Row k="Hosting" v="yes" />}
                    {effectiveIpApi.proxy && <Row k="Proxy/VPN" v="yes" />}
                    {effectiveIpApi.mobile && <Row k="Mobile network" v="yes" />}
                  </div>
                )}
                {(effectiveShodan || effectiveAbuse) && (
                  <div>
                    {effectiveShodan && (
                      <>
                        <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Shodan</div>
                        {effectiveShodan.org && <Row k="Org" v={effectiveShodan.org} />}
                        {effectiveShodan.isp && <Row k="ISP" v={effectiveShodan.isp} />}
                        {effectiveShodan.asn && <Row k="ASN" v={effectiveShodan.asn} />}
                        {effectiveShodan.os && <Row k="OS" v={effectiveShodan.os} />}
                        {shodanHostnames.length > 0 && <Row k="Hostnames" v={shodanHostnames.slice(0, 3).join(', ')} />}
                        {shodanPorts.length > 0 && (
                          <div style={{ marginTop: 10 }}>
                            <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Open ports</div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                              {shodanPorts.map((p) => <Tag key={p} color="#2dd4bf">{p}</Tag>)}
                            </div>
                          </div>
                        )}
                        {shodanVulns.length > 0 && (
                          <div style={{ marginTop: 10 }}>
                            <div style={{ fontSize: 10, color: '#f85149', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Exposed CVEs</div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                              {shodanVulns.map((v) => (
                                <a key={v} href={`/intelligence/cves/${v}`} style={{ textDecoration: 'none' }}><Tag color="#f85149">{v}</Tag></a>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}

                    {effectiveAbuse && (() => {
                      // Map AbuseIPDB's 0-100 score into a categorical
                      // reputation label so we don't show the raw number
                      // (numeric confidence metrics dropped platform-wide).
                      const s = effectiveAbuse.abuse_confidence_score ?? 0;
                      const cat = s >= 75 ? 'malicious'
                                : s >= 25 ? 'suspicious'
                                : 'clean';
                      const catColor = cat === 'malicious' ? '#f85149'
                                     : cat === 'suspicious' ? '#d29922'
                                     : '#3fb950';
                      return (
                        <div style={{ marginTop: effectiveShodan ? 14 : 0 }}>
                          <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>AbuseIPDB reputation</div>
                          <div style={{ marginBottom: 8 }}>
                            <span style={{ fontSize: 15, fontWeight: 700, color: catColor, textTransform: 'capitalize' }}>{cat}</span>
                          </div>
                          <Row k="Reports (90 days)" v={effectiveAbuse.total_reports ?? '0'} />
                          <Row k="Last report" v={effectiveAbuse.last_reported_at ? new Date(effectiveAbuse.last_reported_at).toLocaleDateString('en-GB') : null} />
                          <Row k="Usage type" v={effectiveAbuse.usage_type} />
                          {effectiveAbuse.is_tor && <Row k="Tor exit node" v="yes" />}
                          {effectiveAbuse.is_whitelisted && <Row k="Whitelisted" v="yes" />}
                        </div>
                      );
                    })()}
                  </div>
                )}
              </div>
            </Sec>
          )}

          {/* 2. DNS Records (domain only) */}
          {dnsRecords && Object.keys(dnsRecords).length > 0 && (
            <Sec icon={Network} title="DNS records (live resolver)">
              <div style={{ padding: '12px 16px' }}>
                {Object.entries(dnsRecords).map(([rtype, values]) => (
                  <div key={rtype} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                      {rtype} <span style={{ color: 'var(--text-4)', fontStyle: 'normal' }}>({(values as string[]).length})</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {(values as string[]).map((v, i) => <Tag key={i}>{v}</Tag>)}
                    </div>
                  </div>
                ))}
              </div>
            </Sec>
          )}

          {/* 3. IOC Library matches */}
          {libFound.length > 0 ? (
            libFound.map((h: any) => {
              const ind = h.indicator;
              const malwareFamilies = [...new Set((ind.sources ?? []).map((s: any) => s.malware_family).filter(Boolean))] as string[];
              const threatTypes     = [...new Set((ind.sources ?? []).map((s: any) => s.threat_type).filter(Boolean))] as string[];
              const sourceNames     = [...new Set((ind.sources ?? []).map((s: any) => s.source_name))] as string[];
              return (
                <Sec key={ind.id} icon={Crosshair} title="Threat intelligence library" danger badge="FOUND IN DATABASE">
                  <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Status</div>
                      <div style={{ marginBottom: 8 }}>
                        <span style={{ fontSize: 15, fontWeight: 600, color: '#f85149' }}>Known malicious</span>
                        <span style={{ fontSize: 11, color: 'var(--text-4)', marginLeft: 8 }}>· {sourceNames.length} source{sourceNames.length === 1 ? '' : 's'}</span>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-4)' }}>
                        First seen: <span className="mono" style={{ color: 'var(--text-3)' }}>{fmtDate(ind.first_seen)}</span><br />
                        Last seen: <span className="mono" style={{ color: 'var(--text-3)' }}>{fmtDate(ind.last_seen)}</span>
                      </div>
                    </div>
                    <div>
                      {malwareFamilies.length > 0 && (
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 5 }}>Malware family</div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                            {malwareFamilies.map((f) => <Tag key={f} color="#f85149">{f}</Tag>)}
                          </div>
                        </div>
                      )}
                      {threatTypes.length > 0 && (
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 5 }}>Threat type</div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{threatTypes.map((t) => <Tag key={t}>{t}</Tag>)}</div>
                        </div>
                      )}
                      {sourceNames.length > 0 && (
                        <div>
                          <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 5 }}>Reported by</div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{sourceNames.map((s) => <Tag key={s}>{s}</Tag>)}</div>
                        </div>
                      )}
                      <a href={`/iocs/${ind.id}`} className="btn sm" style={{ marginTop: 10, display: 'inline-flex' }}>View full IOC record <ExternalLink s={10} /></a>
                    </div>
                  </div>
                </Sec>
              );
            })
          ) : libMissed.length > 0 ? (
            <div className="card" style={{ marginBottom: 10 }}>
              <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Check s={13} style={{ color: '#3fb950' }} />
                <span style={{ fontSize: 12.5, color: 'var(--text-3)' }}>
                  <strong style={{ color: '#3fb950' }}>Not in threat library</strong> — no match in ThreatFox / MalwareBazaar / OTX
                </span>
              </div>
            </div>
          ) : null}

          {/* 4. Actor attribution */}
          {relActors.length > 0 ? (
            <Sec icon={Users} title="Actor attribution" danger badge="Attributed to known threat actor(s)">
              <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {relActors.map((a: any, i: number) => (
                  <a key={i} href={a.id ? `/actors/${a.id}` : '#'} style={{ textDecoration: 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 6, background: 'rgba(248,81,73,0.05)', border: '1px solid rgba(248,81,73,0.15)', cursor: 'pointer' }}>
                      <Users s={12} style={{ color: '#f85149', flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{a.name ?? 'Unknown actor'}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 2 }}>
                          {a.mitre_id && <span className="mono" style={{ marginRight: 8 }}>{a.mitre_id}</span>}
                          {a.origin_country && <span>{a.origin_country}</span>}
                          {(a.motivation ?? []).length > 0 && <span style={{ marginLeft: 6 }}>· {a.motivation.join(', ')}</span>}
                        </div>
                      </div>
                      {(a.target_sectors ?? []).slice(0, 2).map((s: string) => <Tag key={s}>{s}</Tag>)}
                      <ExternalLink s={11} style={{ color: 'var(--text-4)', flexShrink: 0 }} />
                    </div>
                  </a>
                ))}
              </div>
            </Sec>
          ) : (
            <div className="card" style={{ marginBottom: 10 }}>
              <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Check s={13} style={{ color: '#3fb950' }} />
                <span style={{ fontSize: 12.5, color: 'var(--text-3)' }}>
                  <strong style={{ color: '#3fb950' }}>No actor attribution</strong> — not linked to any known threat actor in our library
                </span>
              </div>
            </div>
          )}

          {/* 5. WHOIS + Passive DNS */}
          {(whois || passiveDns.length > 0) && (
            <Sec icon={FileText} title="WHOIS / passive DNS">
              <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                {whois && (
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>WHOIS / RDAP</div>
                    {whois.registrar && <Row k="Registrar" v={whois.registrar} />}
                    {whois.org && <Row k="Org" v={whois.org} />}
                    {whois.country && <Row k="Country" v={whois.country} />}
                    {whois.creation_date && <Row k="Created" v={String(whois.creation_date).slice(0, 19)} />}
                    {whois.expiration_date && <Row k="Expires" v={String(whois.expiration_date).slice(0, 19)} />}
                    {Array.isArray(whois.name_servers) && whois.name_servers.length > 0 && (
                      <Row k="Name servers" v={whois.name_servers.slice(0, 4).join(', ')} />
                    )}
                    {Array.isArray(whois.emails) && whois.emails.length > 0 && <Row k="Emails" v={whois.emails.slice(0, 3).join(', ')} />}
                  </div>
                )}
                {passiveDns.length > 0 && (
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
                      Passive DNS / subdomains <span style={{ fontStyle: 'normal' }}>({passiveDns.length})</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 240, overflow: 'auto' }}>
                      {passiveDns.slice(0, 50).map((s) => <Tag key={s}>{s}</Tag>)}
                      {passiveDns.length > 50 && <Tag>+{passiveDns.length - 50} more</Tag>}
                    </div>
                  </div>
                )}
              </div>
            </Sec>
          )}

          {/* 6. crt.sh certs */}
          {crtshSubs.length > 0 && (
            <Sec icon={Shield} title="Certificate transparency (crt.sh)" badge={`${crtshSubs.length} unique entries`}>
              <div style={{ padding: '12px 16px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 200, overflow: 'auto' }}>
                  {crtshSubs.slice(0, 80).map((s, i) => <Tag key={i}>{s}</Tag>)}
                  {crtshSubs.length > 80 && <Tag>+{crtshSubs.length - 80} more</Tag>}
                </div>
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-4)' }}>
                  Source: <a href={`https://crt.sh/?q=${encodeURIComponent(result.normalized_value)}`} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>
                    crt.sh <ExternalLink s={10} />
                  </a>
                </div>
              </div>
            </Sec>
          )}

          {/* 7. Related articles */}
          {relArticles.length > 0 && (
            <Sec icon={FileText} title="Mentioned in intelligence articles" badge={`${relArticles.length} articles`}>
              <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {relArticles.map((a: any) => (
                  <a key={a.id} href={`/intelligence/articles/${a.id}`} style={{ textDecoration: 'none', fontSize: 12.5, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <FileText s={11} style={{ flexShrink: 0, color: 'var(--text-4)' }} />
                    {a.title}
                    <ExternalLink s={10} style={{ color: 'var(--text-4)', flexShrink: 0 }} />
                  </a>
                ))}
              </div>
            </Sec>
          )}

          {/* 8. Google dorking — collapsed, on-demand. Uses the resolved
              target (the indicator we successfully investigated) so the
              dorks fire against whatever passed normalization. */}
          <DorksPanel
            target={result.normalized_value ?? result.raw_value ?? ''}
            targetType={result.indicator_type ?? 'domain'}
          />

          {/* 9. AI Analysis — collapsed, on-demand only */}
          <AIPanel inv={result} onRequest={requestAI} requesting={aiRequesting} requestError={aiError} />
        </div>
      )}

      {/* History table */}
      {!hasSearched && (
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <div className="card">
            <div className="card-h"><Activity s={13} /><div className="t">Recent investigations</div><div className="s">{history.length} records</div></div>
            {hLoading && <div style={{ padding: 20, color: 'var(--text-4)', fontSize: 12 }}>Loading…</div>}
            {!hLoading && history.length === 0 && (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                <Search s={24} />
                <div style={{ marginTop: 10 }}>No investigations yet. Enter an IP or domain above to start.</div>
              </div>
            )}
            {history.length > 0 && (
              <div style={{ overflow: 'auto' }}>
                <table className="tbl">
                  <thead><tr>
                    <th>Value</th>
                    <th style={{ width: 80 }}>Type</th>
                    <th style={{ width: 110 }}>AI verdict</th>
                    <th style={{ width: 80 }}>Risk</th>
                    <th style={{ width: 150 }}>Date</th>
                    <th style={{ width: 130 }}>Actions</th>
                  </tr></thead>
                  <tbody>
                    {history.map((inv) => (
                      <tr key={inv.id} style={{ cursor: 'pointer' }}
                        onClick={() => { setQuery(inv.normalized_value); setResult(inv); setHasSearched(true); }}>
                        <td className="mono" style={{ fontSize: 11.5, color: 'var(--text)' }}>{inv.normalized_value}</td>
                        <td><span className="tag">{inv.indicator_type}</span></td>
                        <td>
                          {inv.verdict
                            ? <span style={{ fontSize: 11, color: verdictColor(inv.verdict), textTransform: 'uppercase', fontWeight: 600 }}>{inv.verdict}</span>
                            : <span style={{ fontSize: 11, color: 'var(--text-4)' }}>not run</span>}
                        </td>
                        <td className="mono" style={{ fontSize: 11, color: riskColor(inv.risk_score) }}>
                          {inv.risk_score != null ? `${inv.risk_score}/100` : '—'}
                        </td>
                        <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>{fmtDate(inv.investigated_at)}</td>
                        <td>
                          {inv.indicator_type === 'domain' && !addedDomains.has(inv.normalized_value) && (
                            <button className="btn sm" style={{ fontSize: 10 }}
                              onClick={(e) => handleAddToDomainWatch(inv.normalized_value, e)}
                              disabled={addingDomain === inv.normalized_value}>
                              <Plus s={10} />{addingDomain === inv.normalized_value ? 'Adding…' : 'Domain Watch'}
                            </button>
                          )}
                          {inv.indicator_type === 'domain' && addedDomains.has(inv.normalized_value) && (
                            <span style={{ fontSize: 10, color: '#3fb950' }}>Added</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
