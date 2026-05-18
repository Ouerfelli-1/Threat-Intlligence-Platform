'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Search, Users, FileText, AlertTriangle, Crosshair,
  Send, Sparkles, ChevronRight,
} from '@/components/icons';

/* ── result data (static mockup — wire to live search later) ──────────── */

interface CmdResult {
  icon: React.FC<{ s?: number }>;
  primary: string;
  sub: string;
  hint: string;
}

interface CmdGroupData {
  title: string;
  icon: React.FC<{ s?: number }>;
  items: CmdResult[];
}

const GROUPS: CmdGroupData[] = [
  {
    title: 'Actors', icon: Users, items: [
      { icon: Users, primary: 'TA505 (Cl0p)',            sub: 'G0092 · RU · ransomware · monitored', hint: 'actor' },
      { icon: Users, primary: 'Cl0p ransomware group',   sub: 'G0092 alias · 218 victims YTD',                  hint: 'actor' },
    ],
  },
  {
    title: 'Articles', icon: FileText, items: [
      { icon: FileText,      primary: 'Cl0p shifts to MOVEit‑style zero‑day pipeline; MEA banking targets', sub: 'BleepingComputer · 14 May 06:12', hint: 'article #1247' },
      { icon: FileText,      primary: 'TA505 returns with FlawedAmmyy successor',                                     sub: 'Group‑IB · 12 May',          hint: 'article #1239' },
      { icon: FileText,      primary: 'LockBit 4.0 affiliate reboot — Cl0p comparison',                          sub: 'TrendMicro · 12 May',             hint: 'article #1232' },
    ],
  },
  {
    title: 'Threats', icon: AlertTriangle, items: [
      { icon: AlertTriangle, primary: 'Cl0p data‑theft campaign vs MEA banks', sub: 'data_breach · active · 14 May', hint: 'threat-118' },
    ],
  },
  {
    title: 'IOCs', icon: Crosshair, items: [
      { icon: Crosshair, primary: 'svc-update.net',        sub: 'domain · 0.94 · cl0p · c2',   hint: 'ioc-92841' },
      { icon: Crosshair, primary: '193.142.30.211',         sub: 'ipv4 · 0.96 · cl0p · c2',     hint: 'ioc-92842' },
      { icon: Crosshair, primary: '7d9af31a8b…0a31f',  sub: 'sha256 · cl0p · loader',            hint: 'ioc-92843' },
    ],
  },
  {
    title: 'Actions', icon: Sparkles, items: [
      { icon: Send,     primary: 'Push Cl0p IOC bundle to Wazuh',    sub: '14 IOCs · active-response',            hint: 'action' },
      { icon: Sparkles, primary: 'Generate ad-hoc brief on Cl0p',    sub: 'orchestrator · analysis_cycle',         hint: 'action' },
      { icon: Search,   primary: 'Search Wazuh for “cl0p”', sub: 'last 30d · all agents',               hint: 'action' },
    ],
  },
];

/* ── component ────────────────────────────────────────────────────────── */

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  /* Cmd+K / Ctrl+K listener */
  const handleKey = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      setOpen(prev => !prev);
    }
    if (e.key === 'Escape') setOpen(false);
  }, []);

  useEffect(() => {
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  useEffect(() => {
    if (open) {
      setQuery('cl0p');
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.select(), 50);
    }
  }, [open]);

  if (!open) return null;

  /* flatten for keyboard navigation */
  const flatItems = GROUPS.flatMap(g => g.items);
  const totalResults = flatItems.length;

  return (
    <>
      {/* backdrop */}
      <div
        onClick={() => setOpen(false)}
        style={{ position: 'fixed', inset: 0, background: 'rgba(1,4,9,0.55)', backdropFilter: 'blur(4px)', zIndex: 900 }}
      />

      {/* palette */}
      <div style={{
        position: 'fixed', top: 70, left: '50%', transform: 'translateX(-50%)',
        width: 720, maxHeight: 540,
        background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12,
        boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(88,166,255,0.18)',
        overflow: 'hidden', display: 'flex', flexDirection: 'column', zIndex: 910,
      }}>
        {/* search input row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
          <Search s={16} />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx(i => Math.min(i + 1, totalResults - 1)); }
              if (e.key === 'ArrowUp')   { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, 0)); }
            }}
            style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 15, flex: 1, fontFamily: 'var(--sans)' }}
            placeholder="Search across all entities..."
          />
          <span className="badge mute">esc to close</span>
        </div>

        {/* entity filter tabs */}
        <div style={{ display: 'flex', gap: 6, padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
          {['Everything', 'Articles', 'CVEs', 'IOCs', 'Actors', 'Assets', 'Reports'].map((t, i) => (
            <span
              key={t}
              className="badge"
              style={{
                background: i === 0 ? 'var(--accent-bg)' : 'var(--bg-elev)',
                color: i === 0 ? 'var(--accent)' : 'var(--text-3)',
                borderColor: i === 0 ? 'rgba(88,166,255,0.3)' : 'var(--border)',
                cursor: 'pointer',
              }}
            >{t}</span>
          ))}
          <span style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--text-4)' }}>&uarr;&darr; navigate &middot; &#x21B5; select &middot; &#x2318;+&#x21B5; open new</span>
        </div>

        {/* results */}
        <div style={{ overflow: 'auto', flex: 1, padding: 6 }}>
          {(() => {
            let globalIdx = 0;
            return GROUPS.map((g) => (
              <div key={g.title} style={{ marginBottom: 4 }}>
                {/* group header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px 4px', fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  <g.icon s={11} />{g.title}
                </div>
                {/* group rows */}
                {g.items.map((item) => {
                  const idx = globalIdx++;
                  const isActive = idx === activeIdx;
                  return (
                    <div
                      key={idx}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '7px 12px', borderRadius: 6,
                        background: isActive ? 'rgba(88,166,255,0.12)' : 'transparent',
                        borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                        cursor: 'pointer',
                      }}
                    >
                      <item.icon s={14} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 12.5, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.primary}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-4)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.sub}</div>
                      </div>
                      <span className="tag">{item.hint}</span>
                      {isActive && <ChevronRight s={12} />}
                    </div>
                  );
                })}
              </div>
            ));
          })()}
        </div>

        {/* footer */}
        <div style={{ borderTop: '1px solid var(--border)', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--text-4)' }}>
          <span>{totalResults} results across 5 entity types</span>
          <span style={{ marginLeft: 'auto' }}>indexed 2 min ago</span>
        </div>
      </div>
    </>
  );
}
