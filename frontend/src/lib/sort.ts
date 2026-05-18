'use client';

import { useState, useMemo } from 'react';

export type SortDir = 'asc' | 'desc';

export interface SortState {
  key: string;
  dir: SortDir;
}

/**
 * Generic client-side sort hook.
 * Returns sorted items + toggle function for column headers.
 */
export function useSortable<T>(
  items: T[],
  defaultKey: string,
  defaultDir: SortDir = 'desc',
) {
  const [sortKey, setSortKey] = useState(defaultKey);
  const [sortDir, setSortDir] = useState<SortDir>(defaultDir);

  const sorted = useMemo(() => {
    if (!sortKey || items.length === 0) return items;
    const copy = [...items];
    copy.sort((a, b) => {
      const av = getNestedValue(a, sortKey);
      const bv = getNestedValue(b, sortKey);
      const cmp = compare(av, bv);
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [items, sortKey, sortDir]);

  function toggle(key: string) {
    if (key === sortKey) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  return { sorted, sortKey, sortDir, toggle };
}

function getNestedValue(obj: unknown, key: string): unknown {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const o = obj as any;
  if (o == null) return null;
  return o[key] ?? null;
}

function compare(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0;
  if (a == null) return -1;
  if (b == null) return 1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'string' && typeof b === 'string') return a.localeCompare(b, undefined, { sensitivity: 'base' });
  return String(a).localeCompare(String(b));
}
