'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import useSWR from 'swr';
import { fetcher } from '@/lib/api';
import { X, ChevronDown, Search } from '@/components/icons';

/**
 * TagPicker — multi-select restricted to the admin-defined catalog.
 *
 * Reads tags from `/api/tags?scope=<scope>`. Analysts cannot type free-text
 * tags; they pick from the catalog. New tags are added by admins from
 * the Settings page (/settings).
 *
 * Props:
 *   scope    — one of: ioc, asset, feed, actor, threat, article, cve
 *   value    — currently-selected tag names (strings)
 *   onChange — fires with the new list when user picks/unpicks
 *   placeholder — text shown when value is empty
 */

export interface TagDef {
  id: string;
  name: string;
  description: string | null;
  color: string | null;
  scopes: string[];
}

export interface TagPickerProps {
  scope: 'ioc' | 'asset' | 'feed' | 'actor' | 'threat' | 'article' | 'cve';
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
}

export default function TagPicker({
  scope, value, onChange, placeholder, disabled,
}: TagPickerProps) {
  const { data: tags = [], isLoading } = useSWR<TagDef[]>(`/tags?scope=${scope}`, fetcher);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const wrapRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      window.addEventListener('mousedown', onClickOutside);
      return () => window.removeEventListener('mousedown', onClickOutside);
    }
  }, [open]);

  const tagByName = useMemo(() => {
    const m = new Map<string, TagDef>();
    for (const t of tags) m.set(t.name, t);
    return m;
  }, [tags]);

  const available = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return tags
      .filter((t) => !value.includes(t.name))
      .filter((t) => !q || t.name.toLowerCase().includes(q) || (t.description ?? '').toLowerCase().includes(q));
  }, [tags, value, filter]);

  const toggle = (name: string) => {
    if (value.includes(name)) onChange(value.filter((v) => v !== name));
    else onChange([...value, name]);
  };

  const remove = (name: string) => onChange(value.filter((v) => v !== name));

  return (
    <div ref={wrapRef} style={{ position: 'relative' }}>
      {/* Selected chips + input area (looks like a multi-select input) */}
      <div
        style={{
          minHeight: 32,
          display: 'flex',
          flexWrap: 'wrap',
          gap: 4,
          alignItems: 'center',
          padding: '4px 28px 4px 6px',
          borderRadius: 6,
          border: '1px solid var(--border)',
          background: disabled ? 'var(--bg-page)' : 'var(--bg-card)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontSize: 12,
          color: 'var(--text)',
          position: 'relative',
        }}
        onClick={() => !disabled && setOpen((v) => !v)}
      >
        {value.length === 0 && (
          <span style={{ color: 'var(--text-4)', padding: '2px 6px' }}>
            {placeholder ?? `Select tags (${scope})…`}
          </span>
        )}
        {value.map((n) => {
          const def = tagByName.get(n);
          const color = def?.color ?? '#8b949e';
          return (
            <span
              key={n}
              className="mono"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '2px 6px',
                fontSize: 11,
                borderRadius: 4,
                background: `${color}1f`,
                border: `1px solid ${color}4d`,
                color,
              }}
            >
              {n}
              {!disabled && (
                <button
                  onClick={(e) => { e.stopPropagation(); remove(n); }}
                  style={{ all: 'unset', cursor: 'pointer', display: 'inline-flex' }}
                  title={`Remove ${n}`}
                >
                  <X s={10} />
                </button>
              )}
            </span>
          );
        })}
        <ChevronDown s={12} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-4)' }} />
      </div>

      {/* Dropdown */}
      {open && !disabled && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            zIndex: 200,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-strong)',
            borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            maxHeight: 280,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: 6, borderBottom: '1px solid var(--border)', position: 'relative' }}>
            <input
              className="input"
              placeholder={`Search tags in catalog…`}
              autoFocus
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              style={{ paddingLeft: 26, height: 28, fontSize: 12, width: '100%', boxSizing: 'border-box' }}
            />
            <Search s={11} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-4)', pointerEvents: 'none' }} />
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {isLoading && (
              <div style={{ padding: 12, fontSize: 11, color: 'var(--text-4)', textAlign: 'center' }}>Loading tag catalog…</div>
            )}
            {!isLoading && available.length === 0 && tags.length === 0 && (
              <div style={{ padding: 12, fontSize: 11.5, color: 'var(--text-4)', textAlign: 'center', lineHeight: 1.5 }}>
                No tags configured for scope <span className="mono">{scope}</span>.<br />
                Ask an admin to add some in <strong>Settings &rarr; Tags</strong>.
              </div>
            )}
            {!isLoading && available.length === 0 && tags.length > 0 && (
              <div style={{ padding: 10, fontSize: 11.5, color: 'var(--text-4)', textAlign: 'center' }}>
                {filter ? 'No tag matches the filter.' : 'All applicable tags already selected.'}
              </div>
            )}
            {available.map((t) => (
              <button
                key={t.id}
                onClick={(e) => { e.stopPropagation(); toggle(t.name); setFilter(''); }}
                style={{
                  all: 'unset',
                  display: 'flex',
                  flexDirection: 'column',
                  width: '100%',
                  padding: '8px 12px',
                  cursor: 'pointer',
                  borderBottom: '1px solid var(--border-soft)',
                  boxSizing: 'border-box',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-elev)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {t.color && (
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: t.color, flexShrink: 0 }} />
                  )}
                  <span className="mono" style={{ fontSize: 12, fontWeight: 500, color: 'var(--text)' }}>{t.name}</span>
                </div>
                {t.description && (
                  <div style={{ fontSize: 10.5, color: 'var(--text-4)', marginTop: 2, marginLeft: t.color ? 14 : 0 }}>{t.description}</div>
                )}
              </button>
            ))}
          </div>
          {tags.length > 0 && (
            <div style={{ padding: '6px 10px', borderTop: '1px solid var(--border)', fontSize: 10, color: 'var(--text-4)' }}>
              {tags.length} tag{tags.length === 1 ? '' : 's'} available for <span className="mono">{scope}</span> &middot; admin-managed
            </div>
          )}
        </div>
      )}
    </div>
  );
}
