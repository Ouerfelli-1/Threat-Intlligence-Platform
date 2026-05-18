'use client';

import React, { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Refresh, X } from '@/components/icons';
import { useSessions } from '@/lib/hooks';
import { api } from '@/lib/api';
import { useStore } from '@/lib/store';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function howLongAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60)    return `${s}s ago`;
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function SessionsPage() {
  const router = useRouter();
  const clearAuth = useStore((s) => s.clearAuth);
  const { items, total, isLoading, mutate } = useSessions();
  const [revoking, setRevoking]       = useState<string | null>(null);
  const [bulkRevoking, setBulkRevoking] = useState(false);

  const revoke = useCallback(async (id: string) => {
    if (!confirm('Revoke this session? The user will be forced to log in again.')) return;
    setRevoking(id);
    try {
      await api.delete(`/sessions/${id}`);
      mutate();
    } catch (e) { alert(String(e)); }
    finally { setRevoking(null); }
  }, [mutate]);

  const revokeAll = useCallback(async () => {
    if (!confirm(`Revoke ALL ${total} active sessions? Every user (including you) will be forced to log in again.`)) return;
    setBulkRevoking(true);
    try {
      await api.post('/sessions/revoke-all');
      // The backend marks every session row as revoked but our JWT is
      // stateless — we wouldn't notice until it expires. Force-clear the
      // local auth + bounce to /login so the admin who initiated this is
      // actually logged out (matches the dialog's promise).
      clearAuth();
      router.push('/login');
    } catch (e) {
      alert(String(e));
      setBulkRevoking(false);
    }
  }, [mutate, total, clearAuth, router]);

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Active sessions</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total} active · JWT exp 1h · refresh sliding`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn danger" onClick={revokeAll} disabled={bulkRevoking || total === 0}>
            {bulkRevoking ? <Refresh s={12} style={{ animation: 'spin 1s linear infinite' }} /> : <X s={12} />}
            {bulkRevoking ? 'Revoking…' : 'Revoke all'}
          </button>
        </div>
      </div>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
        <table className="tbl">
          <thead><tr>
            <th style={{ width: 200 }}>User</th>
            <th style={{ width: 150 }}>IP</th>
            <th>Agent</th>
            <th style={{ width: 160 }}>Started</th>
            <th style={{ width: 160 }}>Expires</th>
            <th style={{ width: 110 }}>Action</th>
          </tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} style={{ textAlign: 'center', padding: 30, color: 'var(--text-4)' }}>Loading sessions...</td></tr>}
            {!isLoading && items.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', padding: 30, color: 'var(--text-4)' }}>No active sessions.</td></tr>}
            {items.map((s) => (
              <tr key={s.id}>
                <td className="primary mono" style={{ fontSize: 11.5 }}>{s.username ?? s.user_id}</td>
                <td className="mono" style={{ fontSize: 11 }}>{s.ip ?? '—'}</td>
                <td className="mono" style={{ fontSize: 11, maxWidth: 380, wordBreak: 'break-word' }}>{s.user_agent ?? '—'}</td>
                <td className="mono" style={{ fontSize: 11 }}>{fmtDate(s.issued_at)} <span style={{ color: 'var(--text-4)' }}>({howLongAgo(s.issued_at)})</span></td>
                <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>{fmtDate(s.expires_at)}</td>
                <td>
                  {s.revoked
                    ? <span className="badge mute">revoked</span>
                    : (
                      <button className="btn danger sm" onClick={() => revoke(s.id)} disabled={revoking === s.id}>
                        {revoking === s.id ? <Refresh s={10} style={{ animation: 'spin 1s linear infinite' }} /> : <X s={11} />}
                        {revoking === s.id ? 'Revoking…' : 'Revoke'}
                      </button>
                    )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}
