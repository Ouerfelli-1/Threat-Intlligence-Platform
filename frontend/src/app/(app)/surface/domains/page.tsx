'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Globe, Plus, Camera, Activity, GitBranch, Crosshair, Refresh,
  Shield, Server, Lock,
} from '@/components/icons';
import { useList } from '@/lib/hooks';
import { api } from '@/lib/api';
import { useStore } from '@/lib/store';

interface Domain {
  id: string;
  name: string;
  active: boolean;
  added_at: string;
  last_checked_at: string | null;
}

interface Snapshot {
  id: string;
  domain_id: string;
  captured_at: string;
  details: Record<string, unknown>;
  content_hash: string | null;
  screenshot_path: string | null;
}

interface Change {
  id: string;
  domain_id: string;
  detected_at: string;
  change_type: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
    + ' · '
    + new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function howLongAgo(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3_600_000);
  const d = Math.floor(diff / 86_400_000);
  if (d > 0) return `${d}d ago`;
  if (h > 0) return `${h}h ago`;
  return 'recent';
}

/* ── Snapshot detail extractor ──────────────────────────────────────────── */

function DetailSection({ label, icon: Icon, children }: { label: string; icon: React.FC<{ s?: number }>; children: React.ReactNode }) {
  return (
    <div style={{ padding: '8px 10px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 6, marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <Icon s={11} />
        <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      </div>
      {children}
    </div>
  );
}

function SnapshotDetails({ details }: { details: Record<string, unknown> }) {
  const dns = details.dns as Record<string, unknown> | undefined;
  const whois = details.whois as Record<string, unknown> | undefined;
  const ssl = (details.ssl ?? details.certificate) as Record<string, unknown> | undefined;
  const iocs = details.iocs as Array<Record<string, string>> | undefined;

  return (
    <div>
      {/* DNS Records */}
      {dns && Object.keys(dns).length > 0 && (
        <DetailSection label="DNS Records" icon={Globe}>
          {Object.entries(dns).map(([type, records]) => (
            <div key={type} style={{ marginBottom: 4 }}>
              <span className="mono" style={{ fontSize: 10, color: 'var(--accent)', marginRight: 8 }}>{type.toUpperCase()}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                {Array.isArray(records) ? records.join(', ') : String(records)}
              </span>
            </div>
          ))}
        </DetailSection>
      )}

      {/* WHOIS / Registrar */}
      {whois && Object.keys(whois).length > 0 && (
        <DetailSection label="WHOIS / Registrar" icon={Server}>
          {Object.entries(whois).slice(0, 8).map(([key, val]) => (
            <div key={key} style={{ display: 'flex', gap: 8, marginBottom: 2 }}>
              <span style={{ fontSize: 10, color: 'var(--text-4)', width: 100, flexShrink: 0 }}>{key.replace(/_/g, ' ')}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{typeof val === 'string' ? val : JSON.stringify(val)}</span>
            </div>
          ))}
        </DetailSection>
      )}

      {/* SSL Certificate */}
      {ssl && Object.keys(ssl).length > 0 && (
        <DetailSection label="SSL Certificate" icon={Lock}>
          {Object.entries(ssl).slice(0, 6).map(([key, val]) => (
            <div key={key} style={{ display: 'flex', gap: 8, marginBottom: 2 }}>
              <span style={{ fontSize: 10, color: 'var(--text-4)', width: 100, flexShrink: 0 }}>{key.replace(/_/g, ' ')}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{typeof val === 'string' ? val : JSON.stringify(val)}</span>
            </div>
          ))}
        </DetailSection>
      )}

      {/* IOCs */}
      {iocs && iocs.length > 0 && (
        <DetailSection label="IOCs Found" icon={Crosshair}>
          {iocs.map((ioc, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
              <span className="tag" style={{ fontSize: 9 }}>{ioc.type ?? ioc.ioc_type ?? 'indicator'}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{ioc.value}</span>
              <span style={{ fontSize: 10, color: 'var(--text-4)' }}>{ioc.source}</span>
            </div>
          ))}
        </DetailSection>
      )}

      {/* Fallback: raw keys not already rendered. Hide internal file paths
          (screenshot_path, output_path) — those are server-side storage refs
          that mean nothing to the analyst and only add clutter. */}
      {(() => {
        const shown = new Set(['dns', 'whois', 'ssl', 'certificate', 'iocs',
                               'screenshot_path', 'screenshot', 'output_path']);
        const remaining = Object.entries(details).filter(([k]) => !shown.has(k));
        if (remaining.length === 0) return null;
        return (
          <DetailSection label="Additional Data" icon={Activity}>
            {remaining.map(([key, val]) => (
              <div key={key} style={{ marginBottom: 4 }}>
                <span style={{ fontSize: 10, color: 'var(--text-4)' }}>{key.replace(/_/g, ' ')}: </span>
                {typeof val === 'string' || typeof val === 'number' ? (
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{String(val)}</span>
                ) : (
                  <pre style={{ fontSize: 10, color: 'var(--text-3)', margin: '2px 0 0', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap' }}>{JSON.stringify(val, null, 2)}</pre>
                )}
              </div>
            ))}
          </DetailSection>
        );
      })()}
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────────────────── */

export default function DomainWatchPage() {
  const token = useStore(s => s.token);
  const [filter, setFilter] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [capturing, setCapturing] = useState(false);
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);

  const { items: domains, isLoading: dLoading, mutate } = useList<Domain>('/domains');

  const filteredDomains = domains.filter(d =>
    !filter || d.name.toLowerCase().includes(filter.toLowerCase())
  );

  const selected = domains.find(d => d.id === selectedId) ?? (domains.length > 0 && !selectedId ? domains[0] : null);
  const effectiveId = selected?.id ?? null;

  const { items: selSnapshots, mutate: mutSnap } = useList<Snapshot>(effectiveId ? `/domains/${effectiveId}/snapshots` : '');
  const { items: selChanges }   = useList<Change>(effectiveId ? `/domains/${effectiveId}/changes` : '');

  // Load screenshot as blob URL
  useEffect(() => {
    if (!effectiveId) { setScreenshotUrl(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/domains/${effectiveId}/screenshot`, {
          headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        });
        if (res.ok && !cancelled) {
          const blob = await res.blob();
          setScreenshotUrl(URL.createObjectURL(blob));
        } else {
          setScreenshotUrl(null);
        }
      } catch { setScreenshotUrl(null); }
    })();
    return () => { cancelled = true; };
  }, [effectiveId, token]);

  const handleAdd = useCallback(async () => {
    if (!newName.trim()) return;
    await api.post('/domains', { name: newName.trim() });
    setNewName(''); setAddOpen(false); mutate();
  }, [newName, mutate]);

  const [captureMsg, setCaptureMsg] = useState<string | null>(null);

  const handleCapture = useCallback(async () => {
    if (!effectiveId) return;
    setCapturing(true);
    setCaptureMsg(null);
    try {
      // Backend returns 202 — capture runs async (Playwright nav + screenshot
      // + DNS + WHOIS). 15s gives the pipeline a realistic head-start before
      // we poll. Then refetch snapshots so the new screenshot shows up.
      await api.post(`/domains/${effectiveId}/check`);
      setCaptureMsg('Capture started — refreshing snapshots in 15s…');
      setTimeout(() => {
        mutSnap();
        mutate();
        setCapturing(false);
        setCaptureMsg(null);
      }, 15000);
    } catch (e: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const err = e as { status?: number; body?: { detail?: string; message?: string } };
      const detail = err?.body?.detail ?? err?.body?.message ?? (e instanceof Error ? e.message : 'unknown error');
      setCaptureMsg(`Capture failed: ${detail}`);
      setCapturing(false);
    }
  }, [effectiveId, mutSnap, mutate]);

  const handleArchive = useCallback(async (active: boolean) => {
    if (!effectiveId) return;
    try {
      await api.patch(`/domains/${effectiveId}`, { active });
      mutate();
    } catch (e) { alert(`Failed to ${active ? 'restore' : 'archive'}: ${e}`); }
  }, [effectiveId, mutate]);

  const handleDelete = useCallback(async () => {
    if (!effectiveId || !selected) return;
    if (!confirm(`Delete watched domain "${selected.name}" and all its snapshots? This cannot be undone.`)) return;
    try {
      await api.delete(`/domains/${effectiveId}`);
      setSelectedId(null);
      mutate();
    } catch (e) { alert(`Failed to delete: ${e}`); }
  }, [effectiveId, selected, mutate]);

  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateColumns: '300px 1fr', overflow: 'hidden' }}>
      {/* Left column — domain list */}
      <div style={{ borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Globe s={13} />
          <div style={{ fontSize: 13, fontWeight: 600 }}>Watched domains</div>
          {!dLoading && <span className="badge med" style={{ marginLeft: 4 }}>{domains.length}</span>}
          <button className="btn sm" style={{ marginLeft: 'auto' }} onClick={() => mutate()}><Refresh s={11} /></button>
          <button className="btn sm" onClick={() => setAddOpen(true)}><Plus s={11} />Add</button>
        </div>

        {/* Add domain inline form */}
        {addOpen && (
          <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 6 }}>
            <input className="input" placeholder="example.com" style={{ height: 26, flex: 1 }}
                   value={newName} onChange={e => setNewName(e.target.value)}
                   onKeyDown={e => e.key === 'Enter' && handleAdd()} autoFocus />
            <button className="btn sm primary" onClick={handleAdd} disabled={!newName.trim()}>Add</button>
            <button className="btn sm" onClick={() => { setAddOpen(false); setNewName(''); }}>Cancel</button>
          </div>
        )}

        <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
          <input className="input" placeholder="Filter..." style={{ height: 26 }}
                 value={filter} onChange={e => setFilter(e.target.value)} />
        </div>
        <div style={{ overflow: 'auto', flex: 1 }}>
          {dLoading && <div style={{ padding: 20, color: 'var(--text-4)', fontSize: 12 }}>Loading domains...</div>}
          {!dLoading && domains.length === 0 && (
            <div style={{ padding: 20, color: 'var(--text-4)', fontSize: 12, textAlign: 'center' }}>
              No domains being watched.<br />Add a domain to start monitoring.
            </div>
          )}
          {filteredDomains.map((d) => {
            const isSelected = (selectedId === d.id) || (!selectedId && d === domains[0]);
            return (
              <div key={d.id} onClick={() => setSelectedId(d.id)}
                   style={{ padding: '8px 12px', borderBottom: '1px solid var(--border-soft)', cursor: 'pointer', background: isSelected ? 'rgba(88,166,255,0.06)' : 'transparent', borderLeft: isSelected ? '2px solid var(--accent)' : '2px solid transparent' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span className={`sev-dot ${d.active ? 'low' : 'mute'}`} />
                  <div title={d.name} className="mono" style={{ fontSize: 11.5, color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</div>
                  {!d.active && <span className="tag" style={{ fontSize: 9 }}>off</span>}
                </div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--text-mute)', marginTop: 2 }}>
                  {d.last_checked_at ? `last check ${howLongAgo(d.last_checked_at)}` : 'not yet checked'}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right — detail */}
      <div style={{ overflow: 'auto' }}>
        {!selected && !dLoading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)', flexDirection: 'column', gap: 12 }}>
            <Globe s={32} />
            <div style={{ fontSize: 13 }}>Select a domain to view details</div>
          </div>
        )}

        {selected && (
          <>
            <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span className={`sev-dot ${selected.active ? 'low' : 'mute'}`} />
                <h1 className="mono" style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.01em', margin: 0, color: 'var(--text)' }}>{selected.name}</h1>
                <span className={`badge ${selected.active ? 'low' : 'mute'}`}>{selected.active ? 'active' : 'inactive'}</span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                  <button className="btn sm" onClick={handleCapture} disabled={capturing}>
                    <Camera s={11} />{capturing ? 'Capturing...' : 'Capture now'}
                  </button>
                  {selected.active ? (
                    <button className="btn sm" onClick={() => handleArchive(false)} title="Archive — stop monitoring but keep history">
                      Archive
                    </button>
                  ) : (
                    <button className="btn sm" onClick={() => handleArchive(true)} title="Restore to active watch list">
                      Restore
                    </button>
                  )}
                  <button className="btn sm" onClick={handleDelete} title="Delete domain and all snapshots permanently">
                    Delete
                  </button>
                </div>
              </div>
              {/* Capture status — shows whether the async job kicked off
                  successfully. Without this the "Capture now" button looked
                  inert if the backend rejected the request. */}
              {captureMsg && (
                <div style={{ marginTop: 8, fontSize: 11.5, color: captureMsg.startsWith('Capture failed') ? '#f85149' : 'var(--text-3)' }}>
                  {captureMsg}
                </div>
              )}
              <div style={{ display: 'flex', gap: 14, marginTop: 6, fontSize: 11.5, color: 'var(--text-3)' }}>
                <span>Added: <span className="mono" style={{ color: 'var(--text-2)' }}>{fmtDate(selected.added_at)}</span></span>
                {selected.last_checked_at && (
                  <span>Last check: <span className="mono" style={{ color: 'var(--text-2)' }}>{fmtDate(selected.last_checked_at)}</span></span>
                )}
              </div>
            </div>

            <div style={{ padding: 14, display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 12 }}>
              {/* Latest snapshot + screenshot */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Screenshot */}
                <div className="card">
                  <div className="card-h">
                    <Camera s={13} />
                    <div className="t">Screenshot</div>
                    <div className="s">{selSnapshots.length > 0 ? fmtDate(selSnapshots[0].captured_at) : 'no snapshots'}</div>
                  </div>
                  {screenshotUrl ? (
                    <div style={{ padding: 8 }}>
                      <img src={screenshotUrl} alt={`Screenshot of ${selected.name}`}
                           style={{ width: '100%', borderRadius: 4, border: '1px solid var(--border)' }} />
                    </div>
                  ) : (
                    <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                      No screenshot available. Click "Capture now" to take one.
                    </div>
                  )}
                </div>

                {/* Parsed snapshot details */}
                {selSnapshots.length > 0 && Object.keys(selSnapshots[0].details).length > 0 && (
                  <div className="card" style={{ padding: 12 }}>
                    <SnapshotDetails details={selSnapshots[0].details} />
                    {selSnapshots[0].content_hash && (
                      <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 8 }}>
                        Content hash: <span className="mono" style={{ color: 'var(--text-3)' }}>{selSnapshots[0].content_hash}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Right panels */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Snapshot history */}
                <div className="card">
                  <div className="card-h">
                    <Activity s={13} />
                    <div className="t">Snapshot history</div>
                    <div className="s">{selSnapshots.length} capture{selSnapshots.length !== 1 ? 's' : ''}</div>
                  </div>
                  {selSnapshots.length === 0 ? (
                    <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 11 }}>No snapshots</div>
                  ) : (
                    <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {selSnapshots.slice(0, 8).map((s, i) => (
                        <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: i < Math.min(selSnapshots.length, 8) - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--low)', flexShrink: 0 }} />
                          <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)', flex: 1 }}>{fmtDate(s.captured_at)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Changes */}
                <div className="card">
                  <div className="card-h">
                    <GitBranch s={13} />
                    <div className="t">Changes detected</div>
                    <div className="s">{selChanges.length}</div>
                  </div>
                  {selChanges.length === 0 ? (
                    <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 11 }}>No changes detected</div>
                  ) : (
                    <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {selChanges.slice(0, 6).map((c, i) => (
                        <div key={c.id} style={{ padding: '6px 0', borderBottom: i < Math.min(selChanges.length, 6) - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span className="tag" style={{ fontSize: 10 }}>{c.change_type}</span>
                            <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>{fmtDate(c.detected_at)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
