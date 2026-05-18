'use client';

import React, { useCallback, useState } from 'react';
import { GitBranch, Brain, Plus, More, Refresh, X, AlertTriangle, Check } from '@/components/icons';
import { usePolicies } from '@/lib/hooks';
import { api } from '@/lib/api';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface PolicyDecision {
  mode: string;
  actions: string[];
  cmdb_filter: boolean;
  policy_id: string | null;
  scope: string;
}

function modeBadge(m: string) {
  if (m === 'full_auto')     return <span className="badge low">full_auto</span>;
  if (m === 'category_auto') return <span className="badge high">category_auto</span>;
  return <span className="badge med">on_demand</span>;
}

const ACTION_CHOICES = [
  'extract_iocs',
  'map_ttps',
  'hunting_hypothesis',
  'check_kev_exploited',
  'actor_likelihood',
  'cve_relevance',
  'correlation',
  'brief',
  'flowviz',
];

const RESOURCE_TYPES = ['article', 'cve', 'threat', 'ioc', 'actor'];
const SCOPES = ['global', 'category', 'resource'];
const MODES = ['full_auto', 'category_auto', 'on_demand'];

export default function PoliciesPage() {
  const { items, total, isLoading, mutate } = usePolicies();
  const activeCount = items.filter((p) => p.active).length;

  // New policy modal
  const [showNew, setShowNew]       = useState(false);
  const [saving, setSaving]         = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [form, setForm] = useState({
    scope: 'category',
    resource_type: 'article',
    category: '',
    mode: 'on_demand',
    actions: [] as string[],
    cmdb_filter: false,
    priority: 100,
    active: true,
  });

  // Simulate drawer
  const [showSim, setShowSim]               = useState(false);
  const [simResourceType, setSimResourceType] = useState('article');
  const [simResourceId, setSimResourceId]     = useState('');
  const [simRunning, setSimRunning]           = useState(false);
  const [simResult, setSimResult]             = useState<PolicyDecision | null>(null);
  const [simError, setSimError]               = useState<string | null>(null);

  const toggleAction = (a: string) => {
    setForm((f) => ({
      ...f,
      actions: f.actions.includes(a) ? f.actions.filter((x) => x !== a) : [...f.actions, a],
    }));
  };

  const createPolicy = useCallback(async () => {
    setSaving(true); setCreateError(null);
    try {
      const body: any = {
        scope: form.scope,
        mode: form.mode,
        actions: form.actions,
        cmdb_filter: form.cmdb_filter,
        priority: form.priority,
        active: form.active,
      };
      if (form.scope !== 'global') body.resource_type = form.resource_type;
      if (form.scope === 'category') body.category = form.category.trim() || null;
      await api.post('/policies', body);
      setShowNew(false);
      setForm({
        scope: 'category', resource_type: 'article', category: '',
        mode: 'on_demand', actions: [], cmdb_filter: false, priority: 100, active: true,
      });
      mutate();
    } catch (e) { setCreateError(String(e)); }
    finally { setSaving(false); }
  }, [form, mutate]);

  const togglePolicyActive = useCallback(async (id: string, current: boolean) => {
    try {
      await api.patch(`/policies/${id}`, { active: !current });
      mutate();
    } catch (e) { alert(String(e)); }
  }, [mutate]);

  const deletePolicy = useCallback(async (id: string) => {
    if (!confirm('Delete this policy? The global default policy cannot be deleted (deactivate instead).')) return;
    try {
      await api.delete(`/policies/${id}`);
      mutate();
    } catch (e) { alert(String(e)); }
  }, [mutate]);

  const runSimulate = useCallback(async () => {
    if (!simResourceId.trim()) { setSimError('Resource ID required'); return; }
    setSimRunning(true); setSimError(null); setSimResult(null);
    try {
      const res = await api.get<PolicyDecision>('/policies/decide', {
        resource_type: simResourceType,
        resource_id: simResourceId.trim(),
      });
      setSimResult(res);
    } catch (e) { setSimError(String(e)); }
    finally { setSimRunning(false); }
  }, [simResourceType, simResourceId]);

  return (
    <div style={{ padding: 14, height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>AI Policies</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading...' : `${total} policies · ${activeCount} active`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn primary" onClick={() => { setCreateError(null); setShowNew(true); }}><Plus s={12} />New policy</button>
        </div>
      </div>

      <div className="card">
        <div className="card-h"><GitBranch s={13} /><div className="t">Active policies</div></div>
        <div style={{ overflow: 'auto' }}>
          <table className="tbl">
            <thead><tr>
              <th style={{ width: 50 }}>Prio</th>
              <th style={{ width: 110 }}>Scope</th>
              <th style={{ width: 110 }}>Resource</th>
              <th>Category</th>
              <th style={{ width: 130 }}>Mode</th>
              <th>Actions</th>
              <th style={{ width: 70 }}>Active</th>
              <th style={{ width: 60 }}></th>
            </tr></thead>
            <tbody>
              {isLoading && <tr><td colSpan={8} style={{ padding: 20, color: 'var(--text-4)' }}>Loading policies...</td></tr>}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={8} style={{ padding: 20, color: 'var(--text-4)' }}>No policies yet. A default global policy will be seeded on first analysis cycle.</td></tr>
              )}
              {items.map((p) => (
                <tr key={p.id}>
                  <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>P{p.priority}</td>
                  <td><span className="tag">{p.scope}</span></td>
                  <td className="mono" style={{ fontSize: 11.5 }}>{p.resource_type}</td>
                  <td className="primary">{p.category ?? '—'}</td>
                  <td>{modeBadge(p.mode)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                      {p.actions.length === 0 ? <span style={{ fontSize: 11, color: 'var(--text-4)' }}>—</span> : p.actions.map((a) => <span key={a} className="tag">{a}</span>)}
                    </div>
                  </td>
                  <td>
                    <button onClick={() => togglePolicyActive(p.id, p.active)} style={{ all: 'unset', cursor: 'pointer' }} title={p.active ? 'Deactivate policy' : 'Activate policy'}>
                      <div style={{ position: 'relative', width: 32, height: 18, borderRadius: 9, background: p.active ? 'var(--accent)' : 'var(--bg-elev2)', border: '1px solid var(--border)' }}>
                        <div style={{ position: 'absolute', top: 1, left: p.active ? 15 : 1, width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'all .2s' }} />
                      </div>
                    </button>
                  </td>
                  <td>
                    <button className="btn sm" style={{ padding: '2px 6px' }} onClick={() => deletePolicy(p.id)} title="Delete policy">
                      <X s={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* New policy modal */}
      {showNew && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 640, maxHeight: '90vh', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <GitBranch s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>New AI policy</div>
              <button className="btn sm" onClick={() => setShowNew(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Scope</label>
                  <select className="select" value={form.scope} onChange={(e) => setForm((f) => ({ ...f, scope: e.target.value }))} style={{ width: '100%' }}>
                    {SCOPES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Priority</label>
                  <input type="number" className="input mono" value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: parseInt(e.target.value || '100') }))} style={{ width: '100%' }} />
                </div>
              </div>

              {form.scope !== 'global' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Resource type</label>
                    <select className="select" value={form.resource_type} onChange={(e) => setForm((f) => ({ ...f, resource_type: e.target.value }))} style={{ width: '100%' }}>
                      {RESOURCE_TYPES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
                  {form.scope === 'category' && (
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Category</label>
                      <input className="input mono" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} placeholder="e.g. ransomware, supply_chain" style={{ width: '100%', fontSize: 12 }} />
                    </div>
                  )}
                </div>
              )}

              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Mode</label>
                <select className="select" value={form.mode} onChange={(e) => setForm((f) => ({ ...f, mode: e.target.value }))} style={{ width: '100%' }}>
                  {MODES.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
                <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
                  <span className="mono">full_auto</span>: every item is processed automatically.{' '}
                  <span className="mono">category_auto</span>: only items in this category.{' '}
                  <span className="mono">on_demand</span>: never automatic — analyst clicks &quot;Analyze&quot;.
                </div>
              </div>

              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 6 }}>
                  Actions <span style={{ color: 'var(--text-4)' }}>({form.actions.length} selected)</span>
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {ACTION_CHOICES.map((a) => {
                    const on = form.actions.includes(a);
                    return (
                      <button key={a} className="tag"
                        style={{
                          cursor: 'pointer', padding: '4px 10px', fontSize: 11,
                          background: on ? 'var(--accent-bg)' : 'var(--bg-elev)',
                          border: on ? '1px solid var(--accent)' : '1px solid var(--border)',
                          color: on ? 'var(--accent)' : 'var(--text-3)',
                        }}
                        onClick={() => toggleAction(a)}>
                        {a}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 18, alignItems: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--text-3)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={form.cmdb_filter} onChange={(e) => setForm((f) => ({ ...f, cmdb_filter: e.target.checked }))} />
                  Only run if CMDB filter matches
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--text-3)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={form.active} onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))} />
                  Active
                </label>
              </div>

              {createError && (
                <div style={{ padding: '8px 10px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>
                  <AlertTriangle s={11} style={{ marginRight: 4 }} />{createError}
                </div>
              )}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowNew(false)}>Cancel</button>
              <button className="btn primary" onClick={createPolicy} disabled={saving}>
                {saving ? <><Refresh s={11} />Creating…</> : <><Plus s={11} />Create policy</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Simulate drawer */}
      {showSim && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 560, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Brain s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Simulate policy decision</div>
              <button className="btn sm" onClick={() => setShowSim(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto', flex: 1 }}>
              <div style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                Enter a real resource ID and we&apos;ll show you which policy would currently win for it,
                what mode it would run in, and which actions would fire. Useful for verifying a new
                policy before activating it.
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Resource type</label>
                  <select className="select" value={simResourceType} onChange={(e) => setSimResourceType(e.target.value)} style={{ width: '100%' }}>
                    {RESOURCE_TYPES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Resource ID</label>
                  <input className="input mono" value={simResourceId} onChange={(e) => setSimResourceId(e.target.value)}
                    placeholder="UUID or CVE-ID" style={{ width: '100%', fontSize: 12 }} autoFocus />
                </div>
              </div>

              {simError && (
                <div style={{ padding: '8px 10px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>
                  <AlertTriangle s={11} style={{ marginRight: 4 }} />{simError}
                </div>
              )}

              {simResult && (
                <div style={{ padding: '12px 14px', background: 'var(--bg-page)', border: '1px solid var(--border)', borderRadius: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                    <Check s={12} style={{ color: '#3fb950' }} />
                    <span style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 600 }}>Decision resolved</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '6px 12px', fontSize: 12 }}>
                    <span style={{ color: 'var(--text-4)' }}>Winning scope:</span>
                    <span className="tag" style={{ width: 'fit-content' }}>{simResult.scope}</span>
                    <span style={{ color: 'var(--text-4)' }}>Mode:</span>
                    <span>{modeBadge(simResult.mode)}</span>
                    <span style={{ color: 'var(--text-4)' }}>CMDB filter:</span>
                    <span className="mono" style={{ color: simResult.cmdb_filter ? '#3fb950' : 'var(--text-4)' }}>{String(simResult.cmdb_filter)}</span>
                    <span style={{ color: 'var(--text-4)' }}>Actions:</span>
                    <span style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {simResult.actions.length === 0 ? <span style={{ color: 'var(--text-4)' }}>none</span> : simResult.actions.map((a) => <span key={a} className="tag">{a}</span>)}
                    </span>
                    <span style={{ color: 'var(--text-4)' }}>Policy ID:</span>
                    <span className="mono" style={{ fontSize: 11 }}>{simResult.policy_id ?? '— (default)'}</span>
                  </div>
                </div>
              )}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowSim(false)}>Close</button>
              <button className="btn primary" onClick={runSimulate} disabled={simRunning || !simResourceId.trim()}>
                {simRunning ? <><Refresh s={11} style={{ animation: 'spin 1s linear infinite' }} />Resolving…</> : <><Brain s={11} />Run simulate</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
