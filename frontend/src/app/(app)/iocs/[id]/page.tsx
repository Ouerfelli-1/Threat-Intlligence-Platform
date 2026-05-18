'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import Bar from '@/components/shared/Bar';
import {
  ChevronLeft, Crosshair, Refresh, Sparkles, Search,
  Clock, FileText, Link as LinkIcon,
} from '@/components/icons';
import { useOne } from '@/lib/hooks';

interface IndicatorSource {
  source_name: string;
  source_id: string | null;
  first_reported_at: string | null;
  last_reported_at: string | null;
  malware_family: string | null;
  threat_type: string | null;
}

interface IndicatorDetail {
  id: string;
  type: string;
  normalized_value: string;
  raw_value: string;
  first_seen: string;
  last_seen: string;
  tags: string[];
  confidence_score: number;
  confidence_inputs: Record<string, unknown> | null;
  analyst_status: string;
  sources: IndicatorSource[];
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function typeBadge(t: string) {
  const m: Record<string, string> = {
    ip: 'low', ipv4: 'low', ipv6: 'low',
    domain: 'med', url: 'med',
    sha256: 'high', sha1: 'high', md5: 'high',
  };
  return <span className={`badge ${m[t] ?? 'mute'}`}>{t}</span>;
}

function stBadge(s: string) {
  if (s === 'reviewed' || s === 'relevant')   return <span className="badge low">{s}</span>;
  if (s === 'unreviewed')                     return <span className="badge med">unreviewed</span>;
  if (s === 'escalated')                      return <span className="badge high">escalated</span>;
  if (s === 'not_relevant')                   return <span className="badge mute">not-rel</span>;
  return <span className="badge mute">{s}</span>;
}

export default function IndicatorDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id     = params?.id as string;

  const { data: indicator, isLoading, mutate: refetch } = useOne<IndicatorDetail>(id ? `/indicators/${id}` : null);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)' }}>
        Loading indicator…
      </div>
    );
  }

  if (!indicator) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)', gap: 12 }}>
        <div>Indicator not found</div>
        <button className="btn" onClick={() => router.back()}><ChevronLeft s={12} />Go back</button>
      </div>
    );
  }

  const conf = indicator.confidence_score ?? 0;
  const sources = indicator.sources ?? [];

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 18 }}>
      {/* Back */}
      <div style={{ marginBottom: 10 }}>
        <button className="btn sm" onClick={() => router.back()}><ChevronLeft s={11} />IOC Library</button>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            {typeBadge(indicator.type)}
            {stBadge(indicator.analyst_status)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <Crosshair s={16} />
            <h1 className="mono" style={{ fontSize: 22, fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.01em', margin: 0, wordBreak: 'break-all' }}>
              {indicator.normalized_value}
            </h1>
          </div>
          {indicator.raw_value && indicator.raw_value !== indicator.normalized_value && (
            <div className="mono" style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 4 }}>
              Raw: {indicator.raw_value}
            </div>
          )}
          <div style={{ display: 'flex', gap: 14, fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>
            <span>First seen <span className="mono">{fmtDate(indicator.first_seen)}</span></span>
            <span>Last seen <span className="mono">{fmtDate(indicator.last_seen)}</span></span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          <a href={`/iocs/investigate?type=${indicator.type}&value=${encodeURIComponent(indicator.normalized_value)}`} className="btn primary">
            <Search s={12} />Investigate
          </a>
          <button className="btn" onClick={() => refetch()} title="Re-fetch this indicator from the backend"><Refresh s={12} />Refresh</button>
        </div>
      </div>

      {/* Body grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 12 }}>
        {/* Left */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Confidence card */}
          <div className="card">
            <div className="card-h"><Sparkles s={13} /><div className="t">Confidence</div></div>
            <div style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12 }}>
                <div style={{ fontSize: 32, fontWeight: 600, fontFamily: 'var(--mono)', color: conf > 0.85 ? 'var(--low)' : conf > 0.6 ? 'var(--med)' : 'var(--high)' }}>
                  {conf.toFixed(2)}
                </div>
                <div style={{ flex: 1 }}>
                  <Bar value={conf} variant={conf > 0.85 ? 'low' : conf > 0.6 ? '' : 'high'} />
                </div>
              </div>
              {indicator.confidence_inputs && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11.5 }}>
                  {Object.entries(indicator.confidence_inputs).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px', background: 'var(--bg-elev)', borderRadius: 4 }}>
                      <span style={{ color: 'var(--text-4)' }}>{k.replace(/_/g, ' ')}</span>
                      <span className="mono" style={{ color: 'var(--text-2)' }}>{typeof v === 'number' ? (v as number).toFixed(2) : String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Sources card */}
          <div className="card">
            <div className="card-h"><LinkIcon s={13} /><div className="t">Sources</div><div className="s">{sources.length} reporting</div></div>
            {sources.length === 0 ? (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>No source records.</div>
            ) : (
              <table className="tbl">
                <thead><tr>
                  <th>Source</th>
                  <th style={{ width: 140 }}>Malware family</th>
                  <th style={{ width: 120 }}>Threat type</th>
                  <th style={{ width: 140 }}>First reported</th>
                  <th style={{ width: 140 }}>Last reported</th>
                </tr></thead>
                <tbody>
                  {sources.map((s, i) => (
                    <tr key={i}>
                      <td className="mono" style={{ fontSize: 11.5, color: 'var(--accent)' }}>{s.source_name}</td>
                      <td>{s.malware_family ? <span className="badge high">{s.malware_family}</span> : <span style={{ color: 'var(--text-4)' }}>—</span>}</td>
                      <td>{s.threat_type ? <span className="tag">{s.threat_type}</span> : <span style={{ color: 'var(--text-4)' }}>—</span>}</td>
                      <td className="mono" style={{ fontSize: 11 }}>{fmtDate(s.first_reported_at)}</td>
                      <td className="mono" style={{ fontSize: 11 }}>{fmtDate(s.last_reported_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Metadata */}
          <div className="card">
            <div className="card-h"><FileText s={13} /><div className="t">Metadata</div></div>
            <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              {[
                ['Type', indicator.type],
                ['First seen', fmtDate(indicator.first_seen)],
                ['Last seen', fmtDate(indicator.last_seen)],
                ['Confidence', conf.toFixed(2)],
                ['Sources', String(sources.length)],
                ['Status', indicator.analyst_status || 'unreviewed'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-4)' }}>{k}</span>
                  <span className="mono" style={{ color: 'var(--text-2)' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Tags */}
          {indicator.tags.length > 0 && (
            <div className="card">
              <div className="card-h"><Clock s={13} /><div className="t">Tags</div></div>
              <div style={{ padding: 10, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {indicator.tags.map(t => <span key={t} className="tag">{t}</span>)}
              </div>
            </div>
          )}

          {/* Quick actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <a href={`/iocs/investigate?type=${indicator.type}&value=${encodeURIComponent(indicator.normalized_value)}`}
               className="btn" style={{ width: '100%', justifyContent: 'center' }}>
              <Search s={12} />Deep investigate
            </a>
            <a href={`/iocs/lookup?q=${encodeURIComponent(indicator.normalized_value)}`}
               className="btn" style={{ width: '100%', justifyContent: 'center' }}>
              <Crosshair s={12} />Quick lookup
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
