'use client';

import React from 'react';
import { Plus, ChevronRight, Settings, More, Refresh } from '@/components/icons';
import { useRoles } from '@/lib/hooks';

export default function RolesPage() {
  const { items, total, isLoading, mutate } = useRoles();

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Roles</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total} roles · RBAC backed by auth/v2`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          {/* RBAC editing is read-only in the UI for now — roles are seeded by
              auth at startup and managed via the admin CLI / direct API. The
              button stays visible so admins know the page is read-only, not
              broken. */}
          <button className="btn primary" disabled title="Role editing is read-only in the UI. Roles are seeded by the auth service; edit via the admin API.">
            <Plus s={12} />New role
          </button>
        </div>
      </div>

      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        {isLoading && <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>Loading roles...</div>}
        {!isLoading && items.length === 0 && <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>No roles defined.</div>}
        {items.map((r, i) => (
          <div key={r.id} style={{ borderBottom: i < items.length - 1 ? '1px solid var(--border-soft)' : 'none', padding: '14px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <ChevronRight s={12} />
              <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text)' }}>{r.name}</div>
              {r.user_count !== undefined && <span className="tag">{r.user_count} user{r.user_count === 1 ? '' : 's'}</span>}
              <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                <button className="btn sm" disabled title="Read-only in UI — edit via the admin API"><Settings s={11} />Edit</button>
                <button className="btn sm" disabled title="No row-level actions yet"><More s={11} /></button>
              </span>
            </div>
            <div style={{ marginLeft: 22, marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {r.permissions.map(p => (
                <span
                  key={p}
                  className="tag"
                  style={{ color: p === '*' || p.endsWith(':*') ? 'var(--crit)' : 'var(--text-2)' }}
                >{p}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
