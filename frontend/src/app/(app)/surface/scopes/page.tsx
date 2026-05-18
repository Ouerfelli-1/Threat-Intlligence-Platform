'use client';

import React, { useCallback, useState } from 'react';
import { Layers, AlertTriangle, Play, Plus, ChevronRight, Refresh, X, Trash, Pause } from '@/components/icons';
import { useList } from '@/lib/hooks';
import { api } from '@/lib/api';

interface Scope {
  id: string;
  name: string;
  description: string | null;
  config: Record<string, unknown>;
  active: boolean;
  created_at: string;
}

interface Target {
  id: string;
  scope_id: string;
  type: string;
  value: string;
  description: string | null;
  active: boolean;
  added_at: string;
}

interface Finding {
  id: string;
  job_id: string;
  target_id: string | null;
  type: string;
  value: string;
  source: string;
  discovered_at: string;
  details: Record<string, unknown>;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) +
    ' · ' + new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function severityFromType(type: string): string {
  if (type.includes('takeover') || type.includes('exposure')) return 'crit';
  if (type.includes('open') || type.includes('lookalike')) return 'high';
  if (type.includes('cert') || type.includes('expired')) return 'med';
  return 'low';
}

function sevLabel(sev: string) {
  if (sev === 'crit') return 'Critical';
  if (sev === 'high') return 'High';
  if (sev === 'med')  return 'Medium';
  return 'Low';
}

const TARGET_TYPES = ['domain', 'subdomain', 'ip', 'cidr', 'asn', 'tls_cert'];

export default function AsmPage() {
  const [selectedScope, setSelectedScope] = useState<string | null>(null);

  const { items: scopes,   isLoading: loadingScopes,   mutate: mutateScopes } = useList<Scope>('/scopes');
  const { items: targets,  isLoading: loadingTargets,  mutate: mutateTargets } = useList<Target>('/targets', { limit: 500 });
  const { items: findings, isLoading: loadingFindings, mutate: mutateFindings } = useList<Finding>(
    '/findings',
    selectedScope ? { scope_id: selectedScope, limit: 200 } : { limit: 200 },
  );

  // Modals
  const [showScopeModal, setShowScopeModal]   = useState(false);
  const [showTargetModal, setShowTargetModal] = useState<string | null>(null); // scope_id when open
  const [scanError, setScanError]             = useState<string | null>(null);
  const [scanRunning, setScanRunning]         = useState(false);

  // Scope form
  const [scopeForm, setScopeForm]       = useState({ name: '', description: '' });
  const [savingScope, setSavingScope]   = useState(false);
  const [scopeError, setScopeError]     = useState<string | null>(null);

  // Target form
  const [targetForm, setTargetForm]     = useState({ type: 'domain', value: '', description: '' });
  const [savingTarget, setSavingTarget] = useState(false);
  const [targetError, setTargetError]   = useState<string | null>(null);

  const totalFindings = findings.length;
  const latestDiscovery = findings.length > 0
    ? findings.reduce((latest, f) => (f.discovered_at > latest ? f.discovered_at : latest), findings[0].discovered_at)
    : null;
  const isLoading = loadingScopes || loadingFindings;

  const triggerScan = useCallback(async () => {
    setScanError(null); setScanRunning(true);
    try {
      await api.post('/scan/run', {});
      // Optimistic: refresh findings after a short delay
      setTimeout(() => { mutateFindings(); mutateScopes(); }, 2000);
    } catch (e) {
      setScanError(String(e));
    } finally {
      setScanRunning(false);
    }
  }, [mutateFindings, mutateScopes]);

  const createScope = useCallback(async () => {
    if (!scopeForm.name.trim()) { setScopeError('Name required'); return; }
    setSavingScope(true); setScopeError(null);
    try {
      await api.post('/scopes', {
        name: scopeForm.name.trim(),
        description: scopeForm.description.trim() || null,
        config: {},
      });
      setShowScopeModal(false);
      setScopeForm({ name: '', description: '' });
      mutateScopes();
    } catch (e) {
      setScopeError(String(e));
    } finally {
      setSavingScope(false);
    }
  }, [scopeForm, mutateScopes]);

  const createTarget = useCallback(async () => {
    if (!showTargetModal || !targetForm.value.trim()) { setTargetError('Value required'); return; }
    setSavingTarget(true); setTargetError(null);
    try {
      await api.post('/targets', {
        scope_id: showTargetModal,
        type: targetForm.type,
        value: targetForm.value.trim(),
        description: targetForm.description.trim() || null,
      });
      setShowTargetModal(null);
      setTargetForm({ type: 'domain', value: '', description: '' });
      mutateTargets();
    } catch (e) {
      setTargetError(String(e));
    } finally {
      setSavingTarget(false);
    }
  }, [showTargetModal, targetForm, mutateTargets]);

  const deleteScope = useCallback(async (id: string, name: string) => {
    if (!confirm(`Delete scope "${name}"? Targets, jobs, and findings linked to this scope will all be removed.`)) return;
    try {
      await api.delete(`/scopes/${id}`);
      mutateScopes(); mutateTargets(); mutateFindings();
    } catch (e) { alert(String(e)); }
  }, [mutateScopes, mutateTargets, mutateFindings]);

  // Pause/resume a scope — flips active boolean. The scanner already filters
  // on Scope.active so the next scheduled run will skip paused scopes.
  const toggleScope = useCallback(async (s: Scope) => {
    try {
      await api.patch(`/scopes/${s.id}`, { active: !s.active });
      mutateScopes();
    } catch (e) { alert(String(e)); }
  }, [mutateScopes]);

  // Pause/resume a single target — same logic, per-target.
  const toggleTarget = useCallback(async (t: Target) => {
    try {
      await api.patch(`/targets/${t.id}`, { active: !t.active });
      mutateTargets();
    } catch (e) { alert(String(e)); }
  }, [mutateTargets]);

  const deleteTarget = useCallback(async (t: Target) => {
    if (!confirm(`Delete target "${t.value}"? Removes it permanently. Use pause if you might re-enable later.`)) return;
    try {
      await api.delete(`/targets/${t.id}`);
      mutateTargets();
    } catch (e) { alert(String(e)); }
  }, [mutateTargets]);

  return (
    // Page is a flex column with hidden overflow; the two interior cards each
    // own their own scroll. That way long finding lists never push the scope
    // list off-screen — and the header stays sticky.
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10, flexShrink: 0 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Attack Surface Management</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading…' : `${scopes.length} scopes · ${targets.length} targets · ${totalFindings} findings`}
          {latestDiscovery && ` · last discovery ${fmtDate(latestDiscovery)}`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => { mutateScopes(); mutateTargets(); mutateFindings(); }}><Refresh s={12} />Refresh</button>
          <button className="btn" onClick={triggerScan} disabled={scanRunning}>
            {scanRunning ? <Refresh s={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Play s={12} />}
            {scanRunning ? 'Starting…' : 'Trigger scan'}
          </button>
          <button className="btn primary" onClick={() => { setScopeError(null); setShowScopeModal(true); }}><Plus s={12} />New scope</button>
        </div>
      </div>

      {scanError && (
        <div style={{ marginBottom: 10, padding: '8px 12px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6, color: '#f85149', fontSize: 12, flexShrink: 0 }}>
          <AlertTriangle s={11} style={{ marginRight: 4 }} />{scanError}
        </div>
      )}

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-4)' }}>Loading ASM data…</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 12, flex: 1, overflow: 'hidden', minHeight: 0 }}>
          {/* Scopes — independent vertical scroll */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
            <div className="card-h" style={{ flexShrink: 0 }}><Layers s={13} /><div className="t">Scopes</div><div className="s">{scopes.length}</div></div>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            {scopes.length === 0 ? (
              <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                No scopes configured yet. Click <strong>New scope</strong> to start passive discovery.
              </div>
            ) : (
              scopes.map((s, i) => {
                const scopeTargets = targets.filter((t) => t.scope_id === s.id);
                const isSelected = selectedScope === s.id;
                const isAutoSync = s.name === 'profile:auto-sync';
                const paused = s.active === false;

                return (
                  <div key={s.id} onClick={() => setSelectedScope(isSelected ? null : s.id)}
                    style={{ padding: '10px 14px', borderBottom: i < scopes.length - 1 ? '1px solid var(--border-soft)' : 'none', cursor: 'pointer', background: isSelected ? 'rgba(88,166,255,0.05)' : 'transparent', borderLeft: isSelected ? '2px solid var(--accent)' : '2px solid transparent', opacity: paused ? 0.7 : 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <ChevronRight s={12} />
                      <div style={{ flex: 1, fontSize: 12.5, color: 'var(--text)', fontWeight: 500 }}>{s.name}</div>
                      {isAutoSync && <span className="tag" style={{ fontSize: 10, color: '#58a6ff' }} title="Auto-synced from CMDB company profile (domains + IP ranges + ASNs). Edit /assets/profile to manage entries.">CMDB sync</span>}
                      <span className={`badge ${!paused ? 'low' : 'mute'}`}>
                        <span className="dot" />{!paused ? 'active' : 'paused'}
                      </span>
                      {/* Pause / Resume — works for CMDB-sync scopes too so analyst
                          can halt noisy auto-discovered targets without editing CMDB. */}
                      <button className="btn sm" style={{ padding: '2px 6px' }}
                              title={paused ? 'Resume scanning' : 'Pause scanning'}
                              onClick={(e) => { e.stopPropagation(); toggleScope(s); }}>
                        {paused ? <Play s={11} /> : <Pause s={11} />}
                      </button>
                      {!isAutoSync && (
                        <button className="btn sm" style={{ padding: '2px 6px' }} title="Delete scope (cascades to targets, jobs, findings)"
                                onClick={(e) => { e.stopPropagation(); deleteScope(s.id, s.name); }}>
                          <Trash s={11} />
                        </button>
                      )}
                    </div>
                    {s.description && (
                      <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 2, paddingLeft: 20 }}>{s.description}</div>
                    )}
                    <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-4)', marginTop: 4, paddingLeft: 20, alignItems: 'center' }}>
                      <span><span className="mono" style={{ color: 'var(--text-3)' }}>{scopeTargets.length}</span> targets</span>
                      {!isAutoSync && (
                        <button className="btn sm" style={{ padding: '2px 6px', fontSize: 10 }} onClick={(e) => { e.stopPropagation(); setShowTargetModal(s.id); setTargetError(null); }}>
                          <Plus s={10} />Add target
                        </button>
                      )}
                    </div>
                    {/* Expanded target list when this scope is selected — lets you pause/delete individual targets. */}
                    {isSelected && scopeTargets.length > 0 && (
                      <div style={{ marginTop: 8, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {scopeTargets.map((t) => {
                          const tPaused = t.active === false;
                          return (
                            <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, padding: '4px 6px', background: 'var(--bg-elev)', borderRadius: 4, opacity: tPaused ? 0.6 : 1 }}>
                              <span className="mono" style={{ color: 'var(--text-4)', minWidth: 56 }}>{t.type}</span>
                              <span className="mono" style={{ flex: 1, color: 'var(--text-2)', wordBreak: 'break-all' }}>{t.value}</span>
                              {tPaused && <span className="badge mute" style={{ fontSize: 9 }}>paused</span>}
                              <button className="btn sm" style={{ padding: '1px 5px' }}
                                      title={tPaused ? 'Resume target' : 'Pause target'}
                                      onClick={(e) => { e.stopPropagation(); toggleTarget(t); }}>
                                {tPaused ? <Play s={10} /> : <Pause s={10} />}
                              </button>
                              {!isAutoSync && (
                                <button className="btn sm" style={{ padding: '1px 5px' }} title="Delete target"
                                        onClick={(e) => { e.stopPropagation(); deleteTarget(t); }}>
                                  <Trash s={10} />
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {/* Compact chip list when NOT selected — first 6 targets only */}
                    {!isSelected && scopeTargets.length > 0 && (
                      <div style={{ marginTop: 6, paddingLeft: 20, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {scopeTargets.slice(0, 6).map((t) => (
                          <span key={t.id} className="tag" style={{ fontSize: 10, opacity: t.active === false ? 0.5 : 1 }}>
                            <span className="mono" style={{ color: 'var(--text-4)', marginRight: 3 }}>{t.type}</span>{t.value}
                          </span>
                        ))}
                        {scopeTargets.length > 6 && <span className="tag">+{scopeTargets.length - 6}</span>}
                      </div>
                    )}
                  </div>
                );
              })
            )}
            </div>
          </div>

          {/* Findings — independent vertical scroll */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
            <div className="card-h" style={{ flexShrink: 0 }}>
              <AlertTriangle s={13} />
              <div className="t">Findings</div>
              <div className="s">{findings.length}{selectedScope ? ' (filtered)' : ''}</div>
              <div className="right">
                {selectedScope && (
                  <button className="btn sm" onClick={() => setSelectedScope(null)}>Show all</button>
                )}
              </div>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            {loadingFindings ? (
              <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>Loading findings…</div>
            ) : findings.length === 0 ? (
              <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                {selectedScope ? 'No findings for this scope yet.' : 'No findings recorded. Trigger a scan to start discovery.'}
              </div>
            ) : (
              <table className="tbl">
                <thead><tr>
                  <th style={{ width: 100 }}>Severity</th>
                  <th style={{ width: 180 }}>Type</th>
                  <th>Value</th>
                  <th style={{ width: 110 }}>Source</th>
                  <th style={{ width: 140 }}>Discovered</th>
                </tr></thead>
                <tbody>
                  {findings.map((f) => {
                    const sev = severityFromType(f.type);
                    return (
                      <tr key={f.id} style={{ cursor: 'pointer' }}>
                        <td><span className={`badge ${sev}`}>{sevLabel(sev)}</span></td>
                        <td className="mono" style={{ fontSize: 11 }}>{f.type}</td>
                        <td className="primary mono" style={{ fontSize: 11.5 }}>{f.value}</td>
                        <td><span className="tag">{f.source}</span></td>
                        <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>{fmtDate(f.discovered_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
            </div>
          </div>
        </div>
      )}

      {/* New scope modal */}
      {showScopeModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 480, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Layers s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>New ASM scope</div>
              <button className="btn sm" onClick={() => setShowScopeModal(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1 }}>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Scope name *</label>
                <input className="input" value={scopeForm.name} onChange={(e) => setScopeForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. external-banking-perimeter" style={{ width: '100%' }} autoFocus />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Description</label>
                <textarea className="input" rows={3} value={scopeForm.description} onChange={(e) => setScopeForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="What this scope covers" style={{ width: '100%', resize: 'vertical', boxSizing: 'border-box' }} />
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-4)' }}>
                After creating the scope, add targets (domains / IPs / CIDRs / ASNs) using the
                &ldquo;Add target&rdquo; button on the scope row.
              </div>
              {scopeError && <div style={{ padding: '6px 10px', background: 'rgba(248,81,73,0.08)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>{scopeError}</div>}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowScopeModal(false)}>Cancel</button>
              <button className="btn primary" onClick={createScope} disabled={savingScope || !scopeForm.name.trim()}>
                {savingScope ? <><Refresh s={11} />Creating…</> : <><Plus s={11} />Create scope</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add target modal */}
      {showTargetModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 480, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Plus s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Add target to scope</div>
              <button className="btn sm" onClick={() => setShowTargetModal(null)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto', flex: 1 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Type</label>
                  <select className="select" value={targetForm.type} onChange={(e) => setTargetForm((f) => ({ ...f, type: e.target.value }))} style={{ width: '100%' }}>
                    {TARGET_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Value *</label>
                  <input className="input mono" value={targetForm.value} onChange={(e) => setTargetForm((f) => ({ ...f, value: e.target.value }))}
                    placeholder="e.g. example.com" style={{ width: '100%', fontSize: 12 }} autoFocus />
                </div>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Description</label>
                <input className="input" value={targetForm.description} onChange={(e) => setTargetForm((f) => ({ ...f, description: e.target.value }))} style={{ width: '100%' }} />
              </div>
              {targetError && <div style={{ padding: '6px 10px', background: 'rgba(248,81,73,0.08)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>{targetError}</div>}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowTargetModal(null)}>Cancel</button>
              <button className="btn primary" onClick={createTarget} disabled={savingTarget || !targetForm.value.trim()}>
                {savingTarget ? <><Refresh s={11} />Adding…</> : <><Plus s={11} />Add target</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
