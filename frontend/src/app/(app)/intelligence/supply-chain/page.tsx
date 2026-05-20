'use client';

import React, { useCallback, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import SortHeader from '@/components/shared/SortHeader';
import FilterBar from '@/components/shared/FilterBar';
import InsightView, { type InsightEnvelope } from '@/components/shared/InsightView';
import { Package, Crosshair, AlertTriangle, Layers, FileText, Plus, Download, Sparkles } from '@/components/icons';
import { useThreats } from '@/lib/hooks';
import type { Threat } from '@/lib/hooks';
import { useSortable } from '@/lib/sort';
import { api, fetcher } from '@/lib/api';
import KPI from '@/components/shared/KPI';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function sevColor(s: string | null) {
  switch (s?.toUpperCase()) {
    case 'CRITICAL': return '#f85149';
    case 'HIGH':     return '#d29922';
    // medium was the same electric blue as the accent — clashed visually
    // after the teal shift. Warm amber matches the platform-wide --med.
    case 'MEDIUM':   return '#e8a33a';
    case 'LOW':      return '#3fb950';
    default:         return '#8b949e';
  }
}

function sevBg(s: string | null) {
  switch (s?.toUpperCase()) {
    case 'CRITICAL': return 'rgba(248,81,73,0.12)';
    case 'HIGH':     return 'rgba(210,153,34,0.12)';
    case 'MEDIUM':   return 'rgba(88,166,255,0.12)';
    case 'LOW':      return 'rgba(63,185,80,0.12)';
    default:         return 'rgba(139,148,158,0.1)';
  }
}

/* ---- Detail panel ---- */
function DetailPanel({ threat, onClose }: { threat: Threat; onClose: () => void }) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const det = (threat.details ?? {}) as any;
  const iocs: string[] = det.iocs ?? det.indicators ?? [];
  const ttps: string[] = det.ttps ?? det.techniques ?? [];
  const products: string[] = det.affected_products ?? det.products ?? [];
  const cves: string[] = det.cves ?? det.vulnerabilities ?? [];

  // Same insight pipeline as the dedicated threat detail page — POST
  // /threats/{id}/analyze produces a hunting hypothesis + IOC extraction
  // + flowviz attack flow; results cache server-side at the current
  // prompt_version so re-opening the drawer doesn't re-bill the AI.
  const { data: insight, isLoading: insightLoading, mutate: mutateInsight } = useSWR<InsightEnvelope>(
    threat.id ? `/threats/${threat.id}/insight` : null,
    fetcher,
    { revalidateOnFocus: false, errorRetryCount: 0 },
  );
  const [analyzing, setAnalyzing] = useState(false);
  const handleAnalyze = useCallback(async (force = false) => {
    setAnalyzing(true);
    try {
      await api.post(`/threats/${threat.id}/analyze`, force ? { force: true } : {});
      mutateInsight();
    } finally { setAnalyzing(false); }
  }, [threat.id, mutateInsight]);

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', justifyContent: 'flex-end', background: 'rgba(0,0,0,0.45)' }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: 580, height: '100vh',
          background: 'var(--bg-page)', borderLeft: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(180deg,rgba(88,166,255,0.06),transparent 80%)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span
                  style={{
                    padding: '2px 8px', borderRadius: 4, fontSize: 10.5, fontWeight: 600,
                    background: sevBg(threat.severity), color: sevColor(threat.severity),
                  }}
                >{threat.severity ?? 'UNKNOWN'}</span>
                <span className="tag">{threat.type.replace('_', ' ')}</span>
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, marginTop: 8, lineHeight: 1.35 }}>{threat.title}</div>
              <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
                {threat.source} · {fmtDate(threat.observed_at)}
              </div>
            </div>
            <button className="btn sm" onClick={onClose}>✕ Close</button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Summary */}
          {threat.summary && (
            <div className="card">
              <div className="card-h"><FileText s={12} /><div className="t">Summary</div></div>
              <div style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6 }}>
                {threat.summary}
              </div>
            </div>
          )}

          {/* Affected products */}
          {products.length > 0 && (
            <div className="card">
              <div className="card-h"><Package s={12} /><div className="t">Affected products & components</div><div className="s">{products.length}</div></div>
              <div style={{ padding: '10px 14px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {products.map((p, i) => <span key={i} className="badge med">{p}</span>)}
              </div>
            </div>
          )}

          {/* CVEs */}
          {cves.length > 0 && (
            <div className="card">
              <div className="card-h"><AlertTriangle s={12} /><div className="t">CVEs</div><div className="s">{cves.length}</div></div>
              <div style={{ padding: '8px 14px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {cves.map((c, i) => (
                  <a key={i} href={`/intelligence/cves/${c}`} className="mono"
                     style={{ fontSize: 11, color: 'var(--accent)', textDecoration: 'none', padding: '3px 8px', background: 'rgba(88,166,255,0.08)', borderRadius: 4, border: '1px solid rgba(88,166,255,0.2)' }}>
                    {c}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* TTPs */}
          {ttps.length > 0 && (
            <div className="card">
              <div className="card-h"><Layers s={12} /><div className="t">MITRE ATT&CK techniques</div><div className="s">{ttps.length}</div></div>
              <div style={{ padding: '8px 14px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {ttps.map((t, i) => (
                  <span key={i} className="mono"
                        style={{ fontSize: 11, color: 'var(--text-2)', padding: '3px 8px', background: 'rgba(248,81,73,0.08)', borderRadius: 4, border: '1px solid rgba(248,81,73,0.2)' }}>
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* IOCs */}
          {iocs.length > 0 && (
            <div className="card">
              <div className="card-h"><Crosshair s={12} /><div className="t">Indicators of Compromise</div><div className="s">{iocs.length}</div></div>
              <div style={{ padding: 4 }}>
                {iocs.map((ioc, i) => (
                  <div key={i} style={{ padding: '7px 14px', borderBottom: i < iocs.length - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                    <span className="mono" style={{ fontSize: 11.5, color: 'var(--accent)' }}>{ioc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI insight — hunting hypothesis + IOC extraction + flowviz
              attack flow. Same shape and component as the standalone
              threat detail page. Cache-first by default; "Re-analyze"
              forces a fresh run. */}
          <div className="card">
            <div className="card-h">
              <Sparkles s={12} />
              <div className="t">AI insight</div>
              {insight && <div className="s">v{insight.prompt_version}</div>}
            </div>
            <div style={{ padding: 14 }}>
              {insightLoading && (
                <div style={{ textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>Loading…</div>
              )}
              {!insightLoading && !insight && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, padding: '8px 0' }}>
                  <div style={{ fontSize: 12, color: 'var(--text-3)' }}>No AI insight yet</div>
                  <button className="btn primary sm" onClick={() => handleAnalyze(false)} disabled={analyzing}>
                    <Sparkles s={11} />{analyzing ? 'Analyzing...' : 'Generate insight'}
                  </button>
                </div>
              )}
              {!insightLoading && insight && (
                <InsightView
                  insight={insight}
                  analyzing={analyzing}
                  onReanalyze={() => handleAnalyze(true)}
                  flowHeight={360}
                />
              )}
            </div>
          </div>

          {/* Source link */}
          {threat.source_url && (
            <div style={{ padding: '8px 0' }}>
              <a href={threat.source_url} target="_blank" rel="noopener noreferrer"
                 style={{ fontSize: 12, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 6 }}>
                View original report →
              </a>
            </div>
          )}

          {/* Raw details fallback */}
          {!threat.summary && products.length === 0 && iocs.length === 0 && ttps.length === 0 && cves.length === 0 && (
            <div className="card">
              <div className="card-h"><FileText s={12} /><div className="t">Raw details</div></div>
              <pre style={{ padding: '10px 14px', fontSize: 11, color: 'var(--text-3)', overflow: 'auto', maxHeight: 400 }}>
                {JSON.stringify(threat.details, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---- Page ---- */
export default function SupplyChainPage() {
  const router = useRouter();
  const [q, setQ] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [selected, setSelected] = useState<Threat | null>(null);

  const { items: threats, total, isLoading } = useThreats({ type: 'supply_chain', limit: 200 });

  const filtered = useMemo(() => {
    let list = threats as Threat[];
    if (q) {
      const lq = q.toLowerCase();
      list = list.filter(t =>
        t.title.toLowerCase().includes(lq) ||
        (t.summary ?? '').toLowerCase().includes(lq) ||
        (t.source ?? '').toLowerCase().includes(lq)
      );
    }
    if (severityFilter) {
      list = list.filter(t => (t.severity ?? '').toUpperCase() === severityFilter);
    }
    return list;
  }, [threats, q, severityFilter]);

  const { sorted, sortKey, sortDir, toggle } = useSortable(filtered, 'observed_at', 'desc');

  // Stats
  const sevCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const t of threats as Threat[]) {
      const k = (t.severity ?? 'UNKNOWN').toUpperCase();
      m[k] = (m[k] ?? 0) + 1;
    }
    return m;
  }, [threats]);

  const thisMonth = useMemo(() => {
    const cutoff = new Date();
    cutoff.setDate(1);
    return (threats as Threat[]).filter(t => t.observed_at && new Date(t.observed_at) >= cutoff).length;
  }, [threats]);

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Title */}
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10, flexShrink: 0 }}>
        <Package s={18} />
        <div style={{ fontSize: 18, fontWeight: 600, marginLeft: 8 }}>Supply Chain Threats</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          Software supply chain attacks, third-party compromises, dependency hijacking
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn sm" onClick={() => router.push('/intelligence/threats?type=supply_chain')}>
            <Download s={11} />Export
          </button>
          <button className="btn primary sm">
            <Plus s={11} />Report incident
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 14, flexShrink: 0 }}>
        <KPI label="Total tracked"       value={isLoading ? '…' : String(total)}                      delta="supply chain events" deltaDir="up" color="#2dd4bf" />
        <KPI label="This month"          value={isLoading ? '…' : String(thisMonth)}                  delta="new incidents" deltaDir="up" color="#d29922" live />
        <KPI label="Critical"            value={isLoading ? '…' : String(sevCounts['CRITICAL'] ?? 0)} delta="severity" deltaDir="up" color="#f85149" />
        <KPI label="High"                value={isLoading ? '…' : String(sevCounts['HIGH'] ?? 0)}     delta="severity" deltaDir="up" color="#d29922" />
        <KPI label="Showing"             value={isLoading ? '…' : String(filtered.length)}            delta="filtered" deltaDir="up" color="#3fb950" />
      </div>

      {/* Filters — switched from a custom div.bar (whose styles trapped the
          input focus on this page) to the shared FilterBar component that the
          rest of the app uses. Search now actually filters as you type. */}
      <FilterBar search="Search title, source, summary…" value={q} onSearch={setQ}>
        <select className="select" value={severityFilter} onChange={e => setSeverityFilter(e.target.value)}>
          <option value="">All severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </FilterBar>

      {/* Table */}
      <div className="card" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ overflow: 'auto', flex: 1 }}>
          <table className="tbl">
            <thead><tr>
              <SortHeader label="Date"     sortKey="observed_at" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
              <th style={{ width: 90 }}>Severity</th>
              <th>Title</th>
              <th style={{ width: 140 }}>Source</th>
              <th style={{ width: 60 }}>Status</th>
            </tr></thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={5} style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>Loading supply chain threats…</td></tr>
              )}
              {!isLoading && sorted.length === 0 && (
                <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-4)' }}>
                  {q || severityFilter ? 'No threats match the current filters.' : 'No supply chain threats recorded yet. Run the threat-intel ingestion job.'}
                </td></tr>
              )}
              {(sorted as Threat[]).map(t => (
                <tr
                  key={t.id}
                  onClick={() => setSelected(t)}
                  style={{ cursor: 'pointer' }}
                >
                  <td className="mono" style={{ fontSize: 11 }}>{fmtDate(t.observed_at)}</td>
                  <td>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 10.5, fontWeight: 600,
                      background: sevBg(t.severity), color: sevColor(t.severity),
                    }}>{t.severity ?? '—'}</span>
                  </td>
                  <td>
                    <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text)' }}>{t.title}</div>
                    {t.summary && (
                      <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 2, maxWidth: 480, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {t.summary}
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--text-4)' }}>{t.source}</td>
                  <td>
                    <span className={`badge ${t.analyst_status === 'relevant' ? 'low' : t.analyst_status === 'not_relevant' ? 'mute' : t.analyst_status === 'escalated' ? 'high' : 'mute'}`}
                          style={{ fontSize: 9.5 }}>
                      {t.analyst_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail panel */}
      {selected && <DetailPanel threat={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
