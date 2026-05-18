'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Feeds management was folded into the unified Settings page. Keep this as a
// permanent redirect so any deep links / bookmarks land on the right tab.
export default function AdminFeedsRedirectPage() {
  const router = useRouter();
  useEffect(() => { router.replace('/settings'); }, [router]);
  return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-4)', fontSize: 13 }}>
      Feeds management is now under Settings &rarr; RSS Feeds — redirecting…
    </div>
  );
}
