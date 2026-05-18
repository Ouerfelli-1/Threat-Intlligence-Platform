'use client';

import React, { useState } from 'react';
import FilterBar from '@/components/shared/FilterBar';
import { Refresh, Upload, Plus } from '@/components/icons';
import { useList } from '@/lib/hooks';
import { api } from '@/lib/api';

interface MispEvent {
  event_id: string;
  info: string;
  threat_level_id: number | null;
  analysis: string | null;
  date: string | null;
  org: string | null;
  raw: Record<string, unknown>;
}

interface MispIoc {
  id: string;
  event_id: string;
  type: string;
  normalized_value: string;
  raw_value: string;
  comment: string | null;
  to_ids: boolean;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function tlColor(t: number | null) {
  if (t === 1) return 'crit';
  if (t === 2) return 'high';
  if (t === 3) return 'med';
  return 'low';
}

function tlLabel(t: number | null) {
  if (t === 1) return 'High';
  if (t === 2) return 'Medium';
  if (t === 3) return 'Low';
  return 'Unknown';
}

function analysisLabel(a: string | null) {
  if (!a) return 'Unknown';
  const n = Number(a);
  if (n === 0) return 'Initial';
  if (n === 1) return 'Ongoing';
  if (n === 2) return 'Completed';
  // If it's already a human-readable string
  return a;
}

function analysisColor(a: string | null) {
  const label = analysisLabel(a);
  if (label === 'Completed') return 'low';
  if (label === 'Initial') return 'high';
  return 'med';
}

export default function MispPage() {
  const [syncing, setSyncing] = useState(false);

  const { items: events, isLoading, mutate } = useList<MispEvent>('/misp/events');
  const { items: iocs } = useList<MispIoc>('/misp/iocs');

  async function syncMisp() {
    setSyncing(true);
    try {
      await api.post('/misp/sync');
      setTimeout(() => { mutate(); setSyncing(false); }, 2000);
    } catch {
      setSyncing(false);
    }
  }

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>MISP — events</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading…' : `${events.length} events · ${iocs.length} IOC attributes synced`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={syncMisp} disabled={syncing}>
            <Refresh s={12} />{syncing ? 'Syncing…' : 'Sync'}
          </button>
          <button className="btn"><Upload s={12} />Push IOCs</button>
          <button className="btn primary"><Plus s={12} />New event</button>
        </div>
      </div>

      <FilterBar search="Event info, org...">
        <select className="select"><option value="">All threat levels</option></select>
      </FilterBar>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ overflow: 'auto', flex: 1 }}>
          {isLoading && (
            <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>Loading MISP events…</div>
          )}
          {!isLoading && events.length === 0 && (
            <div style={{ padding: 50, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
              <div style={{ fontSize: 16, marginBottom: 8 }}>No MISP events</div>
              <div>Configure MISP credentials in the secrets service and trigger a sync, or events will be pulled on the next scheduled cycle.</div>
            </div>
          )}
          {events.length > 0 && (
            <table className="tbl">
              <thead><tr>
                <th style={{ width: 80 }}>Event ID</th>
                <th style={{ width: 110 }}>Threat level</th>
                <th style={{ width: 100 }}>Analysis</th>
                <th>Info</th>
                <th style={{ width: 120 }}>Org</th>
                <th style={{ width: 90 }}>Date</th>
              </tr></thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.event_id} style={{ cursor: 'pointer' }}>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>#{e.event_id}</td>
                    <td><span className={`badge ${tlColor(e.threat_level_id)}`}>{tlLabel(e.threat_level_id)}</span></td>
                    <td><span className={`badge ${analysisColor(e.analysis)}`}>{analysisLabel(e.analysis)}</span></td>
                    <td className="primary" style={{ fontSize: 12 }}>{e.info}</td>
                    <td style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{e.org ?? '—'}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{fmtDate(e.date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
