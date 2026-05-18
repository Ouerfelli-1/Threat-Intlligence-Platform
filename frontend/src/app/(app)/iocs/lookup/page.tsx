'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// The single-/bulk-lookup UI was merged into /iocs (see "Bulk lookup" button).
// Keep this page as a permanent redirect for any deep links / bookmarks.
export default function IocLookupRedirectPage() {
  const router = useRouter();
  useEffect(() => { router.replace('/iocs'); }, [router]);
  return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-4)', fontSize: 13 }}>
      Lookup is now part of the IOC Library — redirecting…
    </div>
  );
}
