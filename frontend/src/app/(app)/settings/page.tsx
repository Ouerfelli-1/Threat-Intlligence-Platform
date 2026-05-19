'use client';

import React, { useCallback, useMemo, useState } from 'react';
import useSWR from 'swr';
import { fetcher, api } from '@/lib/api';
import {
  Refresh, Plus, X, Play, Check, AlertTriangle, ExternalLink, Trash,
  Settings as SettingsIcon, Crosshair, MessageSquare,
} from '@/components/icons';

/* eslint-disable @typescript-eslint/no-explicit-any */

/* --------------------------------------------------------------------------- */
/* Types                                                                       */
/* --------------------------------------------------------------------------- */

interface Feed {
  id: string;
  name: string;
  url: string;
  kind: string;
  active: boolean;
  reliability: number;
  tags: string[];
  added_at: string;
  last_pulled_at: string | null;
}

interface TagDef {
  id: string;
  name: string;
  description: string | null;
  color: string | null;
  scopes: string[];
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

const TAG_SCOPES = ['ioc', 'asset', 'feed', 'actor', 'threat', 'article', 'cve'] as const;
const TAG_COLORS = ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#a371f7', '#f0883e', '#8b949e'];

/* --------------------------------------------------------------------------- */
/* Page                                                                        */
/* --------------------------------------------------------------------------- */

type TabKey = 'feeds' | 'tags' | 'ai' | 'notifications';

const TAB_LABELS: Record<TabKey, string> = {
  feeds:         'RSS Feeds',
  tags:          'Tag catalog',
  ai:            'AI providers',
  notifications: 'Notifications',
};

export default function SettingsPage() {
  const [tab, setTab] = useState<TabKey>('feeds');

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <SettingsIcon s={16} style={{ marginRight: 8 }} />
        <div style={{ fontSize: 18, fontWeight: 600 }}>Settings</div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 12, borderBottom: '1px solid var(--border)' }}>
        {(Object.keys(TAB_LABELS) as TabKey[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              all: 'unset',
              cursor: 'pointer',
              padding: '8px 18px',
              fontSize: 13,
              fontWeight: tab === t ? 600 : 400,
              color: tab === t ? 'var(--text)' : 'var(--text-3)',
              borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {tab === 'ai' && <AIProvidersTab />}
        {tab === 'feeds' && <FeedsTab />}
        {tab === 'tags'  && <TagsTab />}
        {tab === 'notifications' && <NotificationsTab />}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* Notifications tab                                                           */
/* --------------------------------------------------------------------------- */

interface NotificationRule {
  id: string;
  name: string;
  event_type: string;
  channel: string;
  target: string;
  filter: Record<string, unknown>;
  active: boolean;
  created_at: string;
  updated_at: string;
}

interface NotificationDispatch {
  id: string;
  rule_id: string | null;
  event_type: string;
  event_ref: string | null;
  channel: string;
  target: string;
  status: string;
  error: string | null;
  payload: Record<string, unknown>;
  sent_at: string;
}

const EVENT_TYPES = [
  { value: 'domainwatch.change',  label: 'Domain change (DNS / content / cert)' },
  { value: 'cve.exploited',       label: 'CVE exploited in the wild (CISA KEV)' },
  { value: 'threat.supply_chain', label: 'New supply-chain attack detected' },
] as const;

function NotificationsTab() {
  const { data: rules, mutate: mutRules } = useSWR<NotificationRule[]>(
    '/notifications/rules', fetcher, { revalidateOnFocus: false });
  const { data: dispatches } = useSWR<NotificationDispatch[]>(
    '/notifications/dispatches?limit=20', fetcher, { refreshInterval: 30_000 });

  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({
    name:       '',
    event_type: 'domainwatch.change',
    target:     '',
    severity_min: '',     // optional severity floor for cve.exploited
    product_match: false, // only fire if product is in CMDB profile
  });
  const [saving, setSaving] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);

  const [testTo, setTestTo] = useState('');
  const [testEvt, setTestEvt] = useState<string>('domainwatch.change');
  const [testing, setTesting] = useState(false);
  const [testMsg, setTestMsg] = useState<{ ok: boolean; msg: string } | null>(null);

  const createRule = useCallback(async () => {
    setSaving(true); setCreateErr(null);
    try {
      const filter: Record<string, unknown> = {};
      if (form.severity_min)  filter.severity_min  = form.severity_min;
      if (form.product_match) filter.product_match = true;
      await api.post('/notifications/rules', {
        name: form.name.trim() || `${form.event_type} -> ${form.target}`,
        event_type: form.event_type,
        channel: 'smtp',
        target: form.target.trim(),
        filter,
        active: true,
      });
      setShowNew(false);
      setForm({ name: '', event_type: 'domainwatch.change', target: '', severity_min: '', product_match: false });
      mutRules();
    } catch (e) {
      setCreateErr(String(e));
    } finally {
      setSaving(false);
    }
  }, [form, mutRules]);

  const toggleRule = useCallback(async (r: NotificationRule) => {
    await api.patch(`/notifications/rules/${r.id}`, { active: !r.active });
    mutRules();
  }, [mutRules]);

  const removeRule = useCallback(async (r: NotificationRule) => {
    if (!confirm(`Delete rule "${r.name}"?`)) return;
    await api.delete(`/notifications/rules/${r.id}`);
    mutRules();
  }, [mutRules]);

  const sendTest = useCallback(async () => {
    if (!testTo.trim()) return;
    setTesting(true); setTestMsg(null);
    try {
      const res = await api.post<{ sent?: number; failed?: number; error?: string | null }>(
        '/notifications/test',
        { event_type: testEvt, target: testTo.trim() },
      );
      if (res.sent) setTestMsg({ ok: true, msg: `Sent to ${testTo} (check inbox)` });
      else          setTestMsg({ ok: false, msg: res.error || 'Send failed' });
    } catch (e) {
      setTestMsg({ ok: false, msg: String(e) });
    } finally {
      setTesting(false);
    }
  }, [testTo, testEvt]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <MessageSquare s={14} />
        <div style={{ fontSize: 13.5, color: 'var(--text-2)' }}>
          Email alerts for platform events. Configure SMTP credentials in the Secrets vault
          (<span className="mono">SMTP_HOST</span>, <span className="mono">SMTP_PORT</span>,
          <span className="mono"> SMTP_USER</span>, <span className="mono">SMTP_PASS</span>,
          <span className="mono"> SMTP_FROM</span>) then add rules below.
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button className="btn primary sm" onClick={() => setShowNew(true)}>
            <Plus s={12} /> New rule
          </button>
        </div>
      </div>

      {/* Send-test card */}
      <div className="card" style={{ padding: 14 }}>
        <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
          Send test email
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select className="select" value={testEvt} onChange={(e) => setTestEvt(e.target.value)}>
            {EVENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <input className="input" placeholder="you@example.com"
                 value={testTo} onChange={(e) => setTestTo(e.target.value)}
                 style={{ flex: 1, minWidth: 200 }} />
          <button className="btn primary sm" onClick={sendTest} disabled={testing || !testTo.trim()}>
            {testing ? <><Refresh s={11} /> Sending…</> : <><Play s={11} /> Send test</>}
          </button>
        </div>
        {testMsg && (
          <div style={{
            marginTop: 10, padding: '6px 10px',
            background: testMsg.ok ? 'rgba(63,185,80,0.08)' : 'rgba(248,81,73,0.08)',
            border: testMsg.ok ? '1px solid rgba(63,185,80,0.3)' : '1px solid rgba(248,81,73,0.3)',
            color: testMsg.ok ? '#3fb950' : '#f85149',
            borderRadius: 4, fontSize: 12,
          }}>
            {testMsg.ok ? <Check s={10} /> : <AlertTriangle s={10} />} {testMsg.msg}
          </div>
        )}
      </div>

      {/* Rules table */}
      <div className="card">
        <div className="card-h"><MessageSquare s={13} />
          <div className="t">Active rules</div>
          <div className="s">{rules?.length ?? 0}</div>
        </div>
        <div className="card-b flush" style={{ overflow: 'auto' }}>
          {!rules && <div style={{ padding: 14, fontSize: 12, color: 'var(--text-4)' }}>Loading…</div>}
          {rules && rules.length === 0 && (
            <div style={{ padding: 20, fontSize: 12, color: 'var(--text-4)', textAlign: 'center' }}>
              No notification rules yet. Click <strong>New rule</strong> to create one.
            </div>
          )}
          {rules && rules.length > 0 && (
            <table className="tbl">
              <thead><tr>
                <th style={{ width: 36 }}></th>
                <th>Name</th>
                <th style={{ width: 200 }}>Event</th>
                <th style={{ width: 220 }}>Target</th>
                <th style={{ width: 180 }}>Filter</th>
                <th style={{ width: 50 }}></th>
              </tr></thead>
              <tbody>
                {rules.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <button onClick={() => toggleRule(r)}
                              style={{ all: 'unset', cursor: 'pointer' }}
                              title={r.active ? 'Pause this rule' : 'Resume'}>
                        <span className="dot" style={{ background: r.active ? '#3fb950' : 'var(--text-mute)' }} />
                      </button>
                    </td>
                    <td style={{ fontSize: 12.5 }}>{r.name}</td>
                    <td><span className="tag" style={{ fontSize: 10 }}>{r.event_type}</span></td>
                    <td className="mono" style={{ fontSize: 11.5 }}>{r.target}</td>
                    <td style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      {Object.keys(r.filter || {}).length === 0
                        ? <span style={{ color: 'var(--text-4)' }}>(none)</span>
                        : Object.entries(r.filter).map(([k, v]) => (
                            <span key={k} className="mono" style={{ marginRight: 6 }}>{k}={String(v)}</span>
                          ))}
                    </td>
                    <td>
                      <button className="btn sm" style={{ padding: '2px 6px' }}
                              onClick={() => removeRule(r)} title="Delete">
                        <Trash s={10} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Recent dispatches */}
      <div className="card">
        <div className="card-h"><MessageSquare s={13} />
          <div className="t">Recent dispatches</div>
          <div className="s">last 20 · auto-refreshes</div>
        </div>
        <div className="card-b flush" style={{ overflow: 'auto', maxHeight: 360 }}>
          {(!dispatches || dispatches.length === 0) && (
            <div style={{ padding: 14, fontSize: 12, color: 'var(--text-4)' }}>
              Nothing dispatched yet. Wait for a triggering event, or send a test above.
            </div>
          )}
          {dispatches && dispatches.length > 0 && (
            <table className="tbl">
              <thead><tr>
                <th style={{ width: 80 }}>Status</th>
                <th style={{ width: 180 }}>Event</th>
                <th style={{ width: 220 }}>Target</th>
                <th>Ref / Error</th>
                <th style={{ width: 120 }}>When</th>
              </tr></thead>
              <tbody>
                {dispatches.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <span className={`badge ${d.status === 'sent' ? 'low' : d.status === 'failed' ? 'crit' : 'mute'}`}>
                        {d.status}
                      </span>
                    </td>
                    <td><span className="tag" style={{ fontSize: 10 }}>{d.event_type}</span></td>
                    <td className="mono" style={{ fontSize: 11 }}>{d.target}</td>
                    <td className="mono" style={{ fontSize: 10.5, color: d.error ? '#f85149' : 'var(--text-3)' }}>
                      {d.error ? d.error.slice(0, 80) : (d.event_ref || '')}
                    </td>
                    <td className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>
                      {new Date(d.sent_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* New rule modal — Modal renders its own Cancel + submit footer,
          we just supply the form body and the submit callback. */}
      {showNew && (
        <Modal
          title="New notification rule"
          onClose={() => setShowNew(false)}
          submit={{
            label: saving ? 'Saving…' : 'Create rule',
            icon: saving ? <Refresh s={11} /> : <Plus s={11} />,
            disabled: saving || !form.target.trim(),
            onClick: createRule,
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 11, color: 'var(--text-4)' }}>Name (optional)</label>
            <input className="input" placeholder="e.g. SOC ops mailing list"
                   value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />

            <label style={{ fontSize: 11, color: 'var(--text-4)' }}>Event type</label>
            <select className="select" value={form.event_type}
                    onChange={(e) => setForm(f => ({ ...f, event_type: e.target.value }))}>
              {EVENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>

            <label style={{ fontSize: 11, color: 'var(--text-4)' }}>Email target</label>
            <input className="input" placeholder="alerts@bank.example"
                   value={form.target} onChange={(e) => setForm(f => ({ ...f, target: e.target.value }))} />

            {/* Per-event filter options */}
            {form.event_type === 'cve.exploited' && (
              <>
                <label style={{ fontSize: 11, color: 'var(--text-4)' }}>Minimum severity (optional)</label>
                <select className="select" value={form.severity_min}
                        onChange={(e) => setForm(f => ({ ...f, severity_min: e.target.value }))}>
                  <option value="">any</option>
                  <option value="medium">medium and above</option>
                  <option value="high">high and above</option>
                  <option value="critical">critical only</option>
                </select>
                <label style={{ fontSize: 11, color: 'var(--text-4)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input type="checkbox" checked={form.product_match}
                         onChange={(e) => setForm(f => ({ ...f, product_match: e.target.checked }))} />
                  Only when the product is in our CMDB profile
                </label>
              </>
            )}

            {createErr && (
              <div style={{ padding: '6px 10px', background: 'rgba(248,81,73,0.08)',
                            border: '1px solid rgba(248,81,73,0.3)', borderRadius: 4,
                            color: '#f85149', fontSize: 11 }}>
                {createErr}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* RSS Feeds tab                                                               */
/* --------------------------------------------------------------------------- */

function fmtDate(iso: string | null): string {
  if (!iso) return 'never';
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function howLongAgo(iso: string | null): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60)  return `${m}m ago`;
  if (m < 1440) return `${Math.floor(m / 60)}h ago`;
  return `${Math.floor(m / 1440)}d ago`;
}

function FeedsTab() {
  const { data: feeds = [], isLoading, mutate } = useSWR<Feed[]>('/feeds', fetcher);

  const [triggering, setTriggering] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', url: '', kind: 'rss', reliability: 0.7, active: true });

  const [editing, setEditing] = useState<Feed | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: '', url: '', reliability: 0.7, active: true });

  // Tags assigned per feed are managed inline via TagPicker (separate from form modal)
  const [feedTagsDraft, setFeedTagsDraft] = useState<Record<string, string[]>>({});

  const triggerIngest = useCallback(async () => {
    setTriggering(true);
    try {
      await api.post('/jobs/news_pull/trigger', {});
      setTimeout(() => { mutate(); setTriggering(false); }, 6000);
    } catch (e) { setTriggering(false); alert(String(e)); }
  }, [mutate]);

  const submitCreate = useCallback(async () => {
    if (!form.name.trim() || !form.url.trim()) { setCreateError('Name and URL are required'); return; }
    setCreating(true); setCreateError(null);
    try {
      await api.post('/feeds', {
        name: form.name.trim(),
        url: form.url.trim(),
        kind: form.kind || 'rss',
        reliability: form.reliability,
        active: form.active,
        tags: [],
      });
      setShowNew(false);
      setForm({ name: '', url: '', kind: 'rss', reliability: 0.7, active: true });
      mutate();
    } catch (e) { setCreateError(String(e)); }
    finally { setCreating(false); }
  }, [form, mutate]);

  const openEdit = useCallback((feed: Feed) => {
    setEditing(feed);
    setEditError(null);
    setEditForm({ name: feed.name, url: feed.url, reliability: feed.reliability, active: feed.active });
  }, []);

  const submitEdit = useCallback(async () => {
    if (!editing) return;
    setSavingEdit(true); setEditError(null);
    try {
      await api.patch(`/feeds/${editing.id}`, {
        name: editForm.name.trim(),
        url: editForm.url.trim(),
        reliability: editForm.reliability,
        active: editForm.active,
      });
      setEditing(null);
      mutate();
    } catch (e) { setEditError(String(e)); }
    finally { setSavingEdit(false); }
  }, [editing, editForm, mutate]);

  const toggleActive = useCallback(async (feed: Feed) => {
    try {
      await api.patch(`/feeds/${feed.id}`, { active: !feed.active });
      mutate();
    } catch (e) { alert(String(e)); }
  }, [mutate]);

  const removeFeed = useCallback(async (feed: Feed) => {
    if (!confirm(`Delete RSS feed "${feed.name}"? Existing articles stay; future pulls stop.`)) return;
    try { await api.delete(`/feeds/${feed.id}`); mutate(); }
    catch (e) { alert(String(e)); }
  }, [mutate]);

  const saveFeedTags = useCallback(async (feed: Feed, newTags: string[]) => {
    try {
      await api.patch(`/feeds/${feed.id}`, { tags: newTags });
      setFeedTagsDraft((d) => { const { [feed.id]: _, ...rest } = d; return rest; });
      mutate();
    } catch (e) { alert(String(e)); }
  }, [mutate]);

  const activeCount = feeds.filter((f) => f.active).length;
  const stoppedCount = feeds.length - activeCount;

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ color: 'var(--text-4)', fontSize: 12 }}>
          {isLoading ? 'loading…' : `${feeds.length} configured · ${activeCount} active · ${stoppedCount} stopped · pulled every 10 min`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn" onClick={triggerIngest} disabled={triggering}>
            {triggering ? <Refresh s={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Play s={12} />}
            {triggering ? 'Pulling…' : 'Pull now'}
          </button>
          <button className="btn primary" onClick={() => { setCreateError(null); setShowNew(true); }}>
            <Plus s={12} />Add feed
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 10, padding: '10px 14px', fontSize: 12, color: 'var(--text-3)' }}>
        Feed tags come from the catalog (Tags tab) and apply with <em>feed</em> scope. They are merged into every
        article ingested from that feed in addition to per-article keyword tags.
      </div>

      <div className="card" style={{ overflow: 'auto' }}>
        <table className="tbl">
          <thead><tr>
            <th>Name</th>
            <th>URL</th>
            <th style={{ width: 90 }}>Kind</th>
            <th style={{ width: 90 }}>Reliability</th>
            <th style={{ width: 320 }}>Tags (admin catalog)</th>
            <th style={{ width: 110 }}>Last pulled</th>
            <th style={{ width: 80 }}>Active</th>
            <th style={{ width: 110 }}>Actions</th>
          </tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={8} style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>Loading feeds…</td></tr>}
            {!isLoading && feeds.length === 0 && (
              <tr><td colSpan={8} style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>
                No feeds configured. Click <strong>Add feed</strong> to register one.
              </td></tr>
            )}
            {(feeds as Feed[]).map((f) => {
              const draftedTags = feedTagsDraft[f.id] ?? f.tags ?? [];
              const dirty = JSON.stringify(draftedTags) !== JSON.stringify(f.tags ?? []);
              return (
                <tr key={f.id}>
                  <td className="primary mono" style={{ fontSize: 12, fontWeight: 500 }}>{f.name}</td>
                  <td className="mono" style={{ fontSize: 11 }}>
                    <a href={f.url} target="_blank" rel="noreferrer" style={{ color: 'var(--text-3)', textDecoration: 'none' }}>
                      {f.url.length > 56 ? `${f.url.slice(0, 56)}…` : f.url} <ExternalLink s={10} />
                    </a>
                  </td>
                  <td><span className="tag">{f.kind}</span></td>
                  <td className="mono" style={{ fontSize: 11 }}>{f.reliability.toFixed(2)}</td>
                  <td>
                    <FeedTagEditor
                      currentTags={draftedTags}
                      onChange={(next) => setFeedTagsDraft((d) => ({ ...d, [f.id]: next }))}
                    />
                    {dirty && (
                      <div style={{ marginTop: 4, display: 'flex', gap: 4 }}>
                        <button className="btn sm primary" style={{ fontSize: 10 }} onClick={() => saveFeedTags(f, draftedTags)}>
                          <Check s={10} />Save
                        </button>
                        <button
                          className="btn sm"
                          style={{ fontSize: 10 }}
                          onClick={() => setFeedTagsDraft((d) => { const { [f.id]: _, ...rest } = d; return rest; })}
                        >Cancel</button>
                      </div>
                    )}
                  </td>
                  <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>
                    {f.last_pulled_at ? howLongAgo(f.last_pulled_at) : <span style={{ color: '#d29922' }}>never</span>}
                  </td>
                  <td>
                    <button onClick={() => toggleActive(f)} style={{ all: 'unset', cursor: 'pointer' }}
                      title={f.active ? 'Stop pulling this feed' : 'Resume pulling'}>
                      <div style={{ position: 'relative', width: 32, height: 18, borderRadius: 9, background: f.active ? 'var(--accent)' : 'var(--bg-elev2)', border: '1px solid var(--border)' }}>
                        <div style={{ position: 'absolute', top: 1, left: f.active ? 15 : 1, width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'all .2s' }} />
                      </div>
                    </button>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn sm" style={{ padding: '2px 6px', fontSize: 10 }} onClick={() => openEdit(f)}>Edit</button>
                      <button className="btn sm" style={{ padding: '2px 6px' }} onClick={() => removeFeed(f)} title="Delete feed">
                        <Trash s={11} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Add feed modal */}
      {showNew && (
        <Modal title="Add RSS feed" onClose={() => setShowNew(false)}
          submit={{
            label: creating ? 'Adding…' : 'Add feed', icon: creating ? <Refresh s={11} /> : <Plus s={11} />,
            disabled: creating || !form.name.trim() || !form.url.trim(),
            onClick: submitCreate,
          }}>
          <Field label="Name *">
            <input className="input mono" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="e.g. krebsonsecurity" style={{ width: '100%', fontSize: 12 }} autoFocus />
          </Field>
          <Field label="Feed URL *">
            <input className="input mono" value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
              placeholder="https://example.com/feed.xml" style={{ width: '100%', fontSize: 12 }} />
          </Field>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px', gap: 12 }}>
            <Field label="Kind">
              <select className="select" value={form.kind} onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value }))} style={{ width: '100%' }}>
                <option value="rss">rss</option>
                <option value="atom">atom</option>
                <option value="json-feed">json-feed</option>
              </select>
            </Field>
            <Field label="Reliability">
              <input className="input mono" type="number" step="0.05" min="0" max="1" value={form.reliability}
                onChange={(e) => setForm((f) => ({ ...f, reliability: parseFloat(e.target.value) || 0 }))}
                style={{ width: '100%', fontSize: 12 }} />
            </Field>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-3)', cursor: 'pointer' }}>
            <input type="checkbox" checked={form.active} onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))} />
            Active — start pulling on next cycle
          </label>
          <div style={{ fontSize: 11, color: 'var(--text-4)' }}>
            Tags can be assigned to this feed after creation, using the catalog dropdown on the row.
          </div>
          {createError && <ErrorBanner>{createError}</ErrorBanner>}
        </Modal>
      )}

      {/* Edit feed modal */}
      {editing && (
        <Modal title={`Edit feed: ${editing.name}`} onClose={() => setEditing(null)}
          submit={{
            label: savingEdit ? 'Saving…' : 'Save changes', icon: savingEdit ? <Refresh s={11} /> : <Check s={11} />,
            disabled: savingEdit, onClick: submitEdit,
          }}>
          <Field label="Name">
            <input className="input mono" value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} style={{ width: '100%', fontSize: 12 }} />
          </Field>
          <Field label="Feed URL">
            <input className="input mono" value={editForm.url} onChange={(e) => setEditForm((f) => ({ ...f, url: e.target.value }))} style={{ width: '100%', fontSize: 12 }} />
          </Field>
          <Field label="Reliability">
            <input className="input mono" type="number" step="0.05" min="0" max="1" value={editForm.reliability}
              onChange={(e) => setEditForm((f) => ({ ...f, reliability: parseFloat(e.target.value) || 0 }))}
              style={{ width: 120, fontSize: 12 }} />
          </Field>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-3)', cursor: 'pointer' }}>
            <input type="checkbox" checked={editForm.active} onChange={(e) => setEditForm((f) => ({ ...f, active: e.target.checked }))} />
            Active
          </label>
          {editError && <ErrorBanner>{editError}</ErrorBanner>}
        </Modal>
      )}
    </>
  );
}

/* Inline tag editor for the feed row — uses TagPicker but dynamically imported
   to avoid circular imports and keep this file self-contained. */
import TagPicker from '@/components/shared/TagPicker';

function FeedTagEditor({ currentTags, onChange }: { currentTags: string[]; onChange: (next: string[]) => void }) {
  return <TagPicker scope="feed" value={currentTags} onChange={onChange} placeholder="No tags — click to pick from catalog" />;
}

/* --------------------------------------------------------------------------- */
/* Tag catalog tab                                                             */
/* --------------------------------------------------------------------------- */

function TagsTab() {
  const { data: tags = [], isLoading, mutate } = useSWR<TagDef[]>('/tags', fetcher);
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [form, setForm] = useState<{ name: string; description: string; color: string; scopes: string[] }>({
    name: '', description: '', color: '#58a6ff', scopes: [],
  });

  const [editing, setEditing] = useState<TagDef | null>(null);
  const [editForm, setEditForm] = useState<{ name: string; description: string; color: string; scopes: string[] }>({
    name: '', description: '', color: '#58a6ff', scopes: [],
  });
  const [editError, setEditError] = useState<string | null>(null);

  const [scopeFilter, setScopeFilter] = useState<string>('');

  const filtered = useMemo(() => {
    if (!scopeFilter) return tags;
    return tags.filter((t) => (t.scopes ?? []).includes(scopeFilter));
  }, [tags, scopeFilter]);

  const grouped = useMemo(() => {
    // Count tags per scope for the filter chips
    const map: Record<string, number> = {};
    for (const t of tags) for (const s of (t.scopes ?? [])) map[s] = (map[s] ?? 0) + 1;
    return map;
  }, [tags]);

  const submitCreate = useCallback(async () => {
    if (!form.name.trim()) { setCreateError('Tag name is required'); return; }
    if (form.scopes.length === 0) { setCreateError('Pick at least one scope'); return; }
    setSaving(true); setCreateError(null);
    try {
      await api.post('/tags', {
        name: form.name.trim().toLowerCase().replace(/\s+/g, '_'),
        description: form.description.trim() || null,
        color: form.color || null,
        scopes: form.scopes,
      });
      setShowNew(false);
      setForm({ name: '', description: '', color: '#58a6ff', scopes: [] });
      mutate();
    } catch (e) { setCreateError(String(e)); }
    finally { setSaving(false); }
  }, [form, mutate]);

  const openEdit = useCallback((t: TagDef) => {
    setEditing(t); setEditError(null);
    setEditForm({
      name: t.name, description: t.description ?? '', color: t.color ?? '#58a6ff', scopes: t.scopes ?? [],
    });
  }, []);

  const submitEdit = useCallback(async () => {
    if (!editing) return;
    if (editForm.scopes.length === 0) { setEditError('Pick at least one scope'); return; }
    setSaving(true); setEditError(null);
    try {
      await api.patch(`/tags/${editing.id}`, {
        name: editForm.name.trim().toLowerCase().replace(/\s+/g, '_'),
        description: editForm.description.trim() || null,
        color: editForm.color || null,
        scopes: editForm.scopes,
      });
      setEditing(null);
      mutate();
    } catch (e) { setEditError(String(e)); }
    finally { setSaving(false); }
  }, [editing, editForm, mutate]);

  const removeTag = useCallback(async (t: TagDef) => {
    if (!confirm(`Delete tag "${t.name}"? Existing items tagged with it will keep the label until manually cleaned up.`)) return;
    try { await api.delete(`/tags/${t.id}`); mutate(); }
    catch (e) { alert(String(e)); }
  }, [mutate]);

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ color: 'var(--text-4)', fontSize: 12 }}>
          {isLoading ? 'loading…' : `${tags.length} tag${tags.length === 1 ? '' : 's'} in catalog · scopes constrain where each tag is offered to analysts`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn primary" onClick={() => { setCreateError(null); setShowNew(true); }}>
            <Plus s={12} />New tag
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 10, padding: '10px 14px' }}>
        <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 8 }}>
          Filter by scope (which resource type a tag applies to):
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          <button
            onClick={() => setScopeFilter('')}
            className="tag"
            style={{
              cursor: 'pointer', padding: '3px 9px', fontSize: 11,
              background: scopeFilter === '' ? 'var(--accent-bg)' : 'var(--bg-elev)',
              color: scopeFilter === '' ? 'var(--accent)' : 'var(--text-3)',
              border: scopeFilter === '' ? '1px solid var(--accent)' : '1px solid var(--border)',
            }}
          >All ({tags.length})</button>
          {TAG_SCOPES.map((s) => (
            <button
              key={s}
              onClick={() => setScopeFilter(s)}
              className="tag"
              style={{
                cursor: 'pointer', padding: '3px 9px', fontSize: 11,
                background: scopeFilter === s ? 'var(--accent-bg)' : 'var(--bg-elev)',
                color: scopeFilter === s ? 'var(--accent)' : 'var(--text-3)',
                border: scopeFilter === s ? '1px solid var(--accent)' : '1px solid var(--border)',
              }}
            >{s} ({grouped[s] ?? 0})</button>
          ))}
        </div>
      </div>

      <div className="card" style={{ overflow: 'auto' }}>
        <table className="tbl">
          <thead><tr>
            <th style={{ width: 220 }}>Name</th>
            <th style={{ width: 50 }}>Color</th>
            <th>Description</th>
            <th>Applicable scopes</th>
            <th style={{ width: 130 }}>Created</th>
            <th style={{ width: 100 }}>Actions</th>
          </tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>Loading catalog…</td></tr>}
            {!isLoading && filtered.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>
                {scopeFilter ? `No tags applicable to scope "${scopeFilter}". Click New tag to add one.` : 'No tags yet. Click New tag to add one.'}
              </td></tr>
            )}
            {filtered.map((t) => (
              <tr key={t.id}>
                <td>
                  <span className="mono" style={{
                    fontSize: 12, padding: '2px 8px', borderRadius: 4,
                    background: `${t.color ?? '#8b949e'}1f`,
                    color: t.color ?? '#8b949e',
                    border: `1px solid ${t.color ?? '#8b949e'}4d`,
                  }}>{t.name}</span>
                </td>
                <td>
                  {t.color
                    ? <span className="mono" style={{ fontSize: 10, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ width: 12, height: 12, borderRadius: '50%', background: t.color, border: '1px solid var(--border)' }} />
                        {t.color}
                      </span>
                    : <span style={{ fontSize: 10, color: 'var(--text-4)' }}>—</span>}
                </td>
                <td style={{ fontSize: 12, color: 'var(--text-3)' }}>{t.description ?? '—'}</td>
                <td>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    {(t.scopes ?? []).map((s) => (
                      <span key={s} className="tag" style={{ fontSize: 10.5 }}>{s}</span>
                    ))}
                  </div>
                </td>
                <td className="mono" style={{ fontSize: 10.5, color: 'var(--text-4)' }}>
                  {t.created_by ?? '—'}<br />
                  {fmtDate(t.created_at)}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn sm" style={{ padding: '2px 6px', fontSize: 10 }} onClick={() => openEdit(t)}>Edit</button>
                    <button className="btn sm" style={{ padding: '2px 6px' }} onClick={() => removeTag(t)} title="Delete tag">
                      <Trash s={11} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* New tag modal */}
      {showNew && (
        <Modal title="New tag" onClose={() => setShowNew(false)}
          submit={{
            label: saving ? 'Creating…' : 'Create tag', icon: saving ? <Refresh s={11} /> : <Plus s={11} />,
            disabled: saving || !form.name.trim() || form.scopes.length === 0,
            onClick: submitCreate,
          }}>
          <TagFormBody value={form} onChange={setForm} />
          {createError && <ErrorBanner>{createError}</ErrorBanner>}
        </Modal>
      )}

      {/* Edit tag modal */}
      {editing && (
        <Modal title={`Edit tag: ${editing.name}`} onClose={() => setEditing(null)}
          submit={{
            label: saving ? 'Saving…' : 'Save', icon: saving ? <Refresh s={11} /> : <Check s={11} />,
            disabled: saving || editForm.scopes.length === 0,
            onClick: submitEdit,
          }}>
          <TagFormBody value={editForm} onChange={setEditForm} />
          {editError && <ErrorBanner>{editError}</ErrorBanner>}
        </Modal>
      )}
    </>
  );
}

function TagFormBody({
  value, onChange,
}: {
  value: { name: string; description: string; color: string; scopes: string[] };
  onChange: (next: { name: string; description: string; color: string; scopes: string[] }) => void;
}) {
  const toggleScope = (s: string) => {
    onChange({
      ...value,
      scopes: value.scopes.includes(s) ? value.scopes.filter((x) => x !== s) : [...value.scopes, s],
    });
  };

  return (
    <>
      <Field label="Tag name *">
        <input className="input mono" value={value.name} onChange={(e) => onChange({ ...value, name: e.target.value })}
          placeholder="lowercase_with_underscores" style={{ width: '100%', fontSize: 12 }} autoFocus />
        <div style={{ fontSize: 10.5, color: 'var(--text-4)', marginTop: 2 }}>
          Display name is normalized: spaces become underscores, letters lowercased.
        </div>
      </Field>
      <Field label="Description">
        <input className="input" value={value.description} onChange={(e) => onChange({ ...value, description: e.target.value })}
          placeholder="Optional — shown in tag-picker tooltips" style={{ width: '100%' }} />
      </Field>
      <Field label="Color">
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          {TAG_COLORS.map((c) => (
            <button key={c} onClick={() => onChange({ ...value, color: c })}
              style={{
                all: 'unset', cursor: 'pointer',
                width: 22, height: 22, borderRadius: '50%', background: c,
                border: value.color === c ? '2px solid var(--text)' : '2px solid transparent',
                boxShadow: value.color === c ? `0 0 0 2px ${c}` : 'none',
              }}
              title={c}
            />
          ))}
          <input
            type="text"
            className="input mono"
            value={value.color}
            onChange={(e) => onChange({ ...value, color: e.target.value })}
            placeholder="#58a6ff"
            style={{ width: 100, height: 28, fontSize: 11, marginLeft: 8 }}
          />
        </div>
      </Field>
      <Field label="Applicable scopes *">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {TAG_SCOPES.map((s) => {
            const on = value.scopes.includes(s);
            return (
              <button key={s} onClick={() => toggleScope(s)}
                className="tag"
                style={{
                  cursor: 'pointer', padding: '4px 10px', fontSize: 11,
                  background: on ? 'var(--accent-bg)' : 'var(--bg-elev)',
                  color: on ? 'var(--accent)' : 'var(--text-3)',
                  border: on ? '1px solid var(--accent)' : '1px solid var(--border)',
                }}
              >{s}</button>
            );
          })}
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--text-4)', marginTop: 4 }}>
          Tag will only appear in the picker on pages whose resource matches one of these scopes.
        </div>
      </Field>
    </>
  );
}

/* --------------------------------------------------------------------------- */
/* Shared UI primitives                                                        */
/* --------------------------------------------------------------------------- */

function Modal({
  title, children, onClose, submit,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  submit: { label: string; icon?: React.ReactNode; onClick: () => void; disabled?: boolean };
}) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)',
      display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 20,
    }}>
      <div style={{
        width: 580, maxHeight: '90vh', background: 'var(--bg-card)', border: '1px solid var(--border-strong)',
        borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Crosshair s={14} />
          <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>{title}</div>
          <button className="btn sm" onClick={onClose}><X s={12} /></button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1, minHeight: 0 }}>
          {children}
        </div>
        <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={submit.onClick} disabled={submit.disabled}>
            {submit.icon}{submit.label}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  );
}

function ErrorBanner({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      padding: '8px 10px', background: 'rgba(248,81,73,0.08)',
      border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6,
      color: '#f85149', fontSize: 11.5,
    }}>
      <AlertTriangle s={11} style={{ marginRight: 4 }} />{children}
    </div>
  );
}


/* --------------------------------------------------------------------------- */
/* AI Providers tab                                                            */
/*                                                                             */
/* Default is LiteLLM (multi-provider gateway). OpenRouter is kept as fallback.*/
/* Admin manages provider API keys here. Keys are encrypted at rest (Fernet)   */
/* in the secrets service; only an 8-char preview is ever returned to the      */
/* browser — full key material never leaves the backend.                       */
/* --------------------------------------------------------------------------- */

interface SecretPreview {
  name: string;
  version: number;
  preview: string;   // e.g. "sk-or-v1••••••••••••"
  length: number;
  updated_at: string;
}

const AI_KEY_CATALOG: Array<{ name: string; provider: string; help: string; sample: string; modelExamples?: string[] }> = [
  { name: 'GITHUB_API_KEY',     provider: 'GitHub Models',
    help: 'GitHub Personal Access Token with the models:read scope. Free tier of GitHub Models exposes GPT-4o, Llama 3.1, Phi-3.5, etc. via the Azure inference endpoint.',
    sample: 'github_pat_11ABC...',
    modelExamples: ['github/gpt-4o', 'github/gpt-4o-mini', 'github/Meta-Llama-3.1-70B-Instruct', 'github/Phi-3.5-MoE-instruct'],
  },
  { name: 'ANTHROPIC_API_KEY',  provider: 'Anthropic (Claude)',     help: 'Direct Anthropic API key. LiteLLM uses this for anthropic/* models.', sample: 'sk-ant-api03-...',
    modelExamples: ['anthropic/claude-3-5-haiku-20241022', 'anthropic/claude-3-5-sonnet-20241022', 'anthropic/claude-3-opus-20240229'] },
  { name: 'OPENAI_API_KEY',     provider: 'OpenAI',                  help: 'Direct OpenAI API key. LiteLLM uses this for openai/* models.',      sample: 'sk-proj-...',
    modelExamples: ['openai/gpt-4o', 'openai/gpt-4o-mini', 'openai/o1-mini'] },
  { name: 'GROQ_API_KEY',       provider: 'Groq',                    help: 'For groq/* models (very fast inference).',                          sample: 'gsk_...',
    modelExamples: ['groq/llama-3.1-70b-versatile', 'groq/mixtral-8x7b-32768'] },
  { name: 'GEMINI_API_KEY',     provider: 'Google Gemini',           help: 'For gemini/* models.',                                              sample: 'AIza...',
    modelExamples: ['gemini/gemini-1.5-pro', 'gemini/gemini-1.5-flash'] },
  { name: 'MISTRAL_API_KEY',    provider: 'Mistral',                 help: 'For mistral/* models.',                                             sample: '...',
    modelExamples: ['mistral/mistral-large-latest', 'mistral/mistral-small-latest'] },
  { name: 'DEEPSEEK_API_KEY',   provider: 'DeepSeek',                help: 'For deepseek/* models.',                                            sample: 'sk-...',
    modelExamples: ['deepseek/deepseek-chat', 'deepseek/deepseek-coder'] },
  { name: 'OPENROUTER_API_KEY', provider: 'OpenRouter (FALLBACK)',   help: 'Universal fallback. Routes any model id prefixed openrouter/<vendor>/<model>.', sample: 'sk-or-v1-...',
    modelExamples: ['openrouter/anthropic/claude-3-5-haiku', 'openrouter/openai/gpt-4o-mini'] },
];

// Common model identifier suggestions for the "Active model" selector.
// Each option ships its LiteLLM model id and a hint about which secret key
// must be set for it to work.
// Curated list of models the LiteLLM proxy knows how to route. Grouped by
// provider — the GitHub Models block is intentionally wide because the user
// reported "i can only select gpt-4o-mini" and the prior `<datalist>` only
// surfaced matches that started with the typed text. A real `<select>` now
// shows the full list at a glance.
const PRIMARY_MODEL_PRESETS: Array<{ label: string; value: string; needs: string }> = [
  // GitHub Models (free tier via PAT with `models:read` scope)
  { label: 'GitHub · gpt-4o',                            value: 'github/gpt-4o',                              needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · gpt-4o-mini',                       value: 'github/gpt-4o-mini',                         needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · gpt-4.1',                           value: 'github/gpt-4.1',                             needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · gpt-4.1-mini',                      value: 'github/gpt-4.1-mini',                        needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · o1-preview',                        value: 'github/o1-preview',                          needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · o1-mini',                           value: 'github/o1-mini',                             needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · Llama-3.1-405B-Instruct',           value: 'github/Meta-Llama-3.1-405B-Instruct',        needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · Llama-3.1-70B-Instruct',            value: 'github/Meta-Llama-3.1-70B-Instruct',         needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · Llama-3.1-8B-Instruct',             value: 'github/Meta-Llama-3.1-8B-Instruct',          needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · Mistral-large-2407',                value: 'github/Mistral-large-2407',                  needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · Mistral-Nemo',                      value: 'github/Mistral-Nemo',                        needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · Cohere-command-r-plus',             value: 'github/Cohere-command-r-plus',               needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · Phi-3.5-MoE-instruct',              value: 'github/Phi-3.5-MoE-instruct',                needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · Phi-3.5-mini-instruct',             value: 'github/Phi-3.5-mini-instruct',               needs: 'GITHUB_API_KEY' },
  { label: 'GitHub · AI21-Jamba-1.5-Large',              value: 'github/AI21-Jamba-1.5-Large',                needs: 'GITHUB_API_KEY' },
  // Direct provider models
  { label: 'Anthropic · Claude 3.5 Haiku',               value: 'anthropic/claude-3-5-haiku-20241022',        needs: 'ANTHROPIC_API_KEY' },
  { label: 'Anthropic · Claude 3.5 Sonnet',              value: 'anthropic/claude-3-5-sonnet-20241022',       needs: 'ANTHROPIC_API_KEY' },
  { label: 'OpenAI · gpt-4o-mini',                       value: 'openai/gpt-4o-mini',                         needs: 'OPENAI_API_KEY' },
  { label: 'OpenAI · gpt-4o',                            value: 'openai/gpt-4o',                              needs: 'OPENAI_API_KEY' },
  { label: 'Groq · Llama 3.1 70B',                       value: 'groq/llama-3.1-70b-versatile',               needs: 'GROQ_API_KEY' },
  { label: 'Groq · Llama 3.1 8B (instant)',              value: 'groq/llama-3.1-8b-instant',                  needs: 'GROQ_API_KEY' },
  { label: 'Google · Gemini 1.5 Flash',                  value: 'gemini/gemini-1.5-flash',                    needs: 'GEMINI_API_KEY' },
  { label: 'Google · Gemini 1.5 Pro',                    value: 'gemini/gemini-1.5-pro',                      needs: 'GEMINI_API_KEY' },
  // Always-available legacy fallback through OpenRouter
  { label: 'OpenRouter · Claude 3.5 Haiku (fallback)',   value: 'openrouter/anthropic/claude-3-5-haiku',      needs: 'OPENROUTER_API_KEY' },
];


function AIProvidersTab() {
  // Fetch a preview for every catalogued key. Returns null per key if the
  // secret doesn't exist yet (404 from the secrets service); the UI shows
  // "Not configured" in that case.
  const fetcher = useCallback(async (name: string): Promise<SecretPreview | null> => {
    try {
      const r = await fetch(`/api/secrets/${encodeURIComponent(name)}/preview`, {
        credentials: 'include',
      });
      if (!r.ok) return null;
      return await r.json();
    } catch { return null; }
  }, []);

  const [previews, setPreviews] = useState<Record<string, SecretPreview | null>>({});
  const [loading, setLoading] = useState(true);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [newValue, setNewValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmEmpty, setConfirmEmpty] = useState(false);

  // Active-model config (stored as secrets so admins can change without redeploy)
  const [primaryModel, setPrimaryModel]   = useState<string>('');
  const [fallbackModels, setFallbackModels] = useState<string>('');
  const [modelDirty, setModelDirty]       = useState(false);
  const [savingModel, setSavingModel]     = useState(false);
  const [modelError, setModelError]       = useState<string | null>(null);
  const [modelSavedAt, setModelSavedAt]   = useState<string | null>(null);

  const loadModelConfig = useCallback(async () => {
    // Use /api/secrets/{name} via the BFF (admin scope). Falls back to empty on 404.
    const grab = async (n: string): Promise<string> => {
      try {
        const r = await fetch(`/api/secrets/${encodeURIComponent(n)}`, { credentials: 'include' });
        if (!r.ok) return '';
        const data = await r.json();
        return data.value ?? '';
      } catch { return ''; }
    };
    const p = await grab('AI_PRIMARY_MODEL');
    const f = await grab('AI_FALLBACK_MODELS');
    setPrimaryModel(p);
    setFallbackModels(f);
    setModelDirty(false);
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    const next: Record<string, SecretPreview | null> = {};
    await Promise.all(
      AI_KEY_CATALOG.map(async (k) => {
        next[k.name] = await fetcher(k.name);
      })
    );
    setPreviews(next);
    setLoading(false);
  }, [fetcher]);

  React.useEffect(() => { reload(); loadModelConfig(); }, [reload, loadModelConfig]);

  const saveModelConfig = useCallback(async () => {
    setSavingModel(true); setModelError(null);
    try {
      // Upsert both secrets. Empty string deletes nothing — admins use the
      // dedicated keys table to remove a secret entirely.
      await api.post('/secrets', {
        name: 'AI_PRIMARY_MODEL',
        value: primaryModel.trim(),
        metadata: { kind: 'ai_model_config' },
      });
      await api.post('/secrets', {
        name: 'AI_FALLBACK_MODELS',
        value: fallbackModels.trim(),
        metadata: { kind: 'ai_model_config' },
      });
      setModelSavedAt(new Date().toISOString());
      setModelDirty(false);
    } catch (e) {
      setModelError(String(e));
    } finally {
      setSavingModel(false);
    }
  }, [primaryModel, fallbackModels]);

  const openEdit = useCallback((name: string) => {
    setEditingKey(name);
    setNewValue('');
    setError(null);
    setConfirmEmpty(false);
  }, []);

  const submitKey = useCallback(async () => {
    if (!editingKey) return;
    const v = newValue.trim();
    if (!v && !confirmEmpty) {
      setError('Enter the API key value (or check the box to clear it).');
      return;
    }
    setSaving(true); setError(null);
    try {
      // The secrets service supports POST / (upsert) and POST /<name>/rotate.
      // Use upsert because rotate requires the secret to already exist.
      const r = await api.post<{ name: string; version: number }>('/secrets', {
        name: editingKey,
        value: v,
        metadata: { kind: 'ai_provider_key' },
      });
      // Surface a quick optimistic update so the UI shows the new preview
      const visible = v.slice(0, 8);
      setPreviews((p) => ({
        ...p,
        [editingKey]: {
          name: editingKey,
          version: r.version,
          preview: v ? `${visible}${'•'.repeat(12)}` : '(empty)',
          length: v.length,
          updated_at: new Date().toISOString(),
        },
      }));
      setEditingKey(null);
      setNewValue('');
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }, [editingKey, newValue, confirmEmpty]);

  return (
    <>
      {/* Active model selector */}
      <div className="card" style={{ marginBottom: 10, padding: 14 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Active model</div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Field label="Primary model">
            {/* Real <select> instead of <datalist> so the user sees ALL
                options on click. The "Custom…" sentinel swaps in a text
                input for advanced operators who want a model id that isn't
                in the curated preset list. */}
            {(() => {
              const isPreset = PRIMARY_MODEL_PRESETS.some(p => p.value === primaryModel);
              const sentinel = '__custom__';
              return (
                <>
                  <select
                    className="select mono"
                    value={isPreset ? primaryModel : sentinel}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === sentinel) {
                        setPrimaryModel(''); // empty so the text input below renders
                      } else {
                        setPrimaryModel(v);
                      }
                      setModelDirty(true);
                    }}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {PRIMARY_MODEL_PRESETS.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label} — needs {p.needs}
                      </option>
                    ))}
                    <option value={sentinel}>Custom… (type a LiteLLM model id)</option>
                  </select>
                  {!isPreset && (
                    <input
                      className="input mono"
                      value={primaryModel}
                      onChange={(e) => { setPrimaryModel(e.target.value); setModelDirty(true); }}
                      placeholder="e.g. provider/model-id"
                      style={{ width: '100%', fontSize: 12, marginTop: 6 }}
                      autoFocus
                    />
                  )}
                </>
              );
            })()}
          </Field>
          <Field label="Fallback models (comma-separated)">
            <input
              className="input mono"
              value={fallbackModels}
              onChange={(e) => { setFallbackModels(e.target.value); setModelDirty(true); }}
              placeholder="e.g. openrouter/openai/gpt-4o-mini, openrouter/anthropic/claude-3-5-haiku"
              style={{ width: '100%', fontSize: 12 }}
            />
          </Field>
        </div>
        {modelError && <div style={{ marginTop: 8 }}><ErrorBanner>{modelError}</ErrorBanner></div>}
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn primary" onClick={saveModelConfig} disabled={savingModel || !modelDirty}>
            {savingModel ? <><Refresh s={11} style={{ animation: 'spin 1s linear infinite' }} />Saving…</> : <><Check s={11} />Save active model</>}
          </button>
          {modelSavedAt && !modelDirty && (
            <span style={{ fontSize: 11, color: '#3fb950' }}>
              <Check s={11} /> Saved {new Date(modelSavedAt).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · restart orchestrator / flowviz / indicator-intel to apply
            </span>
          )}
          {modelDirty && !modelError && (
            <span style={{ fontSize: 11, color: 'var(--text-4)' }}>Unsaved changes</span>
          )}
        </div>
      </div>

      <div className="card" style={{ overflow: 'auto' }}>
        <table className="tbl">
          <thead><tr>
            <th style={{ width: 220 }}>Provider</th>
            <th style={{ width: 220 }}>Secret name</th>
            <th>Current key (masked)</th>
            <th style={{ width: 90 }}>Length</th>
            <th style={{ width: 130 }}>Last updated</th>
            <th style={{ width: 110 }}>Actions</th>
          </tr></thead>
          <tbody>
            {loading && (
              <tr><td colSpan={6} style={{ padding: 30, textAlign: 'center', color: 'var(--text-4)' }}>Loading providers…</td></tr>
            )}
            {!loading && AI_KEY_CATALOG.map((k) => {
              const p = previews[k.name];
              const isFallback = k.name === 'OPENROUTER_API_KEY';
              return (
                <tr key={k.name}>
                  <td>
                    <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      {k.provider}
                      {isFallback && <span className="tag" style={{ fontSize: 10, background: 'rgba(88,166,255,0.1)', color: 'var(--accent)' }}>fallback</span>}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 2 }}>{k.help}</div>
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>{k.name}</td>
                  <td className="mono" style={{ fontSize: 12, color: p ? 'var(--text-2)' : 'var(--text-4)' }}>
                    {p ? p.preview : <span style={{ fontStyle: 'italic' }}>(not configured)</span>}
                  </td>
                  <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>{p ? `${p.length} chars` : '—'}</td>
                  <td className="mono" style={{ fontSize: 10.5, color: 'var(--text-4)' }}>
                    {p ? new Date(p.updated_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                  </td>
                  <td>
                    <button className="btn sm primary" style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => openEdit(k.name)}>
                      {p ? 'Rotate' : 'Set'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Edit modal */}
      {editingKey && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 20,
        }}>
          <div style={{
            width: 560, maxHeight: '90vh', display: 'flex', flexDirection: 'column',
            background: 'var(--bg-card)', border: '1px solid var(--border-strong)',
            borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden',
          }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Refresh s={14} />
              <div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>
                {previews[editingKey] ? 'Rotate' : 'Set'}: <span className="mono">{editingKey}</span>
              </div>
              <button className="btn sm" onClick={() => setEditingKey(null)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
              <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                Paste the new API key value. It is sent to the secrets service over the in-cluster network,
                Fernet-encrypted at rest, and never echoed back to a browser. The current value (if any) is
                replaced atomically and an audit-log entry is written.
              </div>
              <Field label="New API key value">
                <input
                  className="input mono"
                  type="password"
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  placeholder={AI_KEY_CATALOG.find((k) => k.name === editingKey)?.sample ?? '...'}
                  style={{ width: '100%', fontSize: 12 }}
                  autoFocus
                  autoComplete="new-password"
                  spellCheck={false}
                />
              </Field>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--text-4)', cursor: 'pointer' }}>
                <input type="checkbox" checked={confirmEmpty} onChange={(e) => setConfirmEmpty(e.target.checked)} />
                I want to clear this key (submit empty value)
              </label>
              {error && <ErrorBanner>{error}</ErrorBanner>}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setEditingKey(null)}>Cancel</button>
              <button className="btn primary" onClick={submitKey} disabled={saving}>
                {saving ? <><Refresh s={11} style={{ animation: 'spin 1s linear infinite' }} />Saving…</> : <><Check s={11} />Save key</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
