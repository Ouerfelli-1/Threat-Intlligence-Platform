'use client';

import React, { useState } from 'react';
import {
  FileText, Plus, Sparkles, Download, Refresh,
  AlertTriangle, Users, Bug, Activity,
} from '@/components/icons';
import { useReports, type Report } from '@/lib/hooks';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function howLongAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3_600_000);
  const d = Math.floor(diff / 86_400_000);
  if (d > 0) return `${d}d ago`;
  if (h > 0) return `${h}h ago`;
  return 'just now';
}

function kindLabel(k: string): string {
  return k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function kindBadge(k: string) {
  if (k === 'analysis_cycle') return 'med';
  if (k === 'geo_prediction') return 'high';
  return 'mute';
}

export default function ReportsPage() {
  const { items, total, isLoading, mutate } = useReports({ limit: 50 });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected: Report | undefined = items.find(r => r.id === selectedId) ?? items[0];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const payload = (selected?.payload ?? {}) as any;
  const brief = payload?.brief ?? null;
  const cveRelevance = payload?.cve_relevance ?? null;
  const actorLikelihood = payload?.actor_likelihood ?? null;
  const correlations = payload?.correlations ?? null;
  const headline = brief?.headline ?? payload?.headline ?? null;
  const topActions = brief?.top_3_actions ?? payload?.top_3_actions ?? [];
  const findings = brief?.expanded_findings ?? payload?.expanded_findings ?? [];

  // Check if payload has any real content
  const hasContent = headline || topActions.length > 0 || findings.length > 0;
  const hasSubSections = cveRelevance || actorLikelihood || correlations;
  const isEmpty = !hasContent && !hasSubSections && (!payload || Object.values(payload).every(v => v === null || v === undefined));

  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateColumns: '320px 1fr', overflow: 'hidden' }}>
      {/* Index sidebar */}
      <div style={{ borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileText s={13} /><div style={{ fontSize: 13, fontWeight: 600 }}>Reports</div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            <button className="btn sm" onClick={() => mutate()}><Refresh s={11} /></button>
            <button className="btn sm"><Plus s={11} />Run</button>
          </div>
        </div>
        <div style={{ overflow: 'auto', flex: 1 }}>
          {isLoading && <div style={{ padding: 20, color: 'var(--text-4)' }}>Loading...</div>}
          {!isLoading && items.length === 0 && <div style={{ padding: 20, color: 'var(--text-4)' }}>No reports yet. Trigger the analysis cycle.</div>}
          {items.map((r) => (
            <div
              key={r.id}
              onClick={() => setSelectedId(r.id)}
              style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--border-soft)',
                cursor: 'pointer',
                background: (selected?.id === r.id) ? 'rgba(88,166,255,0.06)' : 'transparent',
                borderLeft: (selected?.id === r.id) ? '2px solid var(--accent)' : '2px solid transparent',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className={`badge ${kindBadge(r.kind)}`} style={{ fontSize: 10 }}>{kindLabel(r.kind)}</span>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 4 }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>{fmtDate(r.generated_at)}</span>
                <span style={{ fontSize: 10, color: 'var(--text-4)' }}>· {howLongAgo(r.generated_at)}</span>
              </div>
              {r.model_name && <div className="mono" style={{ fontSize: 9.5, color: 'var(--text-mute)', marginTop: 2 }}>{r.model_name}</div>}
            </div>
          ))}
        </div>
        <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-4)' }}>
          {total} total
        </div>
      </div>

      {/* Body */}
      <div style={{ overflow: 'auto' }}>
        {!selected && (
          <div style={{ padding: 50, color: 'var(--text-4)', textAlign: 'center' }}>
            <Sparkles s={40} />
            <div style={{ marginTop: 16 }}>Select a report on the left to read it.</div>
          </div>
        )}
        {selected && (
          <>
            <div style={{ padding: '20px 28px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(180deg, rgba(88,166,255,0.05), transparent 80%)' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
                <Sparkles s={16} />
                <span className={`badge ${kindBadge(selected.kind)}`}>{kindLabel(selected.kind)}</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>report-{selected.id.slice(0, 8)}</span>
                <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                  <button className="btn sm"><Download s={11} />Export</button>
                  <button className="btn primary sm"><Refresh s={11} />Re-run</button>
                </span>
              </div>
              <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.015em', margin: '4px 0 6px', color: 'var(--text)' }}>
                {headline ?? kindLabel(selected.kind)}
              </h1>
              <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                Generated {fmtDate(selected.generated_at)} · {selected.model_name || 'unknown model'} · prompt {selected.prompt_version || '—'}
              </div>
            </div>

            <div style={{ padding: 18 }}>
              {/* Top actions — BriefOutput.top_3_actions is list[str] (per
                  prompts.py / analysis.py). Older briefs may have stored
                  legacy {t/p,text/priority} objects — handle both shapes. */}
              {topActions.length > 0 && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="card-h"><FileText s={13} /><div className="t">Top actions</div></div>
                  <div style={{ padding: 14 }}>
                    {topActions.map((a: unknown, i: number) => {
                      const isStr = typeof a === 'string';
                      const obj = isStr ? null : (a as Record<string, unknown>);
                      const text = isStr ? (a as string) : (String(obj?.t ?? obj?.text ?? ''));
                      const tag  = isStr ? `P${i + 1}` : String(obj?.p ?? obj?.priority ?? `P${i + 1}`);
                      return (
                        <div key={i} style={{ padding: '8px 0', borderBottom: i < topActions.length - 1 ? '1px solid var(--border-soft)' : 'none', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                          <span className="mono" style={{ fontSize: 10, color: 'var(--high)', flexShrink: 0, paddingTop: 2, minWidth: 24 }}>{tag}</span>
                          <span style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-2)' }}>{text}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Expanded findings — ExpandedFinding has {title, summary,
                  attack_flow_input, priority, attack_flow?}. Read summary
                  (was misnamed body/description before). */}
              {findings.length > 0 && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="card-h"><FileText s={13} /><div className="t">Expanded findings</div></div>
                  <div style={{ padding: 14 }}>
                    {findings.map((f: Record<string, unknown>, i: number) => {
                      const summary = String(f.summary ?? f.body ?? f.description ?? '');
                      const priority = String(f.priority ?? '');
                      const priClass = priority === 'critical' ? 'crit' : priority === 'high' ? 'high' : priority === 'medium' ? 'med' : priority === 'low' ? 'low' : 'mute';
                      const attackInput = typeof f.attack_flow_input === 'string' ? f.attack_flow_input : '';
                      return (
                        <div key={i} style={{ marginBottom: 18, paddingBottom: i < findings.length - 1 ? 14 : 0, borderBottom: i < findings.length - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
                            <h3 style={{ fontSize: 13.5, color: 'var(--text)', margin: 0, fontWeight: 600 }}>{i + 1}. {String(f.title ?? 'Finding')}</h3>
                            {priority && <span className={`badge ${priClass}`} style={{ fontSize: 10 }}>{priority}</span>}
                          </div>
                          {summary && (
                            <p style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.6, margin: '0 0 6px' }}>{summary}</p>
                          )}
                          {attackInput && (
                            <div style={{ fontSize: 11, color: 'var(--text-4)', fontStyle: 'italic', marginTop: 4 }}>
                              <span style={{ color: 'var(--text-3)' }}>Attack scenario: </span>{attackInput}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Sub-sections from analysis cycle */}
              {cveRelevance && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="card-h"><Bug s={13} /><div className="t">CVE Relevance</div></div>
                  <div style={{ padding: 14 }}>
                    {Array.isArray(cveRelevance) ? (
                      cveRelevance.slice(0, 10).map((c: Record<string, unknown>, i: number) => (
                        <div key={i} style={{ display: 'flex', gap: 10, padding: '6px 0', borderBottom: i < Math.min(cveRelevance.length, 10) - 1 ? '1px solid var(--border-soft)' : 'none', alignItems: 'center' }}>
                          <span className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>{String(c.cve_id ?? '')}</span>
                          <span style={{ fontSize: 11.5, color: 'var(--text-3)', flex: 1 }}>{String(c.rationale ?? c.reason ?? '')}</span>
                          {c.relevance_score != null && <span className="mono" style={{ fontSize: 11, color: 'var(--high)' }}>{Number(c.relevance_score).toFixed(2)}</span>}
                        </div>
                      ))
                    ) : (
                      <pre style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(cveRelevance, null, 2)}</pre>
                    )}
                  </div>
                </div>
              )}

              {actorLikelihood && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="card-h"><Users s={13} /><div className="t">Actor Likelihood</div></div>
                  <div style={{ padding: 14 }}>
                    {Array.isArray(actorLikelihood) ? (
                      actorLikelihood.slice(0, 10).map((a: Record<string, unknown>, i: number) => (
                        <div key={i} style={{ display: 'flex', gap: 10, padding: '6px 0', borderBottom: i < Math.min(actorLikelihood.length, 10) - 1 ? '1px solid var(--border-soft)' : 'none', alignItems: 'center' }}>
                          <span style={{ fontSize: 11.5, color: 'var(--text)' }}>{String(a.actor_name ?? a.actor_id ?? '')}</span>
                          <span style={{ fontSize: 11, color: 'var(--text-3)', flex: 1 }}>{String(a.rationale ?? '')}</span>
                          {a.likelihood_score != null && <span className="mono" style={{ fontSize: 11, color: 'var(--crit)' }}>{(Number(a.likelihood_score) * 100).toFixed(0)}%</span>}
                        </div>
                      ))
                    ) : (
                      <pre style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(actorLikelihood, null, 2)}</pre>
                    )}
                  </div>
                </div>
              )}

              {correlations && (
                <div className="card" style={{ marginBottom: 14 }}>
                  <div className="card-h"><Activity s={13} /><div className="t">Correlations</div></div>
                  <div style={{ padding: 14 }}>
                    {Array.isArray(correlations) ? (
                      correlations.slice(0, 10).map((c: Record<string, unknown>, i: number) => (
                        <div key={i} style={{ padding: '6px 0', borderBottom: i < Math.min(correlations.length, 10) - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                          <span style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{String(c.kind ?? c.type ?? 'correlation')}: </span>
                          <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{JSON.stringify(c.payload ?? c, null, 0).slice(0, 200)}</span>
                        </div>
                      ))
                    ) : (
                      <pre style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(correlations, null, 2)}</pre>
                    )}
                  </div>
                </div>
              )}

              {/* Empty report state */}
              {isEmpty && (
                <div className="card">
                  <div style={{ padding: 40, textAlign: 'center' }}>
                    <AlertTriangle s={24} />
                    <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 10 }}>
                      This report has no content yet.
                    </div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-4)', marginTop: 4 }}>
                      The analysis cycle may have completed without AI output — check OpenRouter API key and model availability.
                    </div>
                  </div>
                </div>
              )}

              {/* Raw fallback — show when there's partial data but no structured content */}
              {!isEmpty && !hasContent && !hasSubSections && (
                <div className="card">
                  <div className="card-h"><FileText s={13} /><div className="t">Raw payload</div></div>
                  <pre style={{ padding: 14, margin: 0, fontSize: 10.5, color: 'var(--text-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'var(--mono)' }}>
                    {JSON.stringify(selected.payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
