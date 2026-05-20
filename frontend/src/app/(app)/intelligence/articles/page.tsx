'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import FilterBar from '@/components/shared/FilterBar';
import Pagination from '@/components/shared/Pagination';
import Bar from '@/components/shared/Bar';
import SortHeader from '@/components/shared/SortHeader';
import { Refresh, Download, Filter, More } from '@/components/icons';
import { useArticles } from '@/lib/hooks';
import { useServerSort } from '@/lib/serverSort';

function stBadge(s: string) {
  if (s === 'reviewed' || s === 'relevant')   return <span className="badge low">{s}</span>;
  if (s === 'unreviewed')                     return <span className="badge med">new</span>;
  if (s === 'escalated')                      return <span className="badge high">escalated</span>;
  if (s === 'not_relevant')                   return <span className="badge mute">not&#x2011;rel</span>;
  return <span className="badge mute">{s}</span>;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

const PAGE_SIZE = 50;

export default function ArticleListPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [showNotRel, setShowNotRel] = useState(false);

  // Default sort: most recently fetched first. Click any column header to change.
  const { sortBy, sortDir, toggle, sortParams } = useServerSort('fetched_at', 'desc');

  const { items, total, isLoading, mutate } = useArticles({
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
    q: q || undefined,
    include_not_relevant: showNotRel || undefined,
    ...sortParams,
  });

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Articles</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total} ingested · page ${page} of ${Math.max(1, Math.ceil(total / PAGE_SIZE))}`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn"><Download s={12} />Export CSV</button>
        </div>
      </div>

      <FilterBar
        search="Search title, summary, tags..."
        value={q}
        onSearch={(v) => { setQ(v); setPage(1); }}
        extra={
          <>
            <button className="btn"><Filter s={12} />More filters</button>
            <label style={{ fontSize: 11.5, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <input
                type="checkbox"
                checked={showNotRel}
                onChange={(e) => setShowNotRel(e.target.checked)}
                style={{ accentColor: '#2dd4bf' }}
              />Show not&#x2011;relevant
            </label>
          </>
        }
      >
        <select className="select"><option>All sources</option></select>
        <select className="select"><option>All tags</option></select>
        <select className="select"><option>Last 7 days</option></select>
      </FilterBar>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <SortHeader label="Status" sortKey="analyst_status" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
                <SortHeader label="Title" sortKey="title" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} />
                <SortHeader label="Source" sortKey="source_name" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 160 }} />
                <SortHeader label="Fetched" sortKey="fetched_at" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 140 }} />
                <SortHeader label="Published" sortKey="published_at" currentKey={sortBy} currentDir={sortDir} onToggle={toggle} style={{ width: 140 }} />
                <th style={{ width: 240 }}>Tags</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>Loading articles...</td></tr>
              )}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>
                  No articles found. Trigger an ingest from the scheduler.
                </td></tr>
              )}
              {items.map((a) => {
                return (
                  <tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => router.push(`/intelligence/articles/${a.id}`)}>
                    <td>{stBadge(a.analyst_status)}</td>
                    <td className="primary">
                      <div style={{ maxWidth: 560, wordBreak: 'break-word' }}>{a.title}</div>
                    </td>
                    <td>{a.source_name}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{fmtDate(a.fetched_at)}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{fmtDate(a.published_at)}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {a.tags.slice(0, 3).map(t => <span key={t} className="tag">{t}</span>)}
                        {a.tags.length > 3 && <span className="tag">+{a.tags.length - 3}</span>}
                      </div>
                    </td>
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
