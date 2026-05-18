'use client';

import React, { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import KPI from '@/components/shared/KPI';
import Flag from '@/components/shared/Flag';
import StatusDot from '@/components/shared/StatusDot';
import {
  Sparkles, Users, Clock, FileText,
  Refresh, Download, Skull, Shield, Layers,
} from '@/components/icons';
import { useDashboard, useRansomwareVictims, useCVEs, useList } from '@/lib/hooks';
import { useStore } from '@/lib/store';
import { api } from '@/lib/api';

function spark(n = 14, base = 20) {
  return Array.from({ length: n }, (_, i) => base + Math.sin(i * 0.6) * 8 + (i % 3) * 2);
}

function fmtNum(n: number): string {
  if (n >= 1000) return n.toLocaleString();
  return String(n);
}

function howLongAgo(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const s = Math.floor(diff / 1000);
  if (s < 60)  return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function fmtMs(ms: number | null): string {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

export default function DashboardPage() {
  const router = useRouter();
  const { data, isLoading, mutate: mutDash } = useDashboard();
  const user = useStore((s) => s.user);

  // Feeds for the side cards. Top likely actors come from useDashboard, the
  // rest pull live each time so dashboard refresh updates them too.
  const { items: kevCves } = useCVEs({ kev: true, limit: 5 });
  const { items: recentVictims } = useRansomwareVictims({ limit: 5 });
  interface AsmFinding {
    id: string;
    type: string;
    value: string;
    source: string;
    discovered_at: string;
  }
  const { items: asmFindings } = useList<AsmFinding>('/findings', { limit: 6 });

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12)  return 'Good morning';
    if (h < 18)  return 'Good afternoon';
    return 'Good evening';
  })();

  // analysis_cycle reports nest the brief at payload.brief.{headline, top_3_actions,...}.
  // Older / partial briefs may put fields at the top level; check both paths.
  // `degraded=true` means the brief was synthesized from raw trending data
  // because the AI was rate-limited or otherwise unavailable.
  type BriefSection = {
    headline?: string;
    top_3_actions?: unknown[];
    threat_level?: string;
    degraded?: boolean;
    degraded_reason?: string;
  };
  type ReportPayload = BriefSection & { brief?: BriefSection };
  const reportPayload = (data?.latest_brief?.payload ?? {}) as ReportPayload;
  const briefSection: BriefSection = reportPayload.brief ?? reportPayload;
  const headline = briefSection?.headline;
  const briefDegraded = !!briefSection?.degraded;
  // top_3_actions is BriefOutput.top_3_actions: list[str]. Older briefs may
  // have stored objects; handle both so we never render JSON.
  const briefActions: { tag: string; text: string }[] = (briefSection?.top_3_actions ?? []).map((a, i) => {
    if (typeof a === 'string') return { tag: `P${i + 1}`, text: a };
    const obj = (a ?? {}) as Record<string, unknown>;
    return {
      tag: String(obj.p ?? obj.priority ?? `P${i + 1}`),
      text: String(obj.t ?? obj.text ?? ''),
    };
  });

  const handleRerunAI = useCallback(async () => {
    try { await api.post('/analyze'); } catch { /* 202 is expected */ }
  }, []);

  const handleExportBrief = useCallback(() => {
    if (!data?.latest_brief) return;
    const blob = new Blob([JSON.stringify(data.latest_brief, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `threat-briefing-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
  }, [data]);

  return (
    <div style={{ padding: 18, overflow: 'auto', height: '100%' }}>
      {/* Greeting strip */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 14 }}>
        <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.015em' }}>
          {greeting}{user?.username ? `, ${user.username.split('.')[0]}` : ''}
        </div>
        <div style={{ color: 'var(--text-4)', fontSize: 12 }}>
          Daily briefing &middot; {new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutDash()}><Refresh s={12} />Refresh feeds</button>
          <button className="btn" onClick={handleExportBrief}><Download s={12} />Export brief</button>
          <button className="btn primary" onClick={handleRerunAI}><Sparkles s={12} />Re&#x2011;run AI analysis</button>
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10, marginBottom: 14 }}>
        <KPI label="Total IOCs"        value={isLoading ? '...' : fmtNum(data?.iocs_total ?? 0)}     delta="live" deltaDir="up" spark={spark(16, 30)} live />
        <KPI label="Active CVEs"       value={isLoading ? '...' : fmtNum(data?.cves_total ?? 0)}     delta="tracked" deltaDir="up" spark={spark(16, 18)} color="#d29922" />
        <KPI label="Threats"           value={isLoading ? '...' : fmtNum(data?.threats_total ?? 0)}  delta="active"  deltaDir="up" spark={[1,2,2,3,3,2,3,3,3,3]} color="#f85149" />
        <KPI label="Articles ingested" value={isLoading ? '...' : fmtNum(data?.articles_total ?? 0)} delta="indexed" deltaDir="up" spark={spark(16, 22)} color="#58a6ff" />
        <KPI label="Ranked actors"     value={isLoading ? '...' : fmtNum(data?.actors_total ?? 0)}   delta="profiled" deltaDir="dn" spark={[6,7,7,8,8,9,9,9,9,9]} color="#a371f7" />
        <KPI
          label="Service health"
          value={isLoading ? '...' : `${data?.services_healthy ?? 0}/${data?.services_total ?? 15}`}
          delta={data && data.services_healthy === data.services_total ? 'all OK' : 'degraded'}
          deltaDir="dn"
          spark={[15, 15, 15, 14, 15, 15, 15, 15]}
          color="#3fb950"
          live
        />
      </div>

      {/* Two-column body
            LEFT                                  RIGHT
            [Daily Threat Briefing]               [Exploited in the Wild]
            [Top actors relevant to us]           [Recent ransomware attacks]
            [ASM findings]                        [Scheduler runs]
      */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {/* LEFT */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Daily Threat Briefing */}
          <div className="card">
            <div className="card-h">
              <Sparkles s={13} />
              <div className="t">Daily Threat Briefing</div>
              <div className="s">
                {data?.latest_brief
                  ? `generated ${howLongAgo(data.latest_brief.generated_at)} by ${data.latest_brief.model_name ?? 'orchestrator'}`
                  : 'no brief yet'}
              </div>
              <div className="right">
                {briefDegraded
                  ? <span className="badge high" title={briefSection?.degraded_reason}><span className="dot" />AI UNAVAILABLE</span>
                  : data?.latest_brief && <span className="badge med"><span className="dot" />FRESH</span>}
              </div>
            </div>
            <div className="card-b">
              {briefDegraded && (
                <div style={{ marginBottom: 10, padding: '8px 10px', background: 'rgba(248,81,73,0.06)', border: '1px solid rgba(248,81,73,0.25)', borderRadius: 6, fontSize: 11.5, color: 'var(--text-2)' }}>
                  <strong style={{ color: '#f85149' }}>Degraded mode:</strong>{' '}
                  AI provider unavailable (quota / rate limit). Showing raw trending signals below.
                </div>
              )}
              <div style={{ fontSize: 15, color: 'var(--text)', fontWeight: 500, lineHeight: 1.5, letterSpacing: '-0.005em' }}>
                {headline ?? (isLoading ? 'Loading latest brief...' : 'No threat briefing generated yet. Click "Re-run AI analysis" above or trigger from Scheduler.')}
              </div>
              {briefActions.length > 0 && (
                <div style={{ marginTop: 16, display: 'grid', gap: 8 }}>
                  {briefActions.map((a, i) => (
                    <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '10px 12px', background: 'var(--bg-elev)', borderRadius: 6, border: '1px solid var(--border-soft)' }}>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-4)', width: 22, paddingTop: 2 }}>{a.tag}</div>
                      <div style={{ flex: 1, fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.5 }}>{a.text}</div>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ marginTop: 14, display: 'flex', gap: 8 }}>
                <button className="btn" onClick={() => router.push('/operations/reports')}><FileText s={12} />Read full report</button>
              </div>
            </div>
          </div>

          {/* Top actors relevant to us — moved from right column. Comes from
              the orchestrator's actor_likelihood scoring against our profile. */}
          <div className="card">
            <div className="card-h">
              <Users s={13} />
              <div className="t">Top actors relevant to us</div>
              <div className="s">ranked by likelihood vs your profile</div>
              <div className="right"><a href="/actors" style={{ fontSize: 11.5, color: 'var(--accent)' }}>View all &rarr;</a></div>
            </div>
            <div className="card-b flush">
              {isLoading && <div style={{ padding: 14, color: 'var(--text-4)', fontSize: 12 }}>Loading...</div>}
              {!isLoading && (data?.top_actors?.length ?? 0) === 0 && (
                <div style={{ padding: 14, color: 'var(--text-4)', fontSize: 12 }}>No ranked actors yet. Run the analysis cycle.</div>
              )}
              {data?.top_actors?.map((a, i) => (
                <div key={a.id ?? a.name} onClick={() => router.push(`/actors/${a.id}`)} style={{ padding: '10px 14px', borderBottom: i < data!.top_actors.length - 1 ? '1px solid var(--border-soft)' : 'none', cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {a.origin_country && <Flag code={a.origin_country} />}
                    <span style={{ fontSize: 12.5, color: 'var(--text)', fontWeight: 500 }}>{a.name}</span>
                    <span className="mono" style={{ marginLeft: 'auto', fontSize: 11, color: i < 2 ? 'var(--crit)' : i < 4 ? 'var(--high)' : 'var(--med)' }}>
                      {(a.likelihood * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                    <div className="bar" style={{ flex: 1 }}>
                      <div className="fill" style={{ width: a.likelihood * 100 + '%', background: i < 2 ? 'var(--crit)' : i < 4 ? 'var(--high)' : 'var(--med)' }} />
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
                    {a.target_sectors?.slice(0, 3).join(' · ') || a.motivation?.join(' · ') || '—'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ASM findings — latest discoveries from the attack-surface scans.
              Lives bottom-left so the dashboard balances briefing + actor ranks
              with operational signals. */}
          <div className="card">
            <div className="card-h">
              <Layers s={13} />
              <div className="t">ASM findings</div>
              <div className="s">latest discoveries</div>
              <div className="right"><a href="/surface/scopes" style={{ fontSize: 11.5, color: 'var(--accent)' }}>View all &rarr;</a></div>
            </div>
            <div className="card-b flush">
              {asmFindings.length === 0 && (
                <div style={{ padding: 14, color: 'var(--text-4)', fontSize: 12 }}>
                  No findings yet. Configure a scope and trigger a scan.
                </div>
              )}
              {asmFindings.map((f, i) => (
                <div key={f.id} onClick={() => router.push('/surface/scopes')}
                     style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', borderBottom: i < asmFindings.length - 1 ? '1px solid var(--border-soft)' : 'none', cursor: 'pointer' }}>
                  <span className="tag" style={{ fontSize: 9 }}>{f.type}</span>
                  <div title={f.value} className="mono" style={{ flex: 1, fontSize: 11.5, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.value}</div>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>{f.source}</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)', minWidth: 64, textAlign: 'right' }}>{fmtDate(f.discovered_at)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Exploited in the Wild (CISA KEV) — promoted to top-right */}
          <div className="card">
            <div className="card-h">
              <Shield s={13} />
              <div className="t">Exploited in the Wild</div>
              <div className="s">CISA KEV matches</div>
              <div className="right"><a href="/intelligence/cves" style={{ fontSize: 11.5, color: 'var(--accent)' }}>View all &rarr;</a></div>
            </div>
            <div className="card-b flush">
              {kevCves.length === 0 && <div style={{ padding: 14, color: 'var(--text-4)', fontSize: 12 }}>No KEV entries yet.</div>}
              {kevCves.map((c, i) => (
                <div key={c.cve_id} onClick={() => router.push(`/intelligence/cves/${c.cve_id}`)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', borderBottom: i < kevCves.length - 1 ? '1px solid var(--border-soft)' : 'none', cursor: 'pointer' }}>
                  <span className="mono" style={{ fontSize: 11.5, color: 'var(--text)' }}>{c.cve_id}</span>
                  <span className={`badge ${(c.severity ?? '').toLowerCase() === 'critical' ? 'crit' : 'high'}`}>{c.severity ?? '—'}</span>
                  <div title={c.description ?? ''} style={{ flex: 1, fontSize: 12, color: 'var(--text-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.description?.slice(0, 70) ?? '—'}</div>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>{fmtDate(c.published_at)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Ransomware attacks */}
          <div className="card">
            <div className="card-h">
              <Skull s={13} />
              <div className="t">Recent ransomware attacks</div>
              <div className="right"><a href="/actors/ransomware" style={{ fontSize: 11.5, color: 'var(--accent)' }}>View all &rarr;</a></div>
            </div>
            <div className="card-b flush">
              {recentVictims.length === 0 && <div style={{ padding: 14, color: 'var(--text-4)', fontSize: 12 }}>No ransomware victims tracked yet.</div>}
              {recentVictims.map((v, i) => (
                <div key={v.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', borderBottom: i < recentVictims.length - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)', width: 60 }}>{fmtDate(v.disclosed_at)}</span>
                  <div style={{ flex: 1, fontSize: 12, color: 'var(--text-2)' }}>{v.victim_name}</div>
                  <span className="tag" style={{ fontSize: 9 }}>{v.sector ?? '—'}</span>
                  {v.country && <Flag code={v.country} />}
                </div>
              ))}
            </div>
          </div>

          {/* Recent scheduler runs */}
          <div className="card">
            <div className="card-h">
              <Clock s={13} />
              <div className="t">Recent scheduler runs</div>
              <div className="right">
                {data && data.recent_runs?.some(r => r.status === 'running') && (
                  <span className="badge low"><span className="dot pulse" />running</span>
                )}
              </div>
            </div>
            <div className="card-b flush">
              {isLoading && <div style={{ padding: 14, color: 'var(--text-4)', fontSize: 12 }}>Loading...</div>}
              {!isLoading && (data?.recent_runs?.length ?? 0) === 0 && (
                <div style={{ padding: 14, color: 'var(--text-4)', fontSize: 12 }}>No runs yet.</div>
              )}
              {data?.recent_runs?.map((r, i) => (
                <div key={r.run_id ?? i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', borderBottom: i < data!.recent_runs.length - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                  <StatusDot status={r.status} />
                  <div title={r.job_id} className="mono" style={{ fontSize: 11.5, color: 'var(--text-2)', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.job_id}</div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text-4)', width: 60, textAlign: 'right' }}>{fmtMs(r.duration_ms)}</div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text-4)', width: 80, textAlign: 'right' }}>{howLongAgo(r.triggered_at)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
