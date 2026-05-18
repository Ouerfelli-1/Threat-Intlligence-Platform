'use client';

import React, { useState } from 'react';
import StatusDot from '@/components/shared/StatusDot';
import KPI from '@/components/shared/KPI';
import { Play, Clock, Activity, More, Refresh, AlertTriangle, ChevronDown, ChevronRight } from '@/components/icons';
import { useJobs, useRuns } from '@/lib/hooks';
import { api } from '@/lib/api';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function howLongAgo(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60)    return `${s}s ago`;
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
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

function stBadge(s: string) {
  const v = s.toLowerCase();
  if (v === 'success' || v === 'completed') return <span className="badge low">success</span>;
  if (v === 'running')                       return <span className="badge med"><span className="dot pulse" />running</span>;
  if (v === 'failed' || v === 'error')       return <span className="badge crit">failed</span>;
  if (v === 'timeout')                       return <span className="badge high">timeout</span>;
  return <span className="badge mute">{s}</span>;
}

export default function SchedulerPage() {
  const { items: jobs,  isLoading: jLoading, mutate: refreshJobs } = useJobs();
  const { items: runs,  isLoading: rLoading, mutate: refreshRuns } = useRuns({ limit: 30 });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  // Visible refreshing flag — the SWR mutate() calls are quick enough that
  // the button used to appear inert. Show "Refreshing…" briefly so users
  // know the click registered.
  const [refreshing, setRefreshing] = useState(false);
  const handleRefresh = React.useCallback(async () => {
    setRefreshing(true);
    try { await Promise.all([refreshJobs(), refreshRuns()]); }
    finally { setTimeout(() => setRefreshing(false), 300); }
  }, [refreshJobs, refreshRuns]);

  const toggleRow = (runId: string) => {
    const next = new Set(expanded);
    if (next.has(runId)) next.delete(runId); else next.add(runId);
    setExpanded(next);
  };

  const successCount = runs.filter(r => r.status === 'success').length;
  const failedCount  = runs.filter(r => r.status === 'failed' || r.status === 'timeout').length;
  const runningCount = runs.filter(r => r.status === 'running').length;
  const totalRuns    = runs.length;

  async function trigger(jobId: string) {
    try {
      await api.post(`/jobs/${jobId}/trigger`);
      setTimeout(() => { refreshRuns(); refreshJobs(); }, 1000);
    } catch (e) {
      console.error('trigger failed', e);
    }
  }

  return (
    <div style={{ padding: 14, height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Scheduler</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={handleRefresh} disabled={refreshing}>
            <Refresh s={12} />{refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 12 }}>
        <KPI label="Recent runs"   value={String(totalRuns)}                                     delta="last 30" deltaDir="up" color="#58a6ff" />
        <KPI label="Success rate"  value={totalRuns ? `${Math.round(successCount / totalRuns * 100)}%` : '—'} delta={`${successCount} ok`} deltaDir="up" color="#3fb950" />
        <KPI label="Running"       value={String(runningCount)}                                  delta="now"     deltaDir="up" color="#d29922" live={runningCount > 0} />
        <KPI label="Failed"        value={String(failedCount)}                                   delta="needs attn" deltaDir="up" color="#f85149" />
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-h"><Clock s={13} /><div className="t">Jobs</div><div className="s">{jobs.length} registered</div></div>
        <div style={{ overflow: 'auto' }}>
          <table className="tbl">
            <thead><tr>
              <th>Job ID</th>
              <th>Trigger</th>
              <th style={{ width: 220 }}>Next run</th>
              <th style={{ width: 120 }}>Action</th>
            </tr></thead>
            <tbody>
              {jLoading && <tr><td colSpan={4} style={{ padding: 20, color: 'var(--text-4)' }}>Loading jobs...</td></tr>}
              {!jLoading && jobs.length === 0 && <tr><td colSpan={4} style={{ padding: 20, color: 'var(--text-4)' }}>No jobs registered.</td></tr>}
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td className="mono primary" style={{ fontSize: 11.5 }}>{j.id}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{j.trigger ?? j.schedule ?? '—'}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{j.next_run_time ? `${fmtDate(j.next_run_time)} (in ${howLongAgo(j.next_run_time).replace(' ago', '').replace(/^-/, '')})` : '—'}</td>
                  <td>
                    <button className="btn sm" onClick={() => trigger(j.id)}><Play s={11} />Trigger</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-h"><Activity s={13} /><div className="t">Recent runs</div><div className="s">last 30</div></div>
        <div style={{ overflow: 'auto' }}>
          <table className="tbl">
            <thead><tr>
              <th>Run ID</th>
              <th>Job</th>
              <th style={{ width: 90 }}>Status</th>
              <th style={{ width: 120 }}>Duration</th>
              <th style={{ width: 120 }}>Triggered</th>
              <th style={{ width: 40 }}></th>
            </tr></thead>
            <tbody>
              {rLoading && <tr><td colSpan={6} style={{ padding: 20, color: 'var(--text-4)' }}>Loading runs...</td></tr>}
              {!rLoading && runs.length === 0 && <tr><td colSpan={6} style={{ padding: 20, color: 'var(--text-4)' }}>No runs yet.</td></tr>}
              {runs.map((r) => {
                const isFailed = r.status === 'failed' || r.status === 'timeout' || r.status === 'error';
                const isExpanded = expanded.has(r.run_id);
                const httpStatus = (r as { http_status?: number | null }).http_status ?? null;
                const errorDetail = (r as { error_detail?: string | null }).error_detail ?? null;
                const hasDetails = !!errorDetail || httpStatus != null;
                return (
                  <React.Fragment key={r.run_id}>
                    <tr style={{ cursor: hasDetails ? 'pointer' : 'default' }} onClick={() => hasDetails && toggleRow(r.run_id)}>
                      <td className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>
                        {hasDetails && (isExpanded ? <ChevronDown s={10} /> : <ChevronRight s={10} />)} {r.run_id.slice(0, 8)}
                      </td>
                      <td className="mono" style={{ fontSize: 11 }}><StatusDot status={r.status} /> {r.job_id}</td>
                      <td>
                        {stBadge(r.status)}
                        {isFailed && httpStatus != null && (
                          <span style={{ marginLeft: 6, fontSize: 10, color: '#f85149', fontFamily: 'var(--mono)' }}>HTTP {httpStatus}</span>
                        )}
                      </td>
                      <td className="mono" style={{ fontSize: 11 }}>{fmtMs(r.duration_ms)}</td>
                      <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>{howLongAgo(r.triggered_at)}</td>
                      <td>{hasDetails ? (isExpanded ? <ChevronDown s={12} /> : <More s={12} />) : <More s={12} />}</td>
                    </tr>
                    {isExpanded && hasDetails && (
                      <tr style={{ background: 'rgba(248,81,73,0.04)' }}>
                        <td colSpan={6} style={{ padding: '8px 14px' }}>
                          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                            <AlertTriangle s={11} style={{ color: '#f85149' }} />Failure detail
                          </div>
                          {httpStatus != null && (
                            <div style={{ marginBottom: 4, fontSize: 11.5 }}>
                              <span style={{ color: 'var(--text-4)' }}>Target responded with</span>{' '}
                              <span className="mono" style={{ color: '#f85149', fontWeight: 600 }}>HTTP {httpStatus}</span>
                            </div>
                          )}
                          {errorDetail ? (
                            <pre style={{ fontSize: 11, color: 'var(--text-2)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, padding: '8px 10px', background: 'var(--bg-page)', borderRadius: 4, maxHeight: 220, overflow: 'auto' }}>
                              {errorDetail}
                            </pre>
                          ) : (
                            <div style={{ fontSize: 11.5, color: 'var(--text-4)' }}>
                              No textual error captured. Check the target service&apos;s container logs for the stack trace.
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
