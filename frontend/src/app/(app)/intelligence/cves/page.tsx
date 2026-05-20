'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import FilterBar from '@/components/shared/FilterBar';
import SortHeader from '@/components/shared/SortHeader';
import Pagination from '@/components/shared/Pagination';
import { Refresh, More } from '@/components/icons';
import { useCVEs, type CVE } from '@/lib/hooks';
import { useServerSort } from '@/lib/serverSort';

const PAGE_SIZE = 50;

function sevClass(sev: string | null): { tag: string; color: string } {
  const s = (sev ?? '').toLowerCase();
  if (s === 'critical') return { tag: 'crit', color: 'var(--crit)' };
  if (s === 'high')     return { tag: 'high', color: 'var(--high)' };
  if (s === 'medium')   return { tag: 'med',  color: 'var(--med)' };
  if (s === 'low')      return { tag: 'low',  color: 'var(--low)' };
  return { tag: 'mute', color: 'var(--text-4)' };
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function productLabel(c: CVE): string {
  const ap = c.affected_products ?? {};
  const items = Array.isArray(ap.items) ? ap.items as Array<Record<string, unknown>> : [];
  if (items.length === 0) return c.description?.split(' ').slice(0, 8).join(' ') ?? '—';
  const first = items[0];
  const vendor  = (first.vendor as string) ?? '';
  const product = (first.product as string) ?? '';
  return [vendor, product].filter(Boolean).join(' ');
}

export default function CveListPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [severity, setSeverity] = useState<string>('');
  const [kevOnly, setKevOnly] = useState(false);
  const [showNotRel, setShowNotRel] = useState(false);

  // Default sort: most recently modified first (matches when CVE was last updated upstream).
  const { sortBy, sortDir, toggle, sortParams } = useServerSort('last_modified_at', 'desc');

  const { items, total, isLoading, mutate } = useCVEs({
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
    q: q || undefined,
    severity: severity || undefined,
    kev: kevOnly || undefined,
    include_not_relevant: showNotRel || undefined,
    ...sortParams,
  });

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>CVEs</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total.toLocaleString()} tracked · sorted by ${sortBy} ${sortDir}`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
        </div>
      </div>

      <FilterBar search="CVE-ID, product, description..." value={q} onSearch={(v) => { setQ(v); setPage(1); }}>
        <select className="select" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}>
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <label style={{ fontSize: 11.5, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <input type="checkbox" checked={kevOnly} onChange={(e) => { setKevOnly(e.target.checked); setPage(1); }} style={{ accentColor: '#2dd4bf' }} />Exploited in the Wild
        </label>
        <label style={{ fontSize: 11.5, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <input type="checkbox" checked={showNotRel} onChange={(e) => setShowNotRel(e.target.checked)} style={{ accentColor: '#2dd4bf' }} />Show not-rel
        </label>
      </FilterBar>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table className="tbl">
            <thead><tr>
              <SortHeader label="CVE-ID" sortKey="cve_id" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 160 }} />
              <SortHeader label="Severity" sortKey="severity" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 90 }} />
              <SortHeader label="CVSS" sortKey="cvss_v3_score" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 70 }} />
              <th>Description / Product</th>
              <SortHeader label="Modified" sortKey="last_modified_at" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
              <SortHeader label="Published" sortKey="published_at" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
              <th style={{ width: 40 }}></th>
            </tr></thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>Loading CVEs...</td></tr>
              )}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>No CVEs found.</td></tr>
              )}
              {items.map((c) => {
                const sev = sevClass(c.severity);
                return (
                  <tr key={c.cve_id} style={{ cursor: 'pointer' }} onClick={() => router.push(`/intelligence/cves/${c.cve_id}`)}>
                    <td className="mono primary" style={{ fontSize: 11.5 }}>{c.cve_id}</td>
                    <td><span className={`badge ${sev.tag}`}>{c.severity ?? 'unknown'}</span></td>
                    <td className="mono" style={{ color: sev.color, fontWeight: 600 }}>{c.cvss_v3_score?.toFixed(1) ?? '—'}</td>
                    <td>
                      <div style={{ maxWidth: 580, wordBreak: 'break-word', color: 'var(--text-2)' }}>
                        {productLabel(c)}
                      </div>
                    </td>
                    <td className="mono" style={{ fontSize: 11 }}>{fmtDate(c.last_modified_at)}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{fmtDate(c.published_at)}</td>
                    <td><More s={14} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <Pagination total={total} page={page} pageSize={PAGE_SIZE} onChange={setPage} />
      </div>
    </div>
  );
}
