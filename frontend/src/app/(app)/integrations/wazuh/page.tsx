'use client';

import React, { useMemo, useState } from 'react';
import FilterBar from '@/components/shared/FilterBar';
import KPI from '@/components/shared/KPI';
import { Refresh, Server } from '@/components/icons';
import { useList } from '@/lib/hooks';
import { api } from '@/lib/api';

interface WazuhAlert {
  alert_id: string;
  agent_id: string;
  agent_name: string;
  rule_id: string;
  rule_description: string;
  severity: number;
  timestamp: string;
  raw: Record<string, unknown>;
}

interface WazuhAgent {
  agent_id: string;
  hostname: string;
  ip: string | null;
  os: string | null;
  version: string | null;
  last_seen: string | null;
  status: string;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function lvlColor(l: number) {
  return l >= 12 ? 'crit' : l >= 8 ? 'high' : l >= 5 ? 'med' : 'low';
}

export default function WazuhPage() {
  const [minSev, setMinSev] = useState(0);
  const [search, setSearch] = useState('');
  const [syncing, setSyncing] = useState(false);

  const { items: alerts, isLoading: aLoading, mutate: mutAlerts } =
    useList<WazuhAlert>('/wazuh/alerts', minSev > 0 ? { severity_gte: minSev } : undefined);
  const { items: agents, isLoading: agLoading } = useList<WazuhAgent>('/wazuh/agents');

  // Client-side text filter — backend doesn't support free-text search on alerts,
  // and the row count is small enough that filtering in-browser is fine.
  const filteredAlerts = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return alerts;
    return alerts.filter(a =>
      a.rule_id?.toLowerCase().includes(q) ||
      a.rule_description?.toLowerCase().includes(q) ||
      a.agent_name?.toLowerCase().includes(q) ||
      a.agent_id?.toLowerCase().includes(q)
    );
  }, [alerts, search]);

  const crit   = filteredAlerts.filter(a => a.severity >= 12).length;
  const high   = filteredAlerts.filter(a => a.severity >= 8 && a.severity < 12).length;
  const low    = filteredAlerts.filter(a => a.severity < 8).length;
  const active = agents.filter(a => a.status === 'active' || a.status === 'Active').length;

  async function syncWazuh() {
    setSyncing(true);
    try {
      await api.post('/wazuh/sync');
      setTimeout(() => { mutAlerts(); setSyncing(false); }, 2000);
    } catch {
      setSyncing(false);
    }
  }

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Wazuh — alerts</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {aLoading
            ? 'loading…'
            : search
              ? `${filteredAlerts.length} of ${alerts.length} alerts · ${agents.length} agents · ${active} active`
              : `${alerts.length} alerts · ${agents.length} agents · ${active} active`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={syncWazuh} disabled={syncing}>
            <Refresh s={12} />{syncing ? 'Syncing…' : 'Sync'}
          </button>
          {/* The "Open in Wazuh" button used to live here but had no URL source
              wired to it. Re-add only when the Wazuh dashboard URL is exposed
              via a settings field (e.g. WAZUH_DASHBOARD_URL in secrets). */}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 12 }}>
        <KPI label="Level 12+ alerts"  value={String(crit)}   delta="critical" deltaDir="up" color="#f85149" live={crit > 0} />
        <KPI label="Level 8–11 alerts" value={String(high)}   delta="high"     deltaDir="up" color="#d29922" />
        <KPI label="Level ≤ 7 alerts"  value={String(low)}    delta="low"      deltaDir="dn" color="#2dd4bf" />
        <KPI label="Agents online"     value={`${active}/${agents.length}`} delta="active" deltaDir="dn" color="#3fb950" />
      </div>

      <FilterBar search="Rule ID, agent, description..." value={search} onSearch={setSearch}>
        <select className="select" value={minSev} onChange={e => setMinSev(Number(e.target.value))}>
          <option value={0}>All levels</option>
          <option value={5}>Level ≥ 5</option>
          <option value={7}>Level ≥ 7</option>
          <option value={10}>Level ≥ 10</option>
          <option value={12}>Level ≥ 12</option>
        </select>
      </FilterBar>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 12, flex: 1, minHeight: 0 }}>
        <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ overflow: 'auto', flex: 1 }}>
            {aLoading && <div style={{ padding: 20, color: 'var(--text-4)' }}>Loading alerts…</div>}
            {!aLoading && alerts.length === 0 && (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                No Wazuh alerts found. Configure Wazuh credentials in the secrets service or trigger a sync.
              </div>
            )}
            {!aLoading && alerts.length > 0 && filteredAlerts.length === 0 && (
              <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                {alerts.length} alert{alerts.length === 1 ? '' : 's'} loaded but none match the current filter.
              </div>
            )}
            {filteredAlerts.length > 0 && (
              <table className="tbl">
                <thead><tr>
                  <th style={{ width: 70 }}>Level</th>
                  <th style={{ width: 140 }}>Agent</th>
                  <th>Rule</th>
                  <th style={{ width: 170 }}>When</th>
                </tr></thead>
                <tbody>
                  {filteredAlerts.map((a) => (
                    <tr key={a.alert_id} style={{ cursor: 'pointer' }}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span className={`sev-dot ${lvlColor(a.severity)}`} />
                          <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: `var(--${lvlColor(a.severity)})` }}>L{a.severity}</span>
                        </div>
                      </td>
                      <td className="mono" style={{ fontSize: 11.5 }}>{a.agent_name || a.agent_id}</td>
                      <td className="primary" style={{ fontSize: 12 }}>
                        <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)', marginRight: 6 }}>{a.rule_id}</span>
                        {a.rule_description}
                      </td>
                      <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>{fmtDate(a.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div className="card-h"><Server s={13} /><div className="t">Agents</div><div className="s">{agents.length} total</div></div>
          <div style={{ overflow: 'auto', flex: 1 }}>
            {agLoading && <div style={{ padding: 20, color: 'var(--text-4)', fontSize: 12 }}>Loading agents…</div>}
            {!agLoading && agents.length === 0 && (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>No agents enrolled</div>
            )}
            {agents.map((a, i) => (
              <div key={a.agent_id} style={{ padding: '8px 12px', borderBottom: i < agents.length - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span className={`sev-dot ${a.status === 'active' || a.status === 'Active' ? 'low' : 'high'}`} />
                  <span className="mono" style={{ fontSize: 11.5, color: 'var(--text)' }}>{a.hostname}</span>
                </div>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-4)', marginTop: 2 }}>
                  {a.os ?? '—'} · {a.ip ?? 'no IP'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
