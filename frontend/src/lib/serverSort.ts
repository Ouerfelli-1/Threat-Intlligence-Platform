'use client';

import { useCallback, useState } from 'react';

/**
 * Server-side sort state for paginated list endpoints.
 *
 * Returns `{sortBy, sortDir, toggle, sortParams}`. Pass `sortParams` into the
 * data-fetch hook so the backend can `ORDER BY` the full result set instead of
 * client-side-sorting only the visible page.
 *
 * Click handler: clicking the active column flips direction; clicking a new
 * column switches to it with the default direction (desc — most recent first).
 *
 * Usage:
 *   const { sortBy, sortDir, toggle, sortParams } = useServerSort('fetched_at');
 *   const { items, total } = useArticles({ ...sortParams, ... });
 *   ...
 *   <SortHeader label="Fetched" sortKey="fetched_at"
 *               currentKey={sortBy} currentDir={sortDir} onToggle={toggle} />
 */
export function useServerSort(defaultKey: string, defaultDir: 'asc' | 'desc' = 'desc') {
  const [sortBy, setSortBy] = useState(defaultKey);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(defaultDir);

  const toggle = useCallback((key: string) => {
    if (key === sortBy) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir(defaultDir);
    }
  }, [sortBy, defaultDir]);

  return {
    sortBy,
    sortDir,
    toggle,
    sortParams: { sort_by: sortBy, sort_dir: sortDir },
  };
}
