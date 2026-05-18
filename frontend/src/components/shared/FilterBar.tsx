'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Search } from '@/components/icons';

interface FilterBarProps {
  search?: string;
  value?: string;
  onSearch?: (v: string) => void;
  children?: React.ReactNode;
  extra?: React.ReactNode;
}

export default function FilterBar({
  children, search = 'Search...', extra, value = '', onSearch,
}: FilterBarProps) {
  const [v, setV] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => setV(value), [value]);

  function handle(input: string) {
    setV(input);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onSearch?.(input), 250);
  }

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: 10, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 220, maxWidth: 360 }}>
          <input
            className="input"
            placeholder={search}
            value={v}
            onChange={(e) => handle(e.target.value)}
            style={{ paddingLeft: 28 }}
          />
          <span style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-4)' }}>
            <Search s={13} />
          </span>
        </div>
        {children}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>{extra}</div>
      </div>
    </div>
  );
}
