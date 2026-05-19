'use client';

import React from 'react';
import Link from 'next/link';
import { Lock, ChevronLeft } from '@/components/icons';
import { useIsAdmin, useStore } from '@/lib/store';

/**
 * Admin route gate.
 *
 * Every page under /admin/* requires the "*" wildcard permission (held only
 * by the admin role). Non-admin users land here and see an explicit
 * "Not authorized" panel instead of a half-rendered page that 403s its
 * underlying API calls and leaves the screen empty.
 *
 * The backend remains the source of truth — every /users, /roles, /sessions
 * endpoint enforces require_admin server-side. This layout is for UX, not
 * security: it removes the misleading impression that a viewer has admin
 * access just because the URL renders chrome.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
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
            Your account ({user?.username ?? 'unknown'}, role <span className="mono">{user?.role ?? 'unknown'}</span>)
            doesn&apos;t have the permissions needed to view this page. Ask an administrator
            to grant the admin role or the required scoped permissions.
          </div>
        </div>
        <Link href="/" className="btn"><ChevronLeft s={12} /> Back to dashboard</Link>
      </div>
    );
  }

  return <>{children}</>;
}
