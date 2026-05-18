'use client';

import React, { useCallback, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import useSWR from 'swr';
import Ring from '@/components/shared/Ring';
import {
  Link as LinkIcon, Download, FileText, Server,
  AlertTriangle, Sparkles, ChevronLeft, Refresh,
} from '@/components/icons';
import { useCVE } from '@/lib/hooks';
import { api, fetcher } from '@/lib/api';

interface ExploitedInWild {
  value: boolean;
  evidence: string;
}

interface RelevantToUs {
  value: boolean;
  rationale: string;
  matched_assets: string[];
}

interface CveInsightPayload {
  description?: string;
  impact?: string;
  affected_versions?: string;
  recommendations?: string[];
  status?: string;
  exploited_in_the_wild?: ExploitedInWild;
  relevant_to_us?: RelevantToUs;
  severity_summary?: string;
  // Any other AI-emitted keys we don't explicitly render get dumped at the
  // bottom under "Additional details" — never lose data.
  [key: string]: unknown;
}

interface CveInsight {
  cve_id: string;
  payload: CveInsightPayload;
  analyst_override: Record<string, unknown> | null;
  model_name: string | null;
  prompt_version: string | null;
  generated_at: string;
}

function statusBadgeClass(s?: string): string {
  if (!s) return 'mute';
  if (s.includes('patched')) return 'low';
  if (s.includes('workaround')) return 'med';
  if (s.includes('no_patch')) return 'high';
  return 'mute';
}

function statusLabel(s?: string): string {
  switch (s) {
    case 'patched_available': return 'Patch available';
    case 'no_patch_yet':      return 'No patch yet';
    case 'workaround_only':   return 'Workaround only';
    default:                  return s ? s.replace(/_/g, ' ') : 'Unknown';
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function sevClass(sev: string | null) {
  const s = (sev ?? '').toLowerCase();
  if (s === 'critical') return { tag: 'crit', color: 'var(--crit)' };
  if (s === 'high')     return { tag: 'high', color: 'var(--high)' };
  if (s === 'medium')   return { tag: 'med',  color: 'var(--med)' };
  if (s === 'low')      return { tag: 'low',  color: 'var(--low)' };
  return { tag: 'mute', color: 'var(--text-4)' };
}

interface ProductItem { vendor?: string; product?: string; versions?: string; }

export default function CveDetailPage() {
  const params  = useParams();
  const router  = useRouter();
  const id      = params?.id as string;

  const { data: cve, isLoading } = useCVE(id);

  // AI insight — vuln-intel exposes GET /cves/{id}/insight (404 if not yet
  // generated) and POST /cves/{id}/analyze (202 — triggers orchestrator).
  const {
    data: insight,
    isLoading: insightLoading,
    mutate: mutateInsight,
  } = useSWR<CveInsight>(
    id ? `/cves/${id}/insight` : null,
    fetcher,
    { revalidateOnFocus: false, errorRetryCount: 0 },
  );
  const [analyzing, setAnalyzing] = useState(false);
  // analyzeError holds the most recent failure message so the user can tell
  // a rate-limit from a generic 500 from an "AI unavailable" — instead of the
  // button silently spinning down with no explanation.
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const handleAnalyze = useCallback(async () => {
    if (!id) return;
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      // POST /cves/{id}/analyze is synchronous — the new vuln-intel route
      // runs the LLM inline and returns the full InsightOut. Hand the result
      // straight to SWR's mutate so the panel updates immediately without an
      // extra GET round-trip. revalidate=false means "trust this value".
      const fresh = await api.post<CveInsight>(`/cves/${id}/analyze`);
      await mutateInsight(fresh, { revalidate: false });
    } catch (e: unknown) {
      // ApiError carries .status and .body — translate the common ones into
      // actionable messages. Anything else falls through to the raw text.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const err = e as { status?: number; body?: { detail?: string; message?: string } };
      const detail =
        err?.body?.detail ??
        err?.body?.message ??
        (e instanceof Error ? e.message : 'Request failed');
      let friendly = detail;
      if (err?.status === 429) {
        friendly = `AI provider is rate-limited. ${detail}`;
      } else if (err?.status === 413) {
        friendly = `This CVE's data is too large for the configured AI model. ${detail}`;
      } else if (err?.status === 502) {
        friendly = `AI provider failed upstream. ${detail}`;
      } else if (err?.status === 404) {
        friendly = `CVE not found (or AI client not configured).`;
      }
      setAnalyzeError(friendly);
    } finally {
      setAnalyzing(false);
    }
  }, [id, mutateInsight]);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)' }}>
        Loading CVE…
      </div>
    );
  }

  if (!cve) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)', gap: 12 }}>
        <div>CVE not found</div>
        <button className="btn" onClick={() => router.back()}><ChevronLeft s={12} />Go back</button>
      </div>
    );
  }

  const sev = sevClass(cve.severity);
  const cvssScore = cve.cvss_v3_score ?? 0;

  // Extract affected products list
  const ap = cve.affected_products ?? {};
  const productItems: ProductItem[] = Array.isArray((ap as Record<string, unknown>).items)
    ? (ap as Record<string, unknown>).items as ProductItem[]
    : [];
  const productLabels = productItems
    .map(p => [p.vendor, p.product, p.versions].filter(Boolean).join(' '))
    .filter(Boolean)
    .slice(0, 10);

  // Extract references
  const refs: string[] = Array.isArray(cve.references) ? cve.references : [];

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 18 }}>
      {/* Back + header */}
      <div style={{ marginBottom: 6 }}>
        <button className="btn sm" onClick={() => router.back()} style={{ marginBottom: 10 }}>
          <ChevronLeft s={11} />CVEs
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 16, alignItems: 'flex-start', marginBottom: 14 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span className={`badge ${sev.tag}`}><span className="dot" />{cve.severity ?? 'Unknown'} · {cvssScore.toFixed(1)}</span>
            {cve.kev && <span className="badge crit"><span className="dot pulse" />CISA KEV</span>}
            {cve.kev_ransomware_use && <span className="badge high">Ransomware-used</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
            <h1 className="mono" style={{ fontSize: 28, fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.01em', margin: 0 }}>
              {cve.cve_id}
            </h1>
          </div>
          <div style={{ display: 'flex', gap: 14, marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>
            <span>Published <span className="mono">{fmtDate(cve.published_at)}</span></span>
            <span>Updated <span className="mono">{fmtDate(cve.last_modified_at)}</span></span>
            {cve.cwe.length > 0 && <span>{cve.cwe[0]}</span>}
            {cve.cvss_v3_vector && <span className="mono" style={{ fontSize: 10.5 }}>{cve.cvss_v3_vector.slice(0, 40)}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <a href={`https://nvd.nist.gov/vuln/detail/${cve.cve_id}`} target="_blank" rel="noreferrer" className="btn">
            <LinkIcon s={12} />NVD
          </a>
          <button className="btn"><Download s={12} />Export</button>
        </div>
      </div>

      {/* Three top cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
        {/* CVSS */}
        <div className="card" style={{ padding: 14 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>CVSS 3.x</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <div style={{ fontSize: 36, fontWeight: 600, color: sev.color, fontFamily: 'var(--mono)', letterSpacing: '-0.02em', lineHeight: 1 }}>
              {cvssScore.toFixed(1)}
            </div>
            <div style={{ color: 'var(--text-3)', fontSize: 12 }}>/ 10</div>
            <span className={`badge ${sev.tag}`} style={{ marginLeft: 'auto' }}>{cve.severity ?? '—'}</span>
          </div>
          {cve.cvss_v3_vector && (
            <div className="mono" style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 6, lineHeight: 1.5, wordBreak: 'break-all' }}>
              {cve.cvss_v3_vector}
            </div>
          )}
          {cve.cwe.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {cve.cwe.slice(0, 3).map(c => <span key={c} className="tag">{c}</span>)}
            </div>
          )}
        </div>

        {/* EPSS */}
        <div className="card" style={{ padding: 14 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>EPSS exploitation probability</div>
          {cve.epss !== null && cve.epss !== undefined ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <Ring value={cve.epss} label={`${(cve.epss * 100).toFixed(1)}%`} sublabel="probability"
                    color={cve.epss > 0.7 ? '#f85149' : cve.epss > 0.3 ? '#d29922' : '#3fb950'}
                    size={108} thickness={8} />
              {cve.epss_percentile !== null && cve.epss_percentile !== undefined && (
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>Percentile</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600, color: cve.epss > 0.7 ? 'var(--crit)' : 'var(--text)' }}>
                    {(cve.epss_percentile * 100).toFixed(1)}%
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ color: 'var(--text-4)', fontSize: 12, paddingTop: 10 }}>No EPSS score available</div>
          )}
        </div>

        {/* KEV */}
        <div className="card" style={{ padding: 14, borderColor: cve.kev ? 'rgba(248,81,73,0.4)' : 'var(--border)' }}>
          <div style={{ fontSize: 10.5, color: cve.kev ? 'var(--crit)' : 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            {cve.kev && <span className="sev-dot crit pulse" />}
            CISA KEV
          </div>
          {cve.kev ? (
            <div>
              <div style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500, lineHeight: 1.45, marginBottom: 12 }}>
                Added to Known Exploited Vulnerabilities catalog
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase' }}>Added</div>
                  <div className="mono" style={{ fontSize: 13, color: 'var(--text)' }}>{fmtDate(cve.kev_date_added)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase' }}>Ransomware</div>
                  <div className={`badge ${cve.kev_ransomware_use ? 'crit' : 'mute'}`} style={{ marginTop: 2 }}>
                    {cve.kev_ransomware_use ? 'Known' : 'Not listed'}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-4)', fontSize: 12, paddingTop: 10 }}>Not in KEV catalog</div>
          )}
        </div>
      </div>

      {/* Body */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Description */}
          <div className="card">
            <div className="card-h"><FileText s={13} /><div className="t">Description</div></div>
            <div className="card-b">
              <p style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.65, margin: 0 }}>
                {cve.description ?? 'No description available.'}
              </p>
            </div>
          </div>

          {/* Affected products */}
          {productLabels.length > 0 && (
            <div className="card">
              <div className="card-h"><Server s={13} /><div className="t">Affected products</div><div className="s">{productLabels.length} entries</div></div>
              <div style={{ padding: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {productLabels.map((p, i) => <span key={i} className="tag" style={{ padding: '4px 8px' }}>{p}</span>)}
              </div>
            </div>
          )}

          {/* References */}
          {refs.length > 0 && (
            <div className="card">
              <div className="card-h"><LinkIcon s={13} /><div className="t">References</div><div className="s">{refs.length}</div></div>
              <div style={{ padding: 4 }}>
                {refs.slice(0, 8).map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderBottom: i < Math.min(refs.length, 8) - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                    <div title={r} className="mono" style={{ flex: 1, fontSize: 11, color: 'var(--accent)', wordBreak: 'break-all' }}>
                      {r}
                    </div>
                    <a href={r} target="_blank" rel="noreferrer" style={{ flexShrink: 0 }}>
                      <LinkIcon s={12} />
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* AI insight — fetches /cves/{id}/insight; if absent, the Generate
              button POSTs to /cves/{id}/analyze which runs the LLM inline and
              persists the structured payload. */}
          <div className="card">
            <div className="card-h">
              <Sparkles s={13} />
              <div className="t">AI insight</div>
              {insight && (
                <div className="right">
                  <button className="btn sm" onClick={handleAnalyze} disabled={analyzing} title="Re-run AI analysis">
                    <Refresh s={11} />{analyzing ? 'Analyzing…' : 'Re-analyze'}
                  </button>
                </div>
              )}
            </div>

            {insightLoading && (
              <div className="card-b" style={{ minHeight: 90, color: 'var(--text-4)', fontSize: 12, textAlign: 'center' }}>
                Loading insight…
              </div>
            )}

            {!insightLoading && !insight && (
              <div className="card-b" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 110, color: 'var(--text-4)', gap: 10 }}>
                <Sparkles s={20} />
                <div style={{ fontSize: 12 }}>
                  {analyzing
                    ? 'Calling the AI provider… (typically 5-15s)'
                    : 'No AI insight yet for this CVE'}
                </div>
                <button className="btn primary sm" onClick={handleAnalyze} disabled={analyzing}>
                  <Refresh s={11} />{analyzing ? 'Analyzing…' : 'Generate insight'}
                </button>
                {/* Show last error so the user can distinguish rate-limit /
                    AI provider failure / 5xx from a silent button. */}
                {analyzeError && (
                  <div style={{ marginTop: 6, padding: '8px 10px', maxWidth: 360, background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.25)', borderRadius: 6, fontSize: 11.5, color: '#f85149', textAlign: 'left' }}>
                    <strong>Last attempt failed:</strong> {analyzeError}
                  </div>
                )}
              </div>
            )}

            {!insightLoading && insight && (() => {
              // Pull the known fields out; everything else falls into "Additional details"
              // so the AI is never silently truncating data.
              const p = insight.payload ?? {};
              const known = new Set([
                'description', 'impact', 'affected_versions', 'recommendations',
                'status', 'exploited_in_the_wild', 'relevant_to_us', 'severity_summary',
              ]);
              const extras = Object.entries(p).filter(([k]) => !known.has(k));
              const eiw = p.exploited_in_the_wild;
              const rtu = p.relevant_to_us;

              return (
                <div className="card-b" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {/* Re-analyze failure banner — old insight stays visible
                      but the user knows the latest attempt to refresh it
                      didn't succeed (rate-limit, 5xx, etc). */}
                  {analyzeError && (
                    <div style={{ padding: '8px 10px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.25)', borderRadius: 6, fontSize: 11.5, color: '#f85149' }}>
                      <strong>Re-analyze failed:</strong> {analyzeError}{' '}
                      <span style={{ color: 'var(--text-4)' }}>— showing the previously-generated insight below.</span>
                    </div>
                  )}

                  {/* Analyst override banner wins over AI payload */}
                  {insight.analyst_override && (
                    <div style={{ padding: '8px 10px', background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.25)', borderRadius: 6 }}>
                      <div style={{ fontWeight: 600, color: '#d29922', fontSize: 11, marginBottom: 4 }}>Analyst Override</div>
                      <pre style={{ fontSize: 11, color: 'var(--text-2)', margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)' }}>
                        {JSON.stringify(insight.analyst_override, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Headline strip: status + exploited + relevance — at-a-glance triage */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    <span className={`badge ${statusBadgeClass(p.status)}`} title="Patch availability">{statusLabel(p.status)}</span>
                    {eiw && (
                      <span className={`badge ${eiw.value ? 'crit' : 'mute'}`} title={eiw.evidence}>
                        {eiw.value ? 'Exploited in the wild' : 'No active exploitation'}
                      </span>
                    )}
                    {rtu && (
                      <span className={`badge ${rtu.value ? 'high' : 'low'}`} title={rtu.rationale}>
                        {rtu.value ? `Relevant to us (${rtu.matched_assets?.length ?? 0} assets)` : 'Not in our inventory'}
                      </span>
                    )}
                  </div>

                  {/* Description */}
                  {p.description && (
                    <section style={{ padding: '8px 10px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Description</div>
                      <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.55 }}>{p.description}</div>
                    </section>
                  )}

                  {/* Impact */}
                  {p.impact && (
                    <section style={{ padding: '8px 10px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Impact</div>
                      <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.55 }}>{p.impact}</div>
                    </section>
                  )}

                  {/* Affected versions */}
                  {p.affected_versions && (
                    <section style={{ padding: '8px 10px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Affected versions</div>
                      <div className="mono" style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>{p.affected_versions}</div>
                    </section>
                  )}

                  {/* Recommendations */}
                  {p.recommendations && p.recommendations.length > 0 && (
                    <section style={{ padding: '8px 10px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Recommendations</div>
                      <ol style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {p.recommendations.map((r, i) => (
                          <li key={i} style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.55 }}>{r}</li>
                        ))}
                      </ol>
                    </section>
                  )}

                  {/* Exploited in the wild detail */}
                  {eiw && (
                    <section style={{ padding: '8px 10px', background: eiw.value ? 'rgba(248,81,73,0.06)' : 'var(--bg-elev)', border: `1px solid ${eiw.value ? 'rgba(248,81,73,0.25)' : 'var(--border)'}`, borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: eiw.value ? 'var(--crit)' : 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                        Exploited in the wild
                      </div>
                      <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.55 }}>
                        <strong style={{ color: eiw.value ? 'var(--crit)' : 'var(--text)' }}>
                          {eiw.value ? 'Yes' : 'No'}
                        </strong>
                        {eiw.evidence && <> — {eiw.evidence}</>}
                      </div>
                    </section>
                  )}

                  {/* Relevant to us */}
                  {rtu && (
                    <section style={{ padding: '8px 10px', background: rtu.value ? 'rgba(210,153,34,0.06)' : 'var(--bg-elev)', border: `1px solid ${rtu.value ? 'rgba(210,153,34,0.25)' : 'var(--border)'}`, borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: rtu.value ? 'var(--high)' : 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                        Relevant to our environment
                      </div>
                      <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.55, marginBottom: rtu.matched_assets && rtu.matched_assets.length > 0 ? 6 : 0 }}>
                        <strong style={{ color: rtu.value ? 'var(--high)' : 'var(--text)' }}>
                          {rtu.value ? 'Yes' : 'No'}
                        </strong>
                        {rtu.rationale && <> — {rtu.rationale}</>}
                      </div>
                      {rtu.matched_assets && rtu.matched_assets.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {rtu.matched_assets.map((a, i) => <span key={i} className="tag" style={{ background: 'rgba(210,153,34,0.1)', color: '#d29922' }}>{a}</span>)}
                        </div>
                      )}
                    </section>
                  )}

                  {/* Anything else the AI emitted — keep it visible */}
                  {extras.length > 0 && (
                    <section style={{ padding: '8px 10px', background: 'var(--bg-elev)', border: '1px dashed var(--border)', borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Additional details</div>
                      <pre style={{ fontSize: 11, color: 'var(--text-3)', margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)' }}>
                        {JSON.stringify(Object.fromEntries(extras), null, 2)}
                      </pre>
                    </section>
                  )}

                  <div style={{ fontSize: 10, color: 'var(--text-4)', display: 'flex', gap: 10, marginTop: 2 }}>
                    {insight.model_name && <span>Model: {insight.model_name}</span>}
                    {insight.prompt_version && <span>v{insight.prompt_version}</span>}
                    <span>{fmtDate(insight.generated_at)}</span>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Metadata */}
          <div className="card">
            <div className="card-h"><AlertTriangle s={13} /><div className="t">Metadata</div></div>
            <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                ['CVE ID', cve.cve_id],
                ['Published', fmtDate(cve.published_at)],
                ['Last modified', fmtDate(cve.last_modified_at)],
                ['CVSS 3.x', cvssScore ? cvssScore.toFixed(1) : '—'],
                ['Severity', cve.severity ?? '—'],
                ['CWE', cve.cwe.join(', ') || '—'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: 'var(--text-4)' }}>{k}</span>
                  <span className="mono" style={{ color: 'var(--text-2)' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
