'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Shell from '@/components/layout/Shell';
import { useStore } from '@/lib/store';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useStore((s) => s.token);
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
