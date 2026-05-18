'use client';

import React from 'react';
import { ChevronLeft, ChevronRight } from '@/components/icons';

interface PaginationProps {
  total: number;
  page?: number;
  pageSize?: number;
  onChange?: (page: number) => void;
}

export default function Pagination({ total, page = 1, pageSize = 25, onChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  // Generate up to 5 page buttons centered around current page
  const windowSize = 5;
  const half = Math.floor(windowSize / 2);
  let start = Math.max(1, page - half);
  let end = Math.min(totalPages, start + windowSize - 1);
  if (end - start + 1 < windowSize) start = Math.max(1, end - windowSize + 1);
  const pages = Array.from({ length: end - start + 1 }, (_, i) => start + i);

  function go(p: number) {
    if (p < 1 || p > totalPages || p === page) return;
    onChange?.(p);
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', fontSize: 11.5, color: 'var(--text-3)', borderTop: '1px solid var(--border)' }}>
      <span>
        {total === 0 ? 0 : (page - 1) * pageSize + 1}&ndash;{Math.min(page * pageSize, total)} of {total.toLocaleString()}
      </span>
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
        <button className="btn sm" disabled={page <= 1} onClick={() => go(page - 1)}><ChevronLeft s={11} /></button>
        {pages.map((p) => (
          <button
            key={p}
            className="btn sm"
            onClick={() => go(p)}
            style={p === page ? { background: 'var(--accent-bg)', color: 'var(--accent)' } : {}}
          >
            {p}
          </button>
        ))}
        <button className="btn sm" disabled={page >= totalPages} onClick={() => go(page + 1)}><ChevronRight s={11} /></button>
      </div>
    </div>
  );
}
