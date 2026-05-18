'use client';

import React, { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import FilterBar from '@/components/shared/FilterBar';
import SortHeader from '@/components/shared/SortHeader';
import Pagination from '@/components/shared/Pagination';
import { Download, Plus, More, Refresh, X } from '@/components/icons';
import { useThreats } from '@/lib/hooks';
import { useServerSort } from '@/lib/serverSort';
import { api } from '@/lib/api';

const PAGE_SIZE = 50;

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function sevBadge(s: string | null) {
  const sev = (s ?? '').toLowerCase();
  if (sev === 'critical') return <span className="badge crit">critical</span>;
  if (sev === 'high')     return <span className="badge high">high</span>;
  if (sev === 'medium')   return <span className="badge med">medium</span>;
  if (sev === 'low')      return <span className="badge low">low</span>;
  return <span className="badge mute">{s ?? 'unknown'}</span>;
}

export default function ThreatsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: '', type: 'supply_chain', severity: 'medium', summary: '', source_url: '' });

  const { sortBy, sortDir, toggle, sortParams } = useServerSort('observed_at', 'desc');

  const { items, total, isLoading, mutate } = useThreats({
    q: q || undefined,
    type: type || undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
    ...sortParams,
  });

  const handleCreate = useCallback(async () => {
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      await api.post('/threats', {
        title: form.title,
        type: form.type,
        severity: form.severity,
        summary: form.summary || null,
        source_url: form.source_url || null,
      });
      setShowModal(false);
      setForm({ title: '', type: 'supply_chain', severity: 'medium', summary: '', source_url: '' });
      mutate();
    } catch { /* ignore */ }
    finally { setCreating(false); }
  }, [form, mutate]);

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Threats</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total} tracked threats · sorted by ${sortBy} ${sortDir}`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn" onClick={() => {
            const blob = new Blob([JSON.stringify(items, null, 2)], { type: 'application/json' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = 'threats-export.json'; a.click();
          }}><Download s={12} />Export</button>
          <button className="btn primary" onClick={() => setShowModal(true)}><Plus s={12} />New threat</button>
        </div>
      </div>

      <FilterBar search="Search title, summary..." value={q} onSearch={(v) => { setQ(v); setPage(1); }}>
        <select className="select" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
          <option value="">All types</option>
          <option value="supply_chain">Supply chain</option>
          <option value="data_breach">Data breach</option>
          <option value="leak">Leak</option>
          <option value="disclosure">Disclosure</option>
          <option value="report">Report</option>
        </select>
      </FilterBar>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table className="tbl">
            <thead><tr>
              <SortHeader label="Type" sortKey="type" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 130 }} />
              <SortHeader label="Title" sortKey="title" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} />
              <SortHeader label="Severity" sortKey="severity" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 100 }} />
              <th style={{ width: 180 }}>Source</th>
              <SortHeader label="Observed" sortKey="observed_at" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
              <th style={{ width: 40 }}></th>
            </tr></thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>Loading threats...</td></tr>
              )}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>No threats found.</td></tr>
              )}
              {items.map((t) => (
                <tr key={t.id} style={{ cursor: 'pointer' }} onClick={() => router.push(`/intelligence/threats/${t.id}`)}>
                  <td><span className="tag">{t.type}</span></td>
                  <td className="primary">
                    <div style={{ fontWeight: 500, maxWidth: 580, wordBreak: 'break-word' }}>{t.title}</div>
                    {t.summary && (
                      <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 2, maxWidth: 580, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{t.summary}</div>
                    )}
                  </td>
                  <td>{sevBadge(t.severity)}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{t.source}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{fmtDate(t.observed_at)}</td>
                  <td><More s={14} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination total={total} page={page} pageSize={PAGE_SIZE} onChange={setPage} />
      </div>

      {/* ── New Threat Modal ── */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 520, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Plus s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>New threat</div>
              <button className="btn sm" onClick={() => setShowModal(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1 }}>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Title *</label>
                <input
                  className="input"
                  value={form.title}
                  onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="e.g. Supply chain compromise in banking middleware"
                  style={{ width: '100%' }}
                  autoFocus
                />
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Type</label>
                  <select className="select" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))} style={{ width: '100%' }}>
                    <option value="supply_chain">Supply chain</option>
                    <option value="data_breach">Data breach</option>
                    <option value="leak">Leak</option>
                    <option value="disclosure">Disclosure</option>
                    <option value="report">Report</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Severity</label>
                  <select className="select" value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))} style={{ width: '100%' }}>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Summary</label>
                <textarea
                  className="input"
                  value={form.summary}
                  onChange={e => setForm(f => ({ ...f, summary: e.target.value }))}
                  placeholder="Brief description of the threat…"
                  rows={3}
                  style={{ width: '100%', height: 'auto', resize: 'vertical' }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Source URL</label>
                <input
                  className="input mono"
                  value={form.source_url}
                  onChange={e => setForm(f => ({ ...f, source_url: e.target.value }))}
                  placeholder="https://..."
                  style={{ width: '100%', fontSize: 12 }}
                />
              </div>
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn primary" onClick={handleCreate} disabled={creating || !form.title.trim()}>
                {creating ? <><Refresh s={11} />Creating…</> : <><Plus s={11} />Create threat</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
