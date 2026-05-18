'use client';

import React, { useCallback, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import FilterBar from '@/components/shared/FilterBar';
import Pagination from '@/components/shared/Pagination';
import Bar from '@/components/shared/Bar';
import SortHeader from '@/components/shared/SortHeader';
import { Refresh, Plus, More, Crosshair, X, Download, Layers, Check, AlertTriangle } from '@/components/icons';
import { useIndicators } from '@/lib/hooks';
import { useServerSort } from '@/lib/serverSort';
import { api } from '@/lib/api';
import TagPicker from '@/components/shared/TagPicker';

const PAGE_SIZE = 50;

/* eslint-disable @typescript-eslint/no-explicit-any */

interface LookupHit {
  type: string;
  value: string;
  normalized_value: string;
  found: boolean;
  indicator: {
    id: string;
    type: string;
    normalized_value: string;
    raw_value: string;
    first_seen: string;
    last_seen: string;
    tags: string[];
    confidence_score: number;
    analyst_status: string;
  } | null;
}

function typeBadge(t: string) {
  const m: Record<string, string> = {
    ip: 'low', ipv4: 'low', ipv6: 'low',
    domain: 'med', url: 'med',
    sha256: 'high', sha1: 'high', md5: 'high',
  };
  return <span className={`badge ${m[t] ?? 'mute'}`}>{t}</span>;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function inferType(v: string): string {
  const s = v.trim();
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(s)) return 'ip';
  if (/^[a-fA-F0-9]{64}$/.test(s)) return 'sha256';
  if (/^[a-fA-F0-9]{40}$/.test(s)) return 'sha1';
  if (/^[a-fA-F0-9]{32}$/.test(s)) return 'md5';
  if (s.includes('://')) return 'url';
  return 'domain';
}

export default function IocsPage() {
  const router = useRouter();
  const [page, setPage]       = useState(1);
  const [type, setType]       = useState('');
  const [q, setQ]             = useState('');
  const [minConf, setMinConf] = useState(0);

  // Manual add modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [creating, setCreating]         = useState(false);
  const [form, setForm] = useState<{ type: string; value: string; tags: string[]; malware_family: string; threat_type: string }>(
    { type: 'ip', value: '', tags: [], malware_family: '', threat_type: '' }
  );

  // Bulk lookup modal
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkText, setBulkText]           = useState('');
  const [bulkLoading, setBulkLoading]     = useState(false);
  const [bulkHits, setBulkHits]           = useState<LookupHit[] | null>(null);
  const [bulkError, setBulkError]         = useState<string | null>(null);

  const { sortBy, sortDir, toggle, sortParams } = useServerSort('last_seen', 'desc');

  const { items, total, isLoading, mutate } = useIndicators({
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
    type: type || undefined,
    q: q || undefined,
    min_confidence: minConf > 0 ? minConf : undefined,
    ...sortParams,
  });

  const handleCreate = useCallback(async () => {
    if (!form.value.trim()) return;
    setCreating(true);
    try {
      await api.post('/indicators', {
        type: form.type,
        value: form.value.trim(),
        tags: form.tags,
        malware_family: form.malware_family || null,
        threat_type: form.threat_type || null,
      });
      setShowAddModal(false);
      setForm({ type: 'ip', value: '', tags: [], malware_family: '', threat_type: '' });
      mutate();
    } catch { /* ignore */ }
    finally { setCreating(false); }
  }, [form, mutate]);

  const handleBulkLookup = useCallback(async () => {
    const lines = bulkText.split('\n').map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;
    setBulkLoading(true);
    setBulkError(null);
    setBulkHits(null);
    try {
      const indicators = lines.map((v) => ({ type: inferType(v), value: v }));
      const res = await api.post<{ hits: LookupHit[] }>('/indicators/lookup', { indicators });
      setBulkHits(res.hits ?? []);
    } catch (e) {
      setBulkError(String(e));
    } finally {
      setBulkLoading(false);
    }
  }, [bulkText]);

  const bulkSummary = useMemo(() => {
    if (!bulkHits) return null;
    const found = bulkHits.filter((h) => h.found).length;
    return { total: bulkHits.length, found, missed: bulkHits.length - found };
  }, [bulkHits]);

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>IOC Library</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total.toLocaleString()} indicators · sorted by ${sortBy} ${sortDir}`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn" onClick={() => { setShowBulkModal(true); setBulkHits(null); setBulkError(null); setBulkText(''); }}>
            <Layers s={12} />Bulk lookup
          </button>
          <button className="btn" onClick={() => {
            const blob = new Blob([JSON.stringify(items, null, 2)], { type: 'application/json' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = 'iocs-export.json'; a.click();
          }}><Download s={12} />Export</button>
          <button className="btn primary" onClick={() => setShowAddModal(true)}><Plus s={12} />Add manual IOC</button>
        </div>
      </div>

      <FilterBar
        search="IP, domain, hash, URL, tag..."
        value={q}
        onSearch={(v) => { setQ(v); setPage(1); }}
      >
        <select className="select" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
          <option value="">All types</option>
          <option value="ip">IP</option>
          <option value="domain">Domain</option>
          <option value="url">URL</option>
          <option value="sha256">SHA-256</option>
          <option value="sha1">SHA-1</option>
          <option value="md5">MD5</option>
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--text-3)' }}>
          Confidence &ge;
          <input
            type="range"
            min={0}
            max={100}
            value={minConf * 100}
            onChange={(e) => { setMinConf(parseInt(e.target.value) / 100); setPage(1); }}
            style={{ width: 120 }}
          />
          <span className="mono" style={{ fontSize: 11, width: 32 }}>{minConf.toFixed(2)}</span>
        </div>
      </FilterBar>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table className="tbl">
            <thead><tr>
              <SortHeader label="Type" sortKey="type" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 90 }} />
              <SortHeader label="Value" sortKey="normalized_value" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} />
              <SortHeader label="First seen" sortKey="first_seen" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 160 }} />
              <SortHeader label="Last seen" sortKey="last_seen" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 160 }} />
              <SortHeader label="Confidence" sortKey="confidence_score" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 140 }} />
              <th style={{ width: 220 }}>Tags</th>
              <th style={{ width: 40 }}></th>
            </tr></thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>Loading IOCs...</td></tr>
              )}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>No indicators match the filters.</td></tr>
              )}
              {items.map((ioc) => (
                <tr key={ioc.id} style={{ cursor: 'pointer' }} onClick={() => router.push(`/iocs/${ioc.id}`)}>
                  <td>{typeBadge(ioc.type)}</td>
                  <td className="mono primary" style={{ fontSize: 11.5, maxWidth: 540, wordBreak: 'break-all' }}>
                    <Crosshair s={11} /> {ioc.normalized_value}
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>{fmtDate(ioc.first_seen)}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{fmtDate(ioc.last_seen)}</td>
                  <td><Bar value={ioc.confidence_score} variant={ioc.confidence_score > 0.85 ? 'low' : ioc.confidence_score > 0.6 ? '' : 'high'} /></td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {ioc.tags.slice(0, 3).map((t) => <span key={t} className="tag">{t}</span>)}
                      {ioc.tags.length > 3 && <span className="tag">+{ioc.tags.length - 3}</span>}
                    </div>
                  </td>
                  <td><More s={14} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination total={total} page={page} pageSize={PAGE_SIZE} onChange={setPage} />
      </div>

      {/* Add Manual IOC Modal */}
      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 480, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Crosshair s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Add manual IOC</div>
              <button className="btn sm" onClick={() => setShowAddModal(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1 }}>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ width: 140 }}>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Type</label>
                  <select className="select" value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))} style={{ width: '100%' }}>
                    <option value="ip">IP</option>
                    <option value="domain">Domain</option>
                    <option value="url">URL</option>
                    <option value="sha256">SHA-256</option>
                    <option value="sha1">SHA-1</option>
                    <option value="md5">MD5</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Value *</label>
                  <input className="input mono" value={form.value} onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
                    placeholder="e.g. 203.0.113.5" style={{ width: '100%', fontSize: 12 }} autoFocus />
                </div>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Tags (from admin catalog)</label>
                <TagPicker scope="ioc" value={form.tags} onChange={(next) => setForm((f) => ({ ...f, tags: next }))} placeholder="Pick from catalog…" />
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Malware family</label>
                  <input className="input" value={form.malware_family} onChange={(e) => setForm((f) => ({ ...f, malware_family: e.target.value }))}
                    placeholder="e.g. Cobalt Strike" style={{ width: '100%' }} />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Threat type</label>
                  <input className="input" value={form.threat_type} onChange={(e) => setForm((f) => ({ ...f, threat_type: e.target.value }))}
                    placeholder="e.g. botnet_cc" style={{ width: '100%' }} />
                </div>
              </div>
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button className="btn primary" onClick={handleCreate} disabled={creating || !form.value.trim()}>
                {creating ? <><Refresh s={11} />Adding…</> : <><Plus s={11} />Add IOC</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk lookup modal */}
      {showBulkModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 20 }}>
          <div style={{ width: 720, maxHeight: '90vh', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Layers s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Bulk lookup against IOC library</div>
              <button className="btn sm" onClick={() => setShowBulkModal(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto', flex: 1 }}>
              <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                Paste a list of IPs, domains, URLs, or hashes — one per line. Each is checked against the local library;
                no external traffic. Type is auto-detected per row.
              </div>
              <textarea
                className="input mono"
                rows={8}
                value={bulkText}
                onChange={(e) => setBulkText(e.target.value)}
                placeholder={'8.8.8.8\nevil.example.com\n44d88612fea8a8f36de82e1278abb02f\nhttps://phish.test/login'}
                style={{ width: '100%', fontSize: 11.5, fontFamily: 'var(--mono)', boxSizing: 'border-box' }}
              />
              {bulkError && (
                <div style={{ padding: '8px 10px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>
                  <AlertTriangle s={11} style={{ marginRight: 4 }} />{bulkError}
                </div>
              )}

              {bulkSummary && (
                <div style={{ display: 'flex', gap: 12, fontSize: 11.5 }}>
                  <span style={{ color: 'var(--text-3)' }}><strong style={{ color: 'var(--text)' }}>{bulkSummary.total}</strong> indicators looked up</span>
                  <span style={{ color: '#f85149' }}>
                    <Crosshair s={11} style={{ marginRight: 4 }} /><strong>{bulkSummary.found}</strong> found in library
                  </span>
                  <span style={{ color: '#3fb950' }}>
                    <Check s={11} style={{ marginRight: 4 }} /><strong>{bulkSummary.missed}</strong> not in library
                  </span>
                </div>
              )}

              {bulkHits && bulkHits.length > 0 && (
                <div style={{ border: '1px solid var(--border)', borderRadius: 6, overflow: 'auto', maxHeight: 320 }}>
                  <table className="tbl" style={{ fontSize: 11.5 }}>
                    <thead><tr>
                      <th style={{ width: 80 }}>Type</th>
                      <th>Value</th>
                      <th style={{ width: 110 }}>Status</th>
                      <th style={{ width: 110 }}>Confidence</th>
                      <th style={{ width: 40 }}></th>
                    </tr></thead>
                    <tbody>
                      {bulkHits.map((h, i) => (
                        <tr key={i} style={{ cursor: h.found ? 'pointer' : 'default' }}
                          onClick={() => h.found && h.indicator && router.push(`/iocs/${h.indicator.id}`)}>
                          <td>{typeBadge(h.type)}</td>
                          <td className="mono" style={{ fontSize: 11 }}>{h.normalized_value || h.value}</td>
                          <td>
                            {h.found
                              ? <span style={{ color: '#f85149', fontSize: 11 }}><Crosshair s={10} /> in library</span>
                              : <span style={{ color: '#3fb950', fontSize: 11 }}><Check s={10} /> clean</span>}
                          </td>
                          <td className="mono" style={{ fontSize: 11 }}>
                            {h.indicator ? h.indicator.confidence_score.toFixed(2) : '—'}
                          </td>
                          <td>{h.found && <span style={{ color: 'var(--accent)' }}>›</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text-4)', alignSelf: 'center' }}>
                {bulkText.split('\n').filter((l) => l.trim()).length} indicators ready
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn" onClick={() => setShowBulkModal(false)}>Close</button>
                <button className="btn primary" onClick={handleBulkLookup} disabled={bulkLoading || bulkText.split('\n').filter((l) => l.trim()).length === 0}>
                  {bulkLoading ? <><Refresh s={11} style={{ animation: 'spin 1s linear infinite' }} />Looking up…</> : <><Layers s={11} />Run lookup</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
