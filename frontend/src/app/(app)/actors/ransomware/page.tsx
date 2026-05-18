'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Ransomware was moved under Intelligence. Keep this path as a permanent
// redirect so existing bookmarks / sidebar deep links land on the new home.
export default function RansomwareRedirectPage() {
  const router = useRouter();
  useEffect(() => { router.replace('/intelligence/ransomware'); }, [router]);
  return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-4)', fontSize: 13 }}>
      Ransomware moved to Intelligence — redirecting…
    </div>
  );
}
