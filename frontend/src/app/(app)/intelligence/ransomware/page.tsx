'use client';

import React, { useEffect, useMemo, useState } from 'react';
import KPI from '@/components/shared/KPI';
import SortHeader from '@/components/shared/SortHeader';
import Flag from '@/components/shared/Flag';
import { Skull, AlertTriangle, Search, X, ExternalLink, Users, Refresh } from '@/components/icons';
import { useRansomwareGroups, useRansomwareVictims, useOne, RansomwareGroup, RansomwareVictim, Actor } from '@/lib/hooks';
import { useSortable } from '@/lib/sort';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

/* --------------------------------------------------------------------------- */
/* Group detail slide-over                                                     */
/* --------------------------------------------------------------------------- */

function GroupDetailPanel({ groupId, onClose }: { groupId: string; onClose: () => void }) {
  // Fetch fresh group + victim data for this group only — keeps the slide-over
  // independent from the main list pagination.
  const { data: group } = useOne<RansomwareGroup>(`/ransomware/groups/${groupId}`);
  const { data: linkedActor } = useOne<Actor | null>(`/ransomware/groups/${groupId}/actor`);
  const { items: victims } = useRansomwareVictims({ group_id: groupId, limit: 500 });

  const { sorted, sortKey, sortDir, toggle } = useSortable(victims as RansomwareVictim[], 'disclosed_at', 'desc');

  if (!group) {
    return (
      <div style={{ position: 'fixed', inset: 0, zIndex: 200, background: 'rgba(0,0,0,0.45)' }} onClick={onClose}>
        <div style={{ position: 'absolute', right: 0, top: 0, width: 640, height: '100%', background: 'var(--bg-page)', padding: 40, color: 'var(--text-4)' }}>
          Loading…
        </div>
      </div>
    );
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end',
      background: 'rgba(0,0,0,0.45)',
    }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        style={{
          width: 720, height: '94vh',
          background: 'var(--bg-page)',
          borderLeft: '1px solid var(--border)',
          borderTop: '1px solid var(--border)',
          borderRadius: '12px 0 0 0',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}>
        {/* Header */}
        <div style={{
          padding: '14px 18px', borderBottom: '1px solid var(--border)',
          background: 'linear-gradient(180deg,rgba(248,81,73,0.07),transparent 80%)',
          display: 'flex', alignItems: 'flex-start', gap: 12,
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{group.name}</div>
              <span className={`badge ${group.status === 'active' ? 'crit' : 'mute'}`}>
                {group.status === 'active' && <span className="dot pulse" />}{group.status}
              </span>
              {linkedActor && (
                <a href={`/actors/${linkedActor.id}`} className="tag" style={{ background: 'rgba(88,166,255,0.1)', color: 'var(--accent)', border: '1px solid rgba(88,166,255,0.3)', fontSize: 11 }}>
                  <Users s={10} /> MITRE: {linkedActor.name} ({linkedActor.mitre_id ?? 'no id'}) <ExternalLink s={9} />
                </a>
              )}
            </div>
            {(group.aliases ?? []).length > 0 && (
              <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 4 }}>
                Aliases: <span className="mono">{(group.aliases ?? []).join(' · ')}</span>
              </div>
            )}
            {group.description && (
              <div style={{ fontSize: 12.5, color: 'var(--text-2)', marginTop: 8, lineHeight: 1.6, maxHeight: 100, overflow: 'auto' }}>
                {group.description}
              </div>
            )}
          </div>
          <button className="btn sm" onClick={onClose}><X s={11} />Close</button>
        </div>

        {/* Detail scroll area */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Meta */}
          <div className="card">
            <div className="card-h"><Skull s={12} /><div className="t">Group profile</div></div>
            <div style={{ padding: '8px 14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 20px', fontSize: 12 }}>
              <Row k="First seen" v={fmtDate(group.first_seen)} />
              <Row k="Last active" v={fmtDate(group.last_seen)} />
              <Row k="Victims (tracked)" v={String(group.victim_count ?? victims.length)} />
              <Row k="Variants" v={(group.variants ?? []).join(', ') || '—'} />
              <Row k="Tor URLs" v={String((group.tor_urls ?? []).length)} />
              <Row k="Domains" v={String((group.domains ?? []).length)} />
            </div>
            <div style={{ padding: '0 14px 12px' }}>
              {(group.target_countries ?? []).length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Target countries</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {(group.target_countries ?? []).slice(0, 30).map((c) => <span key={c} className="tag" style={{ fontSize: 10 }}>{c}</span>)}
                    {(group.target_countries ?? []).length > 30 && <span className="tag">+{(group.target_countries ?? []).length - 30}</span>}
                  </div>
                </div>
              )}
              {(group.target_sectors ?? []).length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Target sectors</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {(group.target_sectors ?? []).slice(0, 20).map((s) => <span key={s} className="tag" style={{ fontSize: 10 }}>{s}</span>)}
                  </div>
                </div>
              )}
              {((group.tor_urls ?? []).length > 0 || group.leak_site_url) && (
                <div style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Leak / Tor URLs</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {group.leak_site_url && (
                      <a href={group.leak_site_url} target="_blank" rel="noopener noreferrer" className="mono" style={{ fontSize: 11, color: 'var(--accent)', wordBreak: 'break-all' }}>
                        {group.leak_site_url}
                      </a>
                    )}
                    {(group.tor_urls ?? []).slice(0, 5).map((u) => (
                      <span key={u} className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)', wordBreak: 'break-all' }}>{u}</span>
                    ))}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 4 }}>Use with caution — these are adversary-controlled leak sites.</div>
                </div>
              )}
            </div>
          </div>

          {/* Victims */}
          <div className="card" style={{ flex: 1, minHeight: 0 }}>
            <div className="card-h">
              <AlertTriangle s={12} />
              <div className="t">Victims</div>
              <div className="s">{victims.length} tracked</div>
            </div>
            <div style={{ overflow: 'auto', maxHeight: 460 }}>
              {victims.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
                  No victims tracked for this group yet.
                </div>
              ) : (
                <table className="tbl">
                  <thead><tr>
                    <SortHeader label="Disclosed" sortKey="disclosed_at" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
                    <SortHeader label="Victim" sortKey="victim_name" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} />
                    <SortHeader label="Sector" sortKey="sector" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 130 }} />
                    <th style={{ width: 70 }}>Country</th>
                  </tr></thead>
                  <tbody>
                    {sorted.map((v) => (
                      <tr key={v.id}>
                        <td className="mono" style={{ fontSize: 11 }}>{fmtDate(v.disclosed_at)}</td>
                        <td className="primary">{v.victim_name}</td>
                        <td><span className="tag" style={{ fontSize: 10 }}>{v.sector ?? '—'}</span></td>
                        <td>{v.country ? <Flag code={v.country} /> : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-soft)', padding: '4px 0' }}>
      <span style={{ color: 'var(--text-4)' }}>{k}</span>
      <span className="mono" style={{ color: 'var(--text-2)' }}>{v}</span>
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* Page                                                                        */
/* --------------------------------------------------------------------------- */

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function RansomwarePage() {
  const [groupSearch, setGroupSearch]   = useState('');
  const [victimSearch, setVictimSearch] = useState('');
  const [victimGroupFilter, setVictimGroupFilter] = useState<{ id: string; name: string } | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);

  const debouncedGroupQ  = useDebounced(groupSearch, 250);
  const debouncedVictimQ = useDebounced(victimSearch, 250);

  const { items: groups,  total: groupsTotal,  isLoading: gLoading, mutate: mutateGroups } =
    useRansomwareGroups({ q: debouncedGroupQ || undefined, limit: 200 });

  const { items: victims, total: victimsTotal, isLoading: vLoading, mutate: mutateVictims } =
    useRansomwareVictims({
      q: debouncedVictimQ || undefined,
      group_id: victimGroupFilter?.id,
      limit: 200,
    });

  // KPIs use the FULL victim aggregates on groups (server-computed) when available,
  // and fall back to the visible page for incomplete cases.
  const now        = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const thisMonth  = (victims as RansomwareVictim[]).filter((v) => v.disclosed_at && new Date(v.disclosed_at) >= monthStart).length;

  const sectorCounts  = useMemo(() => {
    const m = new Map<string, number>();
    for (const g of (groups as RansomwareGroup[])) {
      for (const s of (g.target_sectors ?? [])) {
        m.set(s, (m.get(s) ?? 0) + 1);
      }
    }
    return m;
  }, [groups]);
  const countryCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const g of (groups as RansomwareGroup[])) {
      for (const c of (g.target_countries ?? [])) {
        m.set(c, (m.get(c) ?? 0) + 1);
      }
    }
    return m;
  }, [groups]);
  const topSector  = [...sectorCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]  ?? '—';
  const topCountry = [...countryCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? '—';
  const activeGroups = (groups as RansomwareGroup[]).filter((g) => g.status === 'active').length;

  const { sorted: sortedGroups,  sortKey: gSortKey, sortDir: gSortDir, toggle: gToggle } =
    useSortable(groups as RansomwareGroup[], 'victim_count', 'desc');
  const { sorted: sortedVictims, sortKey: vSortKey, sortDir: vSortDir, toggle: vToggle } =
    useSortable(victims as RansomwareVictim[], 'disclosed_at', 'desc');

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10, flexShrink: 0 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Ransomware tracker</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => { mutateGroups(); mutateVictims(); }}><Refresh s={12} />Refresh</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 14, flexShrink: 0 }}>
        <KPI label="Active groups"      value={gLoading ? '...' : String(activeGroups)}            delta={`${groupsTotal.toLocaleString()} total`} deltaDir="up" color="#f85149" />
        <KPI label="Victims this month" value={vLoading ? '...' : String(thisMonth)}               delta="disclosed" deltaDir="up" color="#d29922" />
        <KPI label="Top sector"         value={topSector}                                          delta="most hit" deltaDir="up" color="#a371f7" />
        <KPI label="Top country"        value={topCountry}                                         delta="most hit" deltaDir="up" color="#58a6ff" />
        <KPI label="Total tracked"      value={vLoading ? '...' : victimsTotal.toLocaleString()}   delta="victims" deltaDir="up" live color="#3fb950" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, flex: 1, minHeight: 0 }}>
        {/* Groups */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="card-h" style={{ flexShrink: 0 }}>
            <Skull s={13} /><div className="t">Groups</div><div className="s">{groups.length} of {groupsTotal.toLocaleString()}</div>
          </div>
          <div style={{ padding: '8px 12px', flexShrink: 0, borderBottom: '1px solid var(--border-soft)' }}>
            <div style={{ position: 'relative', maxWidth: 320 }}>
              <input
                className="input"
                placeholder="Search by name, alias, description..."
                value={groupSearch}
                onChange={(e) => setGroupSearch(e.target.value)}
                style={{ paddingLeft: 28, height: 28, fontSize: 12, width: '100%', boxSizing: 'border-box' }}
              />
              <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-4)', pointerEvents: 'none' }}>
                <Search s={12} />
              </span>
            </div>
          </div>
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="tbl">
              <thead><tr>
                <SortHeader label="Name"        sortKey="name"         currentKey={gSortKey} currentDir={gSortDir} onToggle={gToggle} />
                <SortHeader label="Victims"     sortKey="victim_count" currentKey={gSortKey} currentDir={gSortDir} onToggle={gToggle} style={{ width: 80 }} />
                <SortHeader label="Status"      sortKey="status"       currentKey={gSortKey} currentDir={gSortDir} onToggle={gToggle} style={{ width: 80 }} />
                <SortHeader label="First seen"  sortKey="first_seen"   currentKey={gSortKey} currentDir={gSortDir} onToggle={gToggle} style={{ width: 110 }} />
                <SortHeader label="Last seen"   sortKey="last_seen"    currentKey={gSortKey} currentDir={gSortDir} onToggle={gToggle} style={{ width: 110 }} />
              </tr></thead>
              <tbody>
                {gLoading && <tr><td colSpan={5} style={{ padding: 20, color: 'var(--text-4)' }}>Loading...</td></tr>}
                {!gLoading && sortedGroups.length === 0 && <tr><td colSpan={5} style={{ padding: 20, color: 'var(--text-4)' }}>No groups match.</td></tr>}
                {(sortedGroups as RansomwareGroup[]).map((g) => (
                  <tr key={g.id} onClick={() => setSelectedGroupId(g.id)} style={{ cursor: 'pointer' }}>
                    <td className="primary" style={{ fontWeight: 500, color: 'var(--accent)' }}>{g.name}</td>
                    <td className="mono" style={{ fontSize: 11, fontWeight: 600 }}>{g.victim_count ?? 0}</td>
                    <td><span className={`badge ${g.status === 'active' ? 'crit' : 'mute'}`}>
                      {g.status === 'active' && <span className="dot pulse" />}{g.status}
                    </span></td>
                    <td className="mono" style={{ fontSize: 11 }}>{fmtDate(g.first_seen)}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{fmtDate(g.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Victims */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="card-h" style={{ flexShrink: 0 }}>
            <AlertTriangle s={13} /><div className="t">Recent victims</div><div className="s">{victims.length} of {victimsTotal.toLocaleString()}</div>
          </div>
          <div style={{ padding: '8px 12px', flexShrink: 0, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', borderBottom: '1px solid var(--border-soft)' }}>
            <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
              <input
                className="input"
                placeholder="Search victim, sector, country..."
                value={victimSearch}
                onChange={(e) => setVictimSearch(e.target.value)}
                style={{ paddingLeft: 28, height: 28, fontSize: 12, width: '100%', boxSizing: 'border-box' }}
              />
              <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-4)', pointerEvents: 'none' }}>
                <Search s={12} />
              </span>
            </div>
            {victimGroupFilter && (
              <span className="tag" style={{ fontSize: 11, background: 'rgba(248,81,73,0.1)', color: '#f85149', display: 'flex', alignItems: 'center', gap: 4 }}>
                Group: {victimGroupFilter.name}
                <button onClick={() => setVictimGroupFilter(null)} style={{ all: 'unset', cursor: 'pointer' }}><X s={10} /></button>
              </span>
            )}
          </div>
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="tbl">
              <thead><tr>
                <SortHeader label="Disclosed" sortKey="disclosed_at" currentKey={vSortKey} currentDir={vSortDir} onToggle={vToggle} style={{ width: 110 }} />
                <SortHeader label="Victim"    sortKey="victim_name"  currentKey={vSortKey} currentDir={vSortDir} onToggle={vToggle} />
                <SortHeader label="Group"     sortKey="group_name"   currentKey={vSortKey} currentDir={vSortDir} onToggle={vToggle} style={{ width: 130 }} />
                <SortHeader label="Sector"    sortKey="sector"       currentKey={vSortKey} currentDir={vSortDir} onToggle={vToggle} style={{ width: 110 }} />
                <th style={{ width: 70 }}>Country</th>
              </tr></thead>
              <tbody>
                {vLoading && <tr><td colSpan={5} style={{ padding: 20, color: 'var(--text-4)' }}>Loading...</td></tr>}
                {!vLoading && sortedVictims.length === 0 && <tr><td colSpan={5} style={{ padding: 20, color: 'var(--text-4)' }}>No victims match.</td></tr>}
                {(sortedVictims as RansomwareVictim[]).map((v) => (
                  <tr key={v.id}>
                    <td className="mono" style={{ fontSize: 11 }}>{fmtDate(v.disclosed_at)}</td>
                    <td className="primary">{v.victim_name}</td>
                    <td>
                      {v.group_name ? (
                        <button
                          className="tag"
                          style={{ cursor: 'pointer', background: 'rgba(248,81,73,0.08)', color: '#f85149', border: '1px solid rgba(248,81,73,0.25)', fontSize: 11 }}
                          onClick={() => v.group_id && setVictimGroupFilter({ id: v.group_id, name: v.group_name ?? '' })}
                          title="Filter victims by this group"
                        >
                          {v.group_name}
                        </button>
                      ) : <span className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>—</span>}
                    </td>
                    <td><span className="tag">{v.sector ?? '—'}</span></td>
                    <td>{v.country ? <Flag code={v.country} /> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Group detail slide-over */}
      {selectedGroupId && (
        <GroupDetailPanel
          groupId={selectedGroupId}
          onClose={() => setSelectedGroupId(null)}
        />
      )}
    </div>
  );
}
