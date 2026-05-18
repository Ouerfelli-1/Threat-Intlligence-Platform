'use client';

import React, { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import FilterBar from '@/components/shared/FilterBar';
import SortHeader from '@/components/shared/SortHeader';
import Pagination from '@/components/shared/Pagination';
import Flag from '@/components/shared/Flag';
import { Refresh, Plus, More, X, Download } from '@/components/icons';
import { useActors } from '@/lib/hooks';
import { useSortable } from '@/lib/sort';
import { api } from '@/lib/api';

const PAGE_SIZE = 50;

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

const MOTIVATION_OPTIONS = ['financial-gain', 'cyberespionage', 'hacktivism', 'destruction', 'information-theft', 'sabotage'];
const SECTOR_OPTIONS = ['finance', 'banking', 'government', 'energy', 'telecom', 'healthcare', 'technology', 'defense', 'education', 'retail'];

export default function ActorListPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [name, setName] = useState('');
  const [sector, setSector] = useState('');
  const [motivation, setMotivation] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: '', origin_country: '', motivation: [] as string[], target_sectors: [] as string[],
  });

  const { items, total, isLoading, mutate } = useActors({
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
    name: name || undefined,
    sector: sector || undefined,
    motivation: motivation || undefined,
  });

  const toggleArr = (arr: string[], val: string) =>
    arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val];

  const handleCreate = useCallback(async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    try {
      await api.post('/actors', {
        name: form.name,
        origin_country: form.origin_country || null,
        motivation: form.motivation,
        target_sectors: form.target_sectors,
      });
      setShowModal(false);
      setForm({ name: '', origin_country: '', motivation: [], target_sectors: [] });
      mutate();
    } catch { /* ignore */ }
    finally { setCreating(false); }
  }, [form, mutate]);

  const { sorted, sortKey, sortDir, toggle } = useSortable(items, 'name', 'asc');

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Threat actors</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total} profiled · MITRE ATT&CK groups + curated ransomware operators`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn" onClick={() => {
            const blob = new Blob([JSON.stringify(items, null, 2)], { type: 'application/json' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = 'actors-export.json'; a.click();
          }}><Download s={12} />Export</button>
          <button className="btn primary" onClick={() => setShowModal(true)}><Plus s={12} />Manual actor</button>
        </div>
      </div>

      <FilterBar search="Search by name, alias..." value={name} onSearch={(v) => { setName(v); setPage(1); }}>
        <select className="select" value={sector} onChange={(e) => { setSector(e.target.value); setPage(1); }}>
          <option value="">All sectors</option>
          <option value="finance">Finance</option>
          <option value="banking">Banking</option>
          <option value="government">Government</option>
          <option value="energy">Energy</option>
          <option value="telecom">Telecom</option>
        </select>
        <select className="select" value={motivation} onChange={(e) => { setMotivation(e.target.value); setPage(1); }}>
          <option value="">All motivations</option>
          <option value="financial-gain">Financial</option>
          <option value="cyberespionage">Espionage</option>
          <option value="hacktivism">Hacktivism</option>
          <option value="destruction">Destruction</option>
        </select>
      </FilterBar>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table className="tbl">
            <thead><tr>
              <SortHeader label="Name" sortKey="name" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} />
              <SortHeader label="MITRE ID" sortKey="mitre_id" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 100 }} />
              <th style={{ width: 60 }}>Origin</th>
              <th style={{ width: 240 }}>Motivation</th>
              <th style={{ width: 260 }}>Target sectors</th>
              <SortHeader label="Last seen" sortKey="last_seen" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 100 }} />
              <SortHeader label="Status" sortKey="status" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 100 }} />
              <th style={{ width: 40 }}></th>
            </tr></thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>Loading actors...</td></tr>
              )}
              {!isLoading && sorted.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>No actors match these filters.</td></tr>
              )}
              {sorted.map((a) => (
                <tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => router.push(`/actors/${a.id}`)}>
                  <td className="primary" style={{ fontWeight: 600 }}>{a.name}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{a.mitre_id ?? '—'}</td>
                  <td>{a.origin_country ? <Flag code={a.origin_country} /> : '—'}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {a.motivation.slice(0, 3).map(m => <span key={m} className="tag">{m}</span>)}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {a.target_sectors.slice(0, 4).map(s => <span key={s} className="tag">{s}</span>)}
                      {a.target_sectors.length > 4 && <span className="tag">+{a.target_sectors.length - 4}</span>}
                    </div>
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>{fmtDate(a.last_seen)}</td>
                  <td><span className={`badge ${a.status === 'active' ? 'low' : 'mute'}`}>{a.status}</span></td>
                  <td><More s={14} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination total={total} page={page} pageSize={PAGE_SIZE} onChange={setPage} />
      </div>

      {/* ── Manual Actor Modal ── */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 520, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Plus s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Manual actor</div>
              <button className="btn sm" onClick={() => setShowModal(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1 }}>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Actor name *</label>
                <input
                  className="input"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. BMA regional adversary"
                  style={{ width: '100%' }}
                  autoFocus
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Origin country (ISO 2-letter code)</label>
                <input
                  className="input mono"
                  value={form.origin_country}
                  onChange={e => setForm(f => ({ ...f, origin_country: e.target.value.toUpperCase().slice(0, 2) }))}
                  placeholder="e.g. MA, CN, RU"
                  style={{ width: 120, fontSize: 12 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 6 }}>Motivation</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {MOTIVATION_OPTIONS.map(m => (
                    <button
                      key={m}
                      className={`tag ${form.motivation.includes(m) ? '' : ''}`}
                      style={{
                        cursor: 'pointer', padding: '4px 10px', fontSize: 11,
                        background: form.motivation.includes(m) ? 'var(--accent-bg)' : 'var(--bg-elev)',
                        border: form.motivation.includes(m) ? '1px solid var(--accent)' : '1px solid var(--border)',
                        color: form.motivation.includes(m) ? 'var(--accent)' : 'var(--text-3)',
                      }}
                      onClick={() => setForm(f => ({ ...f, motivation: toggleArr(f.motivation, m) }))}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 6 }}>Target sectors</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {SECTOR_OPTIONS.map(s => (
                    <button
                      key={s}
                      className="tag"
                      style={{
                        cursor: 'pointer', padding: '4px 10px', fontSize: 11,
                        background: form.target_sectors.includes(s) ? 'var(--accent-bg)' : 'var(--bg-elev)',
                        border: form.target_sectors.includes(s) ? '1px solid var(--accent)' : '1px solid var(--border)',
                        color: form.target_sectors.includes(s) ? 'var(--accent)' : 'var(--text-3)',
                      }}
                      onClick={() => setForm(f => ({ ...f, target_sectors: toggleArr(f.target_sectors, s) }))}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn primary" onClick={handleCreate} disabled={creating || !form.name.trim()}>
                {creating ? <><Refresh s={11} />Creating…</> : <><Plus s={11} />Create actor</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
