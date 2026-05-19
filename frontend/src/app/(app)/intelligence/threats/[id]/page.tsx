'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import useSWR from 'swr';
import {
  ChevronLeft, More, Sparkles, Refresh, Pin, X,
  Check, AlertTriangle, Link as LinkIcon,
} from '@/components/icons';
import { useThreat } from '@/lib/hooks';
import { api, fetcher } from '@/lib/api';
import InsightView, { type InsightEnvelope } from '@/components/shared/InsightView';

/* ── types ──────────────────────────────────────────────────────────────── */

// Insight envelope reused via <InsightView> (shared with actor detail).
type Insight = InsightEnvelope;

interface Note {
  id: string;
  body: string;
  pinned: boolean;
  author: string;
  created_at: string;
  updated_at: string;
}

/* ── helpers ─────────────────────────────────────────────────────────────── */

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function sevBadge(s: string | null) {
  const sev = (s ?? '').toLowerCase();
  if (sev === 'critical') return <span className="badge crit">critical</span>;
  if (sev === 'high')     return <span className="badge high">high</span>;
  if (sev === 'medium')   return <span className="badge med">medium</span>;
  if (sev === 'low')      return <span className="badge low">low</span>;
  return <span className="badge mute">{s ?? 'unknown'}</span>;
}

const STATUS_OPTS = [
  { value: 'unreviewed', label: 'Unreviewed', cls: 'mute' },
  { value: 'relevant',   label: 'Relevant',   cls: 'low' },
  { value: 'not_relevant', label: 'Not relevant', cls: 'high' },
  { value: 'escalated',  label: 'Escalated',  cls: 'high' },
  { value: 'reviewed',   label: 'Reviewed',   cls: 'med' },
] as const;

function statusBadgeClass(s: string): string {
  return STATUS_OPTS.find(o => o.value === s)?.cls ?? 'mute';
}

/* ── page ────────────────────────────────────────────────────────────────── */

export default function ThreatDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;
  const [tab, setTab] = useState<'overview' | 'insight' | 'notes' | 'raw'>('overview');

  // Threat data
  const { data: threat, isLoading, mutate: mutateThreat } = useThreat(id);

  // Insight
  const { data: insight, isLoading: insightLoading, mutate: mutateInsight } = useSWR<Insight>(
    id ? `/threats/${id}/insight` : null, fetcher,
    { revalidateOnFocus: false, errorRetryCount: 0 },
  );
  const [analyzing, setAnalyzing] = useState(false);

  // Notes
  const { data: notesData, mutate: mutateNotes } = useSWR<{ items: Note[]; total: number }>(
    id ? `/threats/${id}/notes` : null, fetcher,
    { revalidateOnFocus: false },
  );
  const notes = notesData?.items ?? [];
  const [noteBody, setNoteBody] = useState('');
  const [notePinned, setNotePinned] = useState(false);
  const [postingNote, setPostingNote] = useState(false);

  // Status menu
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  /* ── actions ─────────────────────────────────────────────────────────── */

  // `force=false` (the default) is cheap — backend returns the cached
  // insight without calling the AI if one exists at the current prompt
  // version. Used by the "Generate insight" button on first view.
  // `force=true` re-runs the whole pipeline (IOCs + hunt + flowviz) — the
  // "Re-analyze" button at the bottom of the panel does that explicitly.
  const handleAnalyze = useCallback(async (force = false) => {
    setAnalyzing(true);
    try {
      await api.post(`/threats/${id}/analyze`, force ? { force: true } : {});
      // Cached responses come back in <1s; fresh ones can take 60-90s.
      // Either way the POST already returned, just remutate.
      mutateInsight();
    } finally { setAnalyzing(false); }
  }, [id, mutateInsight]);

  const handlePostNote = useCallback(async () => {
    if (!noteBody.trim()) return;
    setPostingNote(true);
    try {
      await api.post(`/threats/${id}/notes`, { body: noteBody, pinned: notePinned });
      setNoteBody(''); setNotePinned(false); mutateNotes();
    } finally { setPostingNote(false); }
  }, [id, noteBody, notePinned, mutateNotes]);

  const handleDeleteNote = useCallback(async (noteId: string) => {
    await api.delete(`/threats/${id}/notes/${noteId}`);
    mutateNotes();
  }, [id, mutateNotes]);

  const handleTogglePin = useCallback(async (note: Note) => {
    await api.patch(`/threats/${id}/notes/${note.id}`, { pinned: !note.pinned });
    mutateNotes();
  }, [id, mutateNotes]);

  const handleStatus = useCallback(async (status: string) => {
    await api.patch(`/threats/${id}/status`, { analyst_status: status });
    mutateThreat(); setMenuOpen(false);
  }, [id, mutateThreat]);

  /* ── render ──────────────────────────────────────────────────────────── */

  if (isLoading) {
    return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)' }}>Loading threat...</div>;
  }
  if (!threat) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)', gap: 12 }}>
        <div>Threat not found</div>
        <button className="btn" onClick={() => router.back()}><ChevronLeft s={12} />Go back</button>
      </div>
    );
  }

  const details = threat.details ?? {};

  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateColumns: '60% 40%', overflow: 'hidden' }}>
      {/* LEFT */}
      <div style={{ overflow: 'auto', padding: 22, borderRight: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <button className="btn sm" onClick={() => router.back()}><ChevronLeft s={11} />Threats</button>
          <span className="tag">{threat.type}</span>
          {sevBadge(threat.severity)}
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 6, position: 'relative' }}>
            {threat.source_url && (
              <a href={threat.source_url} target="_blank" rel="noreferrer" className="btn sm"><LinkIcon s={11} />Source</a>
            )}
            <button className="btn sm" onClick={() => handleStatus('escalated')}><AlertTriangle s={11} />Escalate</button>
            <div ref={menuRef} style={{ position: 'relative' }}>
              <button className="btn sm" onClick={() => setMenuOpen(o => !o)}><More s={11} /></button>
              {menuOpen && (
                <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: 4, background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6, padding: 4, zIndex: 100, minWidth: 160, boxShadow: '0 4px 12px rgba(0,0,0,.4)' }}>
                  {STATUS_OPTS.map(o => (
                    <div key={o.value} onClick={() => handleStatus(o.value)}
                         style={{ padding: '6px 10px', fontSize: 12, cursor: 'pointer', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 6, color: threat.analyst_status === o.value ? 'var(--accent)' : 'var(--text-2)' }}
                         onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                         onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                      {threat.analyst_status === o.value && <Check s={10} />}
                      <span className={`badge ${o.cls}`} style={{ fontSize: 10 }}>{o.label}</span>
                    </div>
                  ))}
                  <div style={{ borderTop: '1px solid var(--border)', margin: '4px 0' }} />
                  <div onClick={() => { navigator.clipboard.writeText(id); setMenuOpen(false); }}
                       style={{ padding: '6px 10px', fontSize: 12, cursor: 'pointer', borderRadius: 4, color: 'var(--text-3)' }}
                       onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                       onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                    Copy ID
                  </div>
                </div>
              )}
            </div>
          </span>
        </div>

        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text)', lineHeight: 1.3, letterSpacing: '-0.015em', margin: '4px 0 8px' }}>
          {threat.title}
        </h1>

        <div style={{ color: 'var(--text-3)', fontSize: 12.5, display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 14 }}>
          <strong style={{ color: 'var(--text-2)', fontWeight: 500 }}>{threat.source}</strong>
          <span>Observed {fmtDate(threat.observed_at)}</span>
        </div>

        {/* Metrics row — Confidence column intentionally omitted (operator
            dropped numeric confidence platform-wide). */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
          <div style={{ flex: 1, padding: '10px 12px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6 }}>
            <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Status</div>
            <span className={`badge ${statusBadgeClass(threat.analyst_status)}`}>{threat.analyst_status || 'unreviewed'}</span>
          </div>
          <div style={{ flex: 1, padding: '10px 12px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6 }}>
            <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Type</div>
            <span className="tag" style={{ fontSize: 12 }}>{threat.type}</span>
          </div>
        </div>

        {/* Summary */}
        {threat.summary && (
          <>
            <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Summary</div>
            <p style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--text-2)', margin: '0 0 18px' }}>{threat.summary}</p>
          </>
        )}

        {/* Structured details */}
        {Object.keys(details).length > 0 && (
          <>
            <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6, marginTop: 10 }}>Details</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {Object.entries(details).map(([key, val]) => (
                <div key={key} style={{ padding: '8px 10px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                    {key.replace(/_/g, ' ')}
                  </div>
                  {typeof val === 'string' ? (
                    <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.5 }}>{val}</div>
                  ) : Array.isArray(val) ? (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {(val as unknown[]).map((v, i) => <span key={i} className="tag">{typeof v === 'string' ? v : JSON.stringify(v)}</span>)}
                    </div>
                  ) : (
                    <pre style={{ fontSize: 11, color: 'var(--text-3)', margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)' }}>{JSON.stringify(val, null, 2)}</pre>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* RIGHT */}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg-page)' }}>
        <div style={{ padding: '0 14px', borderBottom: '1px solid var(--border)' }}>
          <div className="tabs" style={{ border: 'none' }}>
            {(['insight', 'notes', 'raw'] as const).map(t => (
              <div key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)} style={{ textTransform: 'capitalize' }}>
                {t}{t === 'notes' && notes.length > 0 ? ` (${notes.length})` : ''}
              </div>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 14 }}>
          {/* Insight tab */}
          {tab === 'insight' && (
            <>
              {insightLoading && <div style={{ textAlign: 'center', color: 'var(--text-4)', padding: 30 }}>Loading insight...</div>}
              {!insightLoading && !insight && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-4)', gap: 10 }}>
                  <Sparkles s={24} />
                  <div style={{ fontSize: 13 }}>No AI insight yet</div>
                  <button className="btn sm" onClick={() => handleAnalyze(false)} disabled={analyzing}>
                    <Refresh s={11} />{analyzing ? 'Analyzing...' : 'Generate insight'}
                  </button>
                </div>
              )}
              {!insightLoading && insight && (
                <InsightView
                  insight={insight}
                  analyzing={analyzing}
                  onReanalyze={() => handleAnalyze(true)}
                />
              )}
            </>
          )}

          {/* Notes tab */}
          {tab === 'notes' && (
            <div>
              <div style={{ padding: 10, background: 'var(--bg-elev)', borderRadius: 6, border: '1px solid var(--border)', marginBottom: 12 }}>
                <textarea className="input" rows={3} placeholder="Add a note..."
                          value={noteBody} onChange={e => setNoteBody(e.target.value)}
                          style={{ height: 'auto', padding: 10, fontFamily: 'var(--sans)', width: '100%' }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                  <label style={{ fontSize: 11.5, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                    <input type="checkbox" checked={notePinned} onChange={e => setNotePinned(e.target.checked)} style={{ accentColor: '#d29922' }} />Pin
                  </label>
                  <button className="btn primary sm" style={{ marginLeft: 'auto' }} onClick={handlePostNote}
                          disabled={postingNote || !noteBody.trim()}>
                    {postingNote ? 'Posting...' : 'Post note'}
                  </button>
                </div>
              </div>
              {notes.length === 0 && <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-4)', padding: 20 }}>No notes yet.</div>}
              {notes.map(n => (
                <div key={n.id} style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)', marginBottom: 6, borderLeft: n.pinned ? '3px solid #d29922' : '1px solid var(--border)', background: n.pinned ? 'rgba(210,153,34,0.04)' : 'transparent' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)' }}>{n.author}</span>
                    <span style={{ fontSize: 10, color: 'var(--text-4)' }}>{timeAgo(n.created_at)}</span>
                    {n.pinned && <Pin s={9} />}
                    <span style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                      <button className="btn sm" style={{ padding: '2px 4px' }} onClick={() => handleTogglePin(n)} title={n.pinned ? 'Unpin' : 'Pin'}><Pin s={9} /></button>
                      <button className="btn sm" style={{ padding: '2px 4px' }} onClick={() => handleDeleteNote(n.id)} title="Delete"><X s={9} /></button>
                    </span>
                  </div>
                  <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{n.body}</div>
                </div>
              ))}
            </div>
          )}

          {/* Raw tab */}
          {tab === 'raw' && (
            <pre style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', margin: 0 }}>
              {JSON.stringify(threat, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}


// (ThreatInsightView moved to components/shared/InsightView.tsx — also
// used by the actor detail page so both surfaces render the v2 insight
// payload the same way.)
