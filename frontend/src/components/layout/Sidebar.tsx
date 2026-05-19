'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { I, Settings } from '@/components/icons';
import { useIsAdmin } from '@/lib/store';

interface SidebarItem {
  id: string;
  label: string;
  icon: string;
  href: string;
  num?: string;
  pill?: string;
}

interface SidebarSection {
  title?: string;
  items: SidebarItem[];
  /** If true, only show this section to admin users (those with "*" perm).
   *  Backend already 403s the underlying endpoints — this prevents the nav
   *  links from misleading a viewer into thinking they have admin access. */
  adminOnly?: boolean;
}

// Hardcoded count badges (articles=241, cves=47, etc) were stripped — they
// were never wired to live data and gave a false sense of "fresh". If we want
// real counts here later, fetch them from /api/dashboard.
// Ransomware moved out of the Actors section into Intelligence per spec.
const sections: SidebarSection[] = [
  {
    items: [{ id: 'home', label: 'Home', icon: 'Home', href: '/' }],
  },
  {
    title: 'Intelligence',
    items: [
      { id: 'articles', label: 'Articles', icon: 'FileText', href: '/intelligence/articles' },
      { id: 'cves', label: 'CVEs', icon: 'Bug', href: '/intelligence/cves' },
      { id: 'threats', label: 'Threats', icon: 'AlertTriangle', href: '/intelligence/threats' },
      { id: 'supply-chain', label: 'Supply Chain', icon: 'Package', href: '/intelligence/supply-chain' },
      { id: 'ransom', label: 'Ransomware', icon: 'Skull', href: '/intelligence/ransomware' },
    ],
  },
  {
    title: 'IOCs',
    items: [
      { id: 'iocs', label: 'IOC Library', icon: 'Crosshair', href: '/iocs' },
      { id: 'investigate', label: 'Investigate', icon: 'Scope', href: '/iocs/investigate' },
    ],
  },
  {
    title: 'Actors',
    items: [
      { id: 'actors', label: 'Actor List', icon: 'Users', href: '/actors' },
    ],
  },
  {
    title: 'Integrations',
    items: [
      { id: 'wazuh', label: 'Wazuh', icon: 'Shield', href: '/integrations/wazuh' },
      { id: 'misp', label: 'MISP', icon: 'Plug', href: '/integrations/misp' },
    ],
  },
  {
    title: 'Surface',
    items: [
      { id: 'assets', label: 'Assets', icon: 'Server', href: '/assets' },
      { id: 'profile', label: 'Company Profile', icon: 'Building', href: '/assets/profile' },
      { id: 'asm', label: 'ASM Scopes', icon: 'Radar', href: '/surface/scopes' },
      { id: 'domains', label: 'Domain Watch', icon: 'Globe', href: '/surface/domains' },
    ],
  },
  {
    title: 'Operations',
    items: [
      { id: 'scheduler', label: 'Scheduler', icon: 'Clock', href: '/operations/scheduler' },
      { id: 'policies', label: 'AI Policies', icon: 'GitBranch', href: '/operations/policies' },
      { id: 'reports', label: 'Reports', icon: 'FileText', href: '/operations/reports' },
      { id: 'flowviz', label: 'Attack Flow', icon: 'Activity', href: '/flowviz' },
    ],
  },
  {
    items: [{ id: 'ask', label: 'Ask AI', icon: 'Sparkles', href: '/ask' }],
  },
  {
    title: 'Admin',
    adminOnly: true,
    items: [
      { id: 'users', label: 'Users & Roles', icon: 'Users', href: '/admin/users' },
      { id: 'sessions', label: 'Sessions', icon: 'Lock', href: '/admin/sessions' },
    ],
  },
];

function resolveActive(pathname: string): string {
  // Check longest-match first
  for (const sec of sections) {
    for (const it of sec.items) {
      if (it.href === pathname) return it.id;
    }
  }
  // Prefix match
  for (const sec of sections) {
    for (const it of sec.items) {
      if (it.href !== '/' && pathname.startsWith(it.href)) return it.id;
    }
  }
  if (pathname === '/') return 'home';
  return '';
}

export default function Sidebar() {
  const pathname = usePathname();
  const active = resolveActive(pathname);
  const isAdminUser = useIsAdmin();

  // Hide admin-only sections from non-admin users. The backend already 403s
  // /users, /sessions, /roles for them — but the navigation links would
  // otherwise dangle and make a viewer think they have admin access.
  const visibleSections = sections.filter((s) => !s.adminOnly || isAdminUser);

  return (
    <div className="sb">
      <div className="sb-inner">
        {/* Logo removed; product title is the only branding now. */}
        <div className="sb-brand">
          <div className="wordmark" style={{ letterSpacing: '0.04em', fontSize: 12, lineHeight: 1.25 }}>
            Cyber Threat<br />Intelligence Platform
          </div>
        </div>
        {visibleSections.map((sec, i) => (
          <React.Fragment key={i}>
            {sec.title && <div className="sb-section">{sec.title}</div>}
            {sec.items.map((it) => {
              const IconCmp = I[it.icon] || I.Home;
              return (
                <Link
                  key={it.id}
                  href={it.href}
                  className={`sb-item ${active === it.id ? 'active' : ''}`}
                >
                  <span className="ico"><IconCmp s={14} /></span>
                  <span>{it.label}</span>
                  {it.num && <span className="num">{it.num}</span>}
                  {it.pill && <span className="pill">{it.pill}</span>}
                </Link>
              );
            })}
          </React.Fragment>
        ))}
        {/* Settings exposes secrets management + provider keys — admin-only on
            the backend, so the footer link is also gated to avoid dangling. */}
        {isAdminUser && (
          <div className="sb-foot">
            <Link href="/settings" className="sb-item">
              <span className="ico"><Settings s={14} /></span>
              <span>Settings</span>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
