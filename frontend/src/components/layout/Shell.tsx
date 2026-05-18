'use client';

import React from 'react';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import CommandPalette from './CommandPalette';
import { useStore } from '@/lib/store';

interface ShellProps {
  crumbs?: string[];
  hint?: string;
  children: React.ReactNode;
}

export default function Shell({ crumbs, hint, children }: ShellProps) {
  const collapsed = useStore((s) => s.sidebarCollapsed);

  return (
    <div className={`tip shell ${collapsed ? 'collapsed' : ''}`}>
      <Sidebar />
      <Topbar crumbs={crumbs} hint={hint} />
      <div className="main">{children}</div>
      <CommandPalette />
    </div>
  );
}
