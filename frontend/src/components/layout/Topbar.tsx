'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Bell, Sparkles, Search, ChevronDown, X, Clock,
  AlertTriangle, Settings, Lock, Users,
} from '@/components/icons';
import { useStore } from '@/lib/store';
import { useRuns, RunInfo } from '@/lib/hooks';
import { api } from '@/lib/api';

interface TopbarProps {
  crumbs?: string[];
  hint?: string;
}

/* ── Command palette search result ──────────────────────────── */

interface SearchResult {
  type: 'article' | 'cve' | 'ioc' | 'actor' | 'threat';
  id: string;
  label: string;
  sub?: string;
  href: string;
}

const TYPE_LABEL: Record<string, { label: string; color: string }> = {
  article: { label: 'Article', color: 'var(--accent)' },
  cve:     { label: 'CVE',     color: '#f85149' },
  ioc:     { label: 'IOC',     color: '#d29922' },
  actor:   { label: 'Actor',   color: '#a371f7' },
  threat:  { label: 'Threat',  color: '#f0883e' },
};

/* ── Topbar ─────────────────────────────────────────────────── */

export default function Topbar({
  crumbs = [],
  hint = 'Search articles, CVEs, IOCs, actors…',
}: TopbarProps) {
  const router = useRouter();
  const user = useStore((s) => s.user);
  const clearAuth = useStore((s) => s.clearAuth);

  const initials = user?.username
    ? user.username.split('.').map(p => p[0]?.toUpperCase()).join('').slice(0, 2)
    : 'YA';
  const displayName = user?.username
    ? user.username.split('.').map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' ')
    : 'Yassine A.';
  const role = user?.role || 'SOC Analyst';

  /* ── State ─────────────────────── */
  const [showPalette, setShowPalette] = useState(false);
  const [showNotifs, setShowNotifs]   = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState('');
  const [results, setResults]     = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);

  const paletteRef = useRef<HTMLDivElement>(null);
  const notifRef   = useRef<HTMLDivElement>(null);
  const userRef    = useRef<HTMLDivElement>(null);
  const inputRef   = useRef<HTMLInputElement>(null);

  /* ── Notifications data ────────── */
  const { items: recentRuns } = useRuns({ limit: 20 });
  const failedRuns = recentRuns.filter((r: RunInfo) =>
    r.status === 'failed' || r.status === 'timeout'
  ).slice(0, 8);

  /* ── Keyboard shortcut (Cmd+K / Ctrl+K) ── */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowPalette(v => !v);
        setShowNotifs(false);
        setShowUserMenu(false);
      }
      if (e.key === 'Escape') {
        setShowPalette(false);
        setShowNotifs(false);
        setShowUserMenu(false);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  /* ── Focus input when palette opens ── */
  useEffect(() => {
    if (showPalette) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setPaletteQuery('');
      setResults([]);
      setSelectedIdx(0);
    }
  }, [showPalette]);

  /* ── Click-outside handlers ── */
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotifs(false);
      if (userRef.current && !userRef.current.contains(e.target as Node)) setShowUserMenu(false);
      if (paletteRef.current && !paletteRef.current.contains(e.target as Node)) setShowPalette(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  /* ── Debounced search ── */
  useEffect(() => {
    if (!paletteQuery.trim()) { setResults([]); return; }
    const timer = setTimeout(async () => {
      setSearching(true);
      setSelectedIdx(0);
      const q = paletteQuery.trim();
      const out: SearchResult[] = [];

      /* eslint-disable @typescript-eslint/no-explicit-any */
      // Fire 5 parallel searches
      const [articles, cves, iocs, actors, threats] = await Promise.allSettled([
        api.get<any>('/articles', { q, limit: 5 }),
        api.get<any>('/cves', { q, limit: 5 }),
        api.get<any>('/indicators', { value: q, limit: 5 }),
        api.get<any>('/actors', { name: q, limit: 5 }),
        api.get<any>('/threats', { q, limit: 5 }),
      ]);

      const toArr = (res: PromiseSettledResult<any>): any[] => {
        if (res.status !== 'fulfilled') return [];
        const v = res.value;
        return Array.isArray(v) ? v : v?.items ?? [];
      };

      // Parse articles
      for (const a of toArr(articles).slice(0, 3)) {
        out.push({ type: 'article', id: a.id, label: a.title ?? a.id, sub: a.source_name ?? '', href: `/intelligence/articles/${a.id}` });
      }
      // Parse CVEs
      for (const c of toArr(cves).slice(0, 3)) {
        const cid = c.cve_id ?? c.id;
        out.push({ type: 'cve', id: cid, label: cid, sub: (c.description ?? '').slice(0, 80), href: `/intelligence/cves/${cid}` });
      }
      // Parse IOCs
      for (const ioc of toArr(iocs).slice(0, 3)) {
        out.push({ type: 'ioc', id: ioc.id, label: ioc.normalized_value ?? ioc.id, sub: ioc.type ?? '', href: `/iocs/${ioc.id}` });
      }
      // Parse actors
      for (const a of toArr(actors).slice(0, 3)) {
        out.push({ type: 'actor', id: a.id, label: a.name ?? a.id, sub: a.mitre_id ?? '', href: `/actors/${a.id}` });
      }
      // Parse threats
      for (const t of toArr(threats).slice(0, 3)) {
        out.push({ type: 'threat', id: t.id, label: t.title ?? t.id, sub: t.type ?? '', href: `/intelligence/threats/${t.id}` });
      }
      /* eslint-enable @typescript-eslint/no-explicit-any */

      setResults(out);
      setSearching(false);
    }, 250);
    return () => clearTimeout(timer);
  }, [paletteQuery]);

  /* ── Palette keyboard nav ── */
  const onPaletteKey = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx(i => Math.min(i + 1, results.length - 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setSelectedIdx(i => Math.max(i - 1, 0)); }
    if (e.key === 'Enter' && results[selectedIdx]) {
      e.preventDefault();
      router.push(results[selectedIdx].href);
      setShowPalette(false);
    }
  }, [results, selectedIdx, router]);

  /* ── Logout ── */
  const handleLogout = useCallback(() => {
    clearAuth();
    router.push('/login');
  }, [clearAuth, router]);

  /* ── Format run time ── */
  function fmtRunTime(iso: string) {
    return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  }

  return (
    <>
      <div className="topbar">
        <div className="tb">
          {/* Tenant chip + ⌘K shortcut hint removed — single-tenant deploy
              didn't need the branding chip, and the kbd hint was confusing
              (the palette still opens on click). */}
          <div className="tb-crumbs">
            {crumbs.map((c, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span className="sep">/</span>}
                <span className={i === crumbs.length - 1 ? 'here' : ''}>{c}</span>
              </React.Fragment>
            ))}
          </div>

          {/* Search bar — opens command palette on click */}
          <div
            className="tb-search"
            style={{ cursor: 'pointer' }}
            onClick={() => { setShowPalette(true); setShowNotifs(false); setShowUserMenu(false); }}
          >
            <Search s={13} />
            <span>{hint}</span>
          </div>

          {/* Bell — notifications */}
          <div ref={notifRef} style={{ position: 'relative' }}>
            <div
              className="tb-icon"
              style={{ cursor: 'pointer' }}
              onClick={() => { setShowNotifs(v => !v); setShowUserMenu(false); }}
            >
              <Bell s={15} />
              {failedRuns.length > 0 && <span className="dot" style={{ background: '#f85149' }} />}
            </div>
            {showNotifs && (
              <div style={{
                position: 'absolute', right: 0, top: '100%', marginTop: 6,
                width: 340, background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.4)', zIndex: 999,
                overflow: 'hidden',
              }}>
                <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Bell s={13} />
                  <span style={{ fontSize: 12, fontWeight: 600 }}>Notifications</span>
                  <span className="badge med" style={{ fontSize: 9, marginLeft: 'auto' }}>{failedRuns.length}</span>
                </div>
                <div style={{ maxHeight: 320, overflow: 'auto' }}>
                  {failedRuns.length === 0 && (
                    <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                      All clear — no failed or timed-out jobs.
                    </div>
                  )}
                  {failedRuns.map((run: RunInfo) => (
                    <div
                      key={run.run_id}
                      style={{
                        padding: '10px 14px', borderBottom: '1px solid var(--border)',
                        cursor: 'pointer', display: 'flex', gap: 10, alignItems: 'flex-start',
                      }}
                      onClick={() => { router.push('/operations/scheduler'); setShowNotifs(false); }}
                    >
                      <AlertTriangle s={14} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text)' }}>
                          {run.job_id}
                          <span className={`badge ${run.status === 'failed' ? 'crit' : 'high'}`} style={{ fontSize: 9, marginLeft: 6 }}>
                            {run.status}
                          </span>
                        </div>
                        {run.error_detail && (
                          <div title={run.error_detail} style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                            {run.error_detail}
                          </div>
                        )}
                        <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 3, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Clock s={9} /> {fmtRunTime(run.triggered_at)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                {failedRuns.length > 0 && (
                  <div
                    style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', textAlign: 'center', cursor: 'pointer', fontSize: 11, color: 'var(--accent)' }}
                    onClick={() => { router.push('/operations/scheduler'); setShowNotifs(false); }}
                  >
                    View all in Scheduler
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sparkles — navigate to Ask AI */}
          <div
            className="tb-icon"
            style={{ cursor: 'pointer' }}
            onClick={() => router.push('/ask')}
            title="Ask AI"
          >
            <Sparkles s={15} />
          </div>

          {/* User menu */}
          <div ref={userRef} style={{ position: 'relative' }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 4px', cursor: 'pointer' }}
              onClick={() => { setShowUserMenu(v => !v); setShowNotifs(false); }}
            >
              <div className="tb-avatar">{initials}</div>
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
                <div style={{ fontSize: 11.5, color: 'var(--text)', fontWeight: 500 }}>{displayName}</div>
                <div style={{ fontSize: 10, color: 'var(--text-4)' }}>{role}</div>
              </div>
              <ChevronDown s={10} />
            </div>
            {showUserMenu && (
              <div style={{
                position: 'absolute', right: 0, top: '100%', marginTop: 6,
                width: 200, background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.4)', zIndex: 999,
                overflow: 'hidden',
              }}>
                <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{displayName}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-4)' }}>{role}</div>
                </div>
                <div
                  style={{ padding: '8px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-2)' }}
                  onClick={() => { router.push('/admin/users'); setShowUserMenu(false); }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elev)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <Users s={13} /> Users & Roles
                </div>
                <div
                  style={{ padding: '8px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-2)' }}
                  onClick={() => { router.push('/admin/sessions'); setShowUserMenu(false); }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elev)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <Lock s={13} /> Sessions
                </div>
                <div
                  style={{ padding: '8px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-2)' }}
                  onClick={() => { router.push('/settings'); setShowUserMenu(false); }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elev)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <Settings s={13} /> Settings
                </div>
                <div style={{ borderTop: '1px solid var(--border)' }}>
                  <div
                    style={{ padding: '8px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#f85149' }}
                    onClick={handleLogout}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elev)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <X s={13} /> Logout
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Command Palette Overlay ── */}
      {showPalette && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', justifyContent: 'center', paddingTop: 100,
        }}>
          <div
            ref={paletteRef}
            style={{
              width: 580, maxHeight: 460, background: 'var(--bg-card)',
              border: '1px solid var(--border-strong)', borderRadius: 12,
              boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden',
              display: 'flex', flexDirection: 'column',
            }}
          >
            {/* Search input */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
              <Search s={16} />
              <input
                ref={inputRef}
                className="input"
                value={paletteQuery}
                onChange={e => setPaletteQuery(e.target.value)}
                onKeyDown={onPaletteKey}
                placeholder="Search articles, CVEs, IOCs, actors, threats…"
                style={{ flex: 1, border: 'none', background: 'transparent', fontSize: 14, padding: 0, outline: 'none' }}
                autoFocus
              />
              <span className="kbd" style={{ fontSize: 10, opacity: 0.5 }}>ESC</span>
            </div>

            {/* Results */}
            <div style={{ flex: 1, overflow: 'auto' }}>
              {!paletteQuery.trim() && (
                <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                  Type to search across all intelligence data…
                </div>
              )}

              {paletteQuery.trim() && searching && (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                  Searching…
                </div>
              )}

              {paletteQuery.trim() && !searching && results.length === 0 && (
                <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                  No results for &ldquo;{paletteQuery}&rdquo;
                </div>
              )}

              {results.length > 0 && results.map((r, i) => {
                const meta = TYPE_LABEL[r.type];
                return (
                  <div
                    key={`${r.type}-${r.id}`}
                    style={{
                      padding: '10px 16px', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 10,
                      background: i === selectedIdx ? 'var(--bg-elev)' : 'transparent',
                      borderLeft: i === selectedIdx ? `3px solid ${meta.color}` : '3px solid transparent',
                    }}
                    onClick={() => { router.push(r.href); setShowPalette(false); }}
                    onMouseEnter={() => setSelectedIdx(i)}
                  >
                    <span
                      className="tag"
                      style={{
                        fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
                        background: `${meta.color}18`, color: meta.color,
                        border: `1px solid ${meta.color}40`,
                        minWidth: 48, textAlign: 'center',
                      }}
                    >
                      {meta.label}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, color: 'var(--text)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.label}
                      </div>
                      {r.sub && (
                        <div style={{ fontSize: 10.5, color: 'var(--text-4)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 1 }}>
                          {r.sub}
                        </div>
                      )}
                    </div>
                    {i === selectedIdx && (
                      <span style={{ fontSize: 10, color: 'var(--text-4)' }}>↵</span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Footer hints */}
            <div style={{
              padding: '8px 16px', borderTop: '1px solid var(--border)',
              display: 'flex', gap: 16, fontSize: 10, color: 'var(--text-mute)',
            }}>
              <span>↑↓ Navigate</span>
              <span>↵ Open</span>
              <span>ESC Close</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
