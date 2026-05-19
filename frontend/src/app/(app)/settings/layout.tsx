'use client';

import React from 'react';
import Link from 'next/link';
import { Lock, ChevronLeft } from '@/components/icons';
import { useIsAdmin, useStore } from '@/lib/store';

/**
 * Settings route gate. Same logic as the /admin layout — Settings exposes
 * secrets, provider keys and feed config which are all backed by
 * admin-only endpoints, so non-admin users should see a clear refusal
 * instead of a broken page that 403s every fetch.
 */
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const isAdmin = useIsAdmin();
  const user = useStore((s) => s.user);

  if (!isAdmin) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', height: '100%', padding: 40, textAlign: 'center', gap: 16,
      }}>
        <div style={{ width: 56, height: 56, borderRadius: 28, background: 'rgba(248,81,73,0.1)', display: 'grid', placeItems: 'center', color: '#f85149' }}>
          <Lock s={26} />
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
            Admin access required
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--text-3)', maxWidth: 420, lineHeight: 1.55 }}>
            Settings (secrets, AI provider keys, feeds, tag catalog) is restricted
            to administrators. Your account ({user?.username ?? 'unknown'},
            role <span className="mono">{user?.role ?? 'unknown'}</span>) doesn&apos;t hold
            the admin permission.
          </div>
        </div>
        <Link href="/" className="btn"><ChevronLeft s={12} /> Back to dashboard</Link>
      </div>
    );
  }

  return <>{children}</>;
}
