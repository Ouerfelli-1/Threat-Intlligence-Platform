'use client';

import React, { useCallback, useState } from 'react';
import FilterBar from '@/components/shared/FilterBar';
import KPI from '@/components/shared/KPI';
import { Server, Plus, More, Eye, Refresh, X } from '@/components/icons';
import { useAssets } from '@/lib/hooks';
import { api } from '@/lib/api';
import TagPicker from '@/components/shared/TagPicker';

function critBadge(c: string | null) {
  const v = (c ?? '').toLowerCase();
  if (v === 'critical') return <span className="badge crit">critical</span>;
  if (v === 'high')     return <span className="badge high">high</span>;
  if (v === 'medium')   return <span className="badge med">medium</span>;
  if (v === 'low')      return <span className="badge low">low</span>;
  return <span className="badge mute">{c ?? '—'}</span>;
}

const DEVICE_TYPES = [
  'server', 'workstation', 'database', 'firewall', 'switch', 'router', 'vpn',
  'appliance', 'domain-controller', 'atm', 'hsm', 'hypervisor',
];

export default function AssetsPage() {
  const [q, setQ]       = useState('');
  const [crit, setCrit] = useState('');
  const { items, total, isLoading, mutate } = useAssets({
    hostname: q || undefined,
    criticality: crit || undefined,
    limit: 500,
  });

  // Add asset modal
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating]   = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [form, setForm] = useState<{
    hostname: string; ip: string; os: string;
    device_type: string; criticality: string;
    owner: string; location: string; tags: string[];
  }>({
    hostname: '',
    ip: '',
    os: '',
    device_type: 'server',
    criticality: 'medium',
    owner: '',
    location: '',
    tags: [],
  });

  const handleCreate = useCallback(async () => {
    if (!form.hostname.trim()) { setError('Hostname is required'); return; }
    setCreating(true); setError(null);
    try {
      await api.post('/assets', {
        hostname: form.hostname.trim(),
        ip: form.ip.trim() || null,
        os: form.os.trim() || null,
        device_type: form.device_type || null,
        criticality: form.criticality || null,
        owner: form.owner.trim() || null,
        location: form.location.trim() || null,
        software: {},
        tags: form.tags,
      });
      setShowModal(false);
      setForm({ hostname: '', ip: '', os: '', device_type: 'server', criticality: 'medium', owner: '', location: '', tags: [] });
      mutate();
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  }, [form, mutate]);

  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const a of items) {
    const k = (a.criticality ?? '').toLowerCase();
    if (k && k in counts) (counts as Record<string, number>)[k]++;
  }

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Assets · CMDB</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total} tracked · canonical source for orchestrator + HIBP`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn primary" onClick={() => { setError(null); setShowModal(true); }}><Plus s={12} />Add asset</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 12 }}>
        <KPI label="Total assets"   value={isLoading ? '...' : total.toLocaleString()} delta="in CMDB" deltaDir="up" color="#58a6ff" />
        <KPI label="Critical"       value={String(counts.critical)} delta="crown jewels" deltaDir="up" color="#f85149" />
        <KPI label="High"           value={String(counts.high)}     delta="hardened"     deltaDir="up" color="#d29922" />
        <KPI label="Medium"         value={String(counts.medium)}   delta="standard"     deltaDir="up" color="#58a6ff" />
        <KPI label="Low / Endpoint" value={String(counts.low)}      delta="endpoints"    deltaDir="up" color="#3fb950" />
      </div>

      <FilterBar search="Hostname, IP..." value={q} onSearch={setQ}>
        <select className="select" value={crit} onChange={(e) => setCrit(e.target.value)}>
          <option value="">All criticality</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </FilterBar>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
        <table className="tbl">
          <thead><tr>
            <th style={{ width: 30 }}><input type="checkbox" /></th>
            <th>Hostname</th>
            <th style={{ width: 130 }}>IP</th>
            <th style={{ width: 140 }}>OS</th>
            <th style={{ width: 130 }}>Type</th>
            <th style={{ width: 110 }}>Criticality</th>
            <th style={{ width: 160 }}>Owner</th>
            <th style={{ width: 60 }}></th>
          </tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={8} style={{ textAlign: 'center', padding: 30, color: 'var(--text-4)' }}>Loading assets...</td></tr>}
            {!isLoading && items.length === 0 && <tr><td colSpan={8} style={{ textAlign: 'center', padding: 30, color: 'var(--text-4)' }}>No assets in CMDB yet. Click <strong>Add asset</strong> to register one.</td></tr>}
            {items.map((a) => (
              <tr key={a.id}>
                <td><input type="checkbox" /></td>
                <td className="primary mono" style={{ fontSize: 11.5 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Server s={11} />{a.hostname}</div>
                </td>
                <td className="mono" style={{ fontSize: 11 }}>{a.ip ?? '—'}</td>
                <td className="mono" style={{ fontSize: 11 }}>{a.os ?? '—'}</td>
                <td><span className="tag">{a.device_type ?? '—'}</span></td>
                <td>{critBadge(a.criticality)}</td>
                <td style={{ fontSize: 11.5, color: 'var(--text-3)' }}>{a.owner ?? '—'}</td>
                <td><span style={{ display: 'inline-flex', gap: 6 }}><Eye s={12} /><More s={12} /></span></td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* Add asset modal */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 560, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Server s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Add asset to CMDB</div>
              <button className="btn sm" onClick={() => setShowModal(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto', flex: 1 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Hostname *</label>
                  <input className="input mono" value={form.hostname} onChange={(e) => setForm((f) => ({ ...f, hostname: e.target.value }))} placeholder="e.g. core-t24-prod-01" style={{ width: '100%', fontSize: 12 }} autoFocus />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>IP address</label>
                  <input className="input mono" value={form.ip} onChange={(e) => setForm((f) => ({ ...f, ip: e.target.value }))} placeholder="e.g. 10.10.1.10" style={{ width: '100%', fontSize: 12 }} />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>OS</label>
                  <input className="input" value={form.os} onChange={(e) => setForm((f) => ({ ...f, os: e.target.value }))} placeholder="e.g. Ubuntu 22.04" style={{ width: '100%' }} />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Device type</label>
                  <select className="select" value={form.device_type} onChange={(e) => setForm((f) => ({ ...f, device_type: e.target.value }))} style={{ width: '100%' }}>
                    {DEVICE_TYPES.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Criticality</label>
                  <select className="select" value={form.criticality} onChange={(e) => setForm((f) => ({ ...f, criticality: e.target.value }))} style={{ width: '100%' }}>
                    <option value="critical">critical</option>
                    <option value="high">high</option>
                    <option value="medium">medium</option>
                    <option value="low">low</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Owner</label>
                  <input className="input" value={form.owner} onChange={(e) => setForm((f) => ({ ...f, owner: e.target.value }))} placeholder="e.g. Core Banking Ops" style={{ width: '100%' }} />
                </div>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Location</label>
                <input className="input" value={form.location} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} placeholder="e.g. DC1 - Casablanca primary" style={{ width: '100%' }} />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Tags (from admin catalog)</label>
                <TagPicker scope="asset" value={form.tags} onChange={(next) => setForm((f) => ({ ...f, tags: next }))} placeholder="Pick from catalog…" />
              </div>
              {error && (
                <div style={{ padding: '8px 10px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>{error}</div>
              )}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn primary" onClick={handleCreate} disabled={creating || !form.hostname.trim()}>
                {creating ? <><Refresh s={11} />Adding…</> : <><Plus s={11} />Add asset</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
