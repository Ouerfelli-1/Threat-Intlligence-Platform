'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Shell from '@/components/layout/Shell';
import { useStore } from '@/lib/store';
import { api } from '@/lib/api';

// Backend /me responds DB-truth. When it returns 401 the session was revoked
// (admin demoted us, or our row was deactivated) — api.ts handles that path
// by clearing local auth and redirecting to /login. We just need to call /me
// often enough that the user notices.
const ME_POLL_MS = 15_000;  // 15s — fast enough for "demote -> logout" UX,
                            // slow enough to be negligible load.

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const token = useStore((s) => s.token);
  const setAuth = useStore((s) => s.setAuth);
  // Zustand+persist hydrates from localStorage on the client only.
  // Use a `mounted` flag to avoid SSR/CSR token mismatch and avoid
  // redirecting before hydration completes.
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && !token) {
      router.replace('/login');
    }
  }, [mounted, token, router]);

  // Keep a stable ref to the latest token so the polling effect's interval
  // doesn't have to re-subscribe whenever token changes mid-session.
  const tokenRef = useRef(token);
  useEffect(() => { tokenRef.current = token; }, [token]);

  // /me poller — three triggers:
  //   1. Initial mount (immediate check).
  //   2. setInterval every ME_POLL_MS — catches background demotions.
  //   3. Window 'focus' + 'visibilitychange' — catches "user switched tab,
  //      came back to a stale page" without making them wait 15s.
  //   4. Route change (pathname dep) — catches navigation within the SPA.
  // If /me returns 401, api.ts clears auth + redirects. Other errors are
  // logged and ignored so a transient network blip doesn't kick the user.
  useEffect(() => {
    if (!mounted) return;
    if (!tokenRef.current) return;

    let cancelled = false;

    const checkMe = async () => {
      if (!tokenRef.current || cancelled) return;
      try {
        const me = await api.get<{ id: string; username: string; role: string; permissions: string[] }>('/me');
        if (!cancelled) setAuth(tokenRef.current, me);
      } catch {
        // 401 path handled in api.ts; other failures are non-fatal.
      }
    };

    // Fire immediately on this effect run (mount + route change).
    checkMe();

    // Periodic background poll.
    const interval = setInterval(checkMe, ME_POLL_MS);

    // Refocus / tab-visibility check — common case: admin demotes a user
    // while their tab was in the background. The moment they look at it,
    // they get kicked.
    const onFocus = () => checkMe();
    const onVisibility = () => { if (document.visibilityState === 'visible') checkMe(); };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibility);
    };
    // pathname is in deps so SPA navigations also trigger an immediate check
  }, [mounted, pathname, setAuth]);

  if (!mounted) {
    return (
      <div style={{ position: 'fixed', inset: 0, display: 'grid', placeItems: 'center', background: 'var(--bg-page)', color: 'var(--text-3)', fontSize: 12 }}>
        Loading…
      </div>
    );
  }

  if (!token) {
    return null; // redirect in flight
  }

  return <Shell>{children}</Shell>;
}
