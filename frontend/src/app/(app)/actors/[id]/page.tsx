'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Flag from '@/components/shared/Flag';
import SortHeader from '@/components/shared/SortHeader';
import {
  Layers, Sparkles, Skull, Crosshair, MessageSquare,
  Pin, Refresh, GitBranch, Download, Plus, ChevronLeft,
  FileText, AlertTriangle, Search, ExternalLink, Network,
} from '@/components/icons';
import useSWR from 'swr';
import {
  useOne,
  useArticles, useIndicators, useRansomwareGroups, useRansomwareVictims,
} from '@/lib/hooks';
import type { Actor, Article, Indicator, RansomwareGroup, RansomwareVictim } from '@/lib/hooks';
import { useSortable } from '@/lib/sort';
import { fetcher } from '@/lib/api';

/* ---- Extended actor detail type ---- */
interface TTP {
  technique_id: string;
  technique_name: string;
  sub_technique_id: string | null;
  confidence: number;
  source: string;
}
interface Tool { id: string; name: string; type: string; mitre_id: string | null; description: string | null; }
interface ActorDetail extends Actor {
  ttps?: TTP[];
  tools?: Tool[];
}

type TabId = 'overview' | 'ttps' | 'iocs' | 'intel' | 'ransomware';

/* ---- MITRE ATT&CK tactics ---- */
const TACTICS = [
  { id: 'TA0043', name: 'Recon' }, { id: 'TA0042', name: 'Resource Dev.' },
  { id: 'TA0001', name: 'Initial Access' }, { id: 'TA0002', name: 'Execution' },
  { id: 'TA0003', name: 'Persistence' }, { id: 'TA0004', name: 'Priv. Esc.' },
  { id: 'TA0005', name: 'Defense Evasion' }, { id: 'TA0006', name: 'Cred. Access' },
  { id: 'TA0007', name: 'Discovery' }, { id: 'TA0008', name: 'Lateral Mvt.' },
  { id: 'TA0009', name: 'Collection' }, { id: 'TA0011', name: 'C2' },
  { id: 'TA0010', name: 'Exfil' }, { id: 'TA0040', name: 'Impact' },
];

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function confColor(c: number) {
  if (c >= 0.8) return 'rgba(248,81,73,0.22)';
  if (c >= 0.5) return 'rgba(210,153,34,0.18)';
  return 'rgba(88,166,255,0.12)';
}
function confBorder(c: number) {
  if (c >= 0.8) return 'rgba(248,81,73,0.4)';
  if (c >= 0.5) return 'rgba(210,153,34,0.35)';
  return 'rgba(88,166,255,0.25)';
}

function confBar(c: number) {
  const pct = Math.round(c * 100);
  const color = c >= 0.8 ? '#f85149' : c >= 0.5 ? '#d29922' : '#58a6ff';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)', width: 28 }}>{pct}%</span>
    </div>
  );
}

/* ---- Tabs ---- */
function TabBar({ active, onChange, showRansomware }: { active: TabId; onChange: (t: TabId) => void; showRansomware: boolean }) {
  const tabs: { id: TabId; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'ttps', label: 'TTPs' },
    { id: 'iocs', label: 'IOCs' },
    { id: 'intel', label: 'Intel' },
    ...(showRansomware ? [{ id: 'ransomware' as TabId, label: 'Ransomware' }] : []),
  ];

  return (
    <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 18px', flexShrink: 0 }}>
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          style={{
            padding: '9px 16px', fontSize: 12.5,
            fontWeight: active === t.id ? 600 : 400,
            color: active === t.id ? 'var(--text)' : 'var(--text-4)',
            borderBottom: `2px solid ${active === t.id ? 'var(--accent)' : 'transparent'}`,
            background: 'none', border: 'none',
            borderTop: 'none', borderLeft: 'none', borderRight: 'none',
            cursor: 'pointer', transition: 'color 0.15s',
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ---- Overview tab ---- */
function OverviewTab({ actor, tools }: { actor: ActorDetail; tools: Tool[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 12, padding: 14 }}>
      {/* Left */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Description */}
        <div className="card">
          <div className="card-h"><Skull s={13} /><div className="t">Actor summary</div></div>
          <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 20px', fontSize: 12 }}>
              {[
                ['MITRE ID', actor.mitre_id ?? '—'],
                ['Status', actor.status],
                ['Origin country', actor.origin_country ?? '—'],
                ['Active since', fmtDate(actor.active_since)],
                ['Last seen', fmtDate(actor.last_seen)],
                ['Aliases', actor.aliases.join(', ') || '—'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-soft)', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-4)' }}>{k}</span>
                  <span className="mono" style={{ color: 'var(--text-2)' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Motivations & sectors */}
        <div className="card">
          <div className="card-h"><Crosshair s={13} /><div className="t">Targeting profile</div></div>
          <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 6 }}>Motivations</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {actor.motivation.length > 0
                  ? actor.motivation.map(m => <span key={m} className="badge high">{m}</span>)
                  : <span style={{ fontSize: 11, color: 'var(--text-4)' }}>—</span>}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 6 }}>Target sectors</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {actor.target_sectors.length > 0
                  ? actor.target_sectors.map(s => <span key={s} className="tag">{s}</span>)
                  : <span style={{ fontSize: 11, color: 'var(--text-4)' }}>—</span>}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 6 }}>Target countries</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {actor.target_countries.length > 0
                  ? actor.target_countries.map(c => (
                    <span key={c} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Flag code={c} /><span style={{ fontSize: 11.5 }}>{c}</span>
                    </span>
                  ))
                  : <span style={{ fontSize: 11, color: 'var(--text-4)' }}>—</span>}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Stats */}
        <div className="card">
          <div className="card-h"><Network s={13} /><div className="t">Intelligence metrics</div></div>
          <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
            {[
              ['Techniques', String((actor.ttps ?? []).length)],
              ['Tools & malware', String(tools.length)],
              ['Target sectors', String(actor.target_sectors.length)],
              ['Target countries', String(actor.target_countries.length)],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-4)' }}>{k}</span>
                <span className="mono" style={{ color: 'var(--accent)', fontWeight: 600 }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Tools & Malware */}
        <div className="card">
          <div className="card-h"><MessageSquare s={13} /><div className="t">Tools & Malware</div><div className="s">{tools.length}</div></div>
          {tools.length === 0 ? (
            <div style={{ padding: '14px 12px', textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
              No tools recorded
            </div>
          ) : (
            <div style={{ padding: 4, maxHeight: 320, overflow: 'auto' }}>
              {tools.map((t, i) => (
                <div key={t.id} style={{ padding: '8px 12px', borderBottom: i < tools.length - 1 ? '1px solid var(--border-soft)' : 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ fontSize: 12.5, color: 'var(--text)', fontWeight: 500 }}>{t.name}</div>
                    {t.mitre_id && <span className="mono" style={{ fontSize: 10, color: 'var(--accent)' }}>{t.mitre_id}</span>}
                    <span className="tag" style={{ marginLeft: 'auto', fontSize: 10 }}>{t.type}</span>
                  </div>
                  {t.description && (
                    <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 2, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {t.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI insight — pulls the actor_likelihood row produced by the
            orchestrator's analysis cycle. If this actor wasn't ranked, the
            cycle either hasn't run or this actor isn't in the top-N (which is
            itself a signal we expose). */}
        <ActorAiInsight actorId={actor.id} />

        {/* Export — both formats are stubbed; mark disabled so users know it's
            planned not broken. */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" style={{ flex: 1 }} disabled title="STIX 2.1 export not yet implemented"><Download s={11} />STIX 2.1</button>
          <button className="btn" style={{ flex: 1 }} disabled title="MISP push not yet implemented"><MessageSquare s={11} />MISP</button>
        </div>
      </div>
    </div>
  );
}


/* ---- ActorAiInsight ----------------------------------------------------
 * Show this actor's row from the orchestrator's actor_likelihood scoring.
 * No new endpoint needed — /relevance/actors returns the top-ranked actors
 * and we look up by id.
 */
interface ActorLikelihoodRow {
  actor_id: string;
  likelihood_score: number;
  ttps_overlap: string[];
  rationale: string | null;
  scored_at: string;
}

function ActorAiInsight({ actorId }: { actorId: string }) {
  const { data, isLoading } = useSWR<ActorLikelihoodRow[]>(
    '/relevance/actors?limit=50',
    fetcher,
    { revalidateOnFocus: false },
  );
  const row = (data ?? []).find(r => r.actor_id === actorId);

  return (
    <div className="card">
      <div className="card-h"><Sparkles s={13} /><div className="t">AI insight</div></div>
      {isLoading && (
        <div style={{ padding: '16px 14px', textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
          Loading likelihood…
        </div>
      )}
      {!isLoading && !row && (
        <div style={{ padding: '16px 14px', textAlign: 'center', color: 'var(--text-4)', fontSize: 12, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          <Sparkles s={18} />
          <div>This actor isn&apos;t in the latest top-50 likelihood ranking for our profile.</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-mute)' }}>
            Trigger an analysis cycle from the dashboard to refresh rankings.
          </div>
        </div>
      )}
      {!isLoading && row && (
        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: row.likelihood_score >= 0.7 ? 'var(--crit)' : row.likelihood_score >= 0.4 ? 'var(--high)' : 'var(--med)', fontFamily: 'var(--mono)' }}>
              {(row.likelihood_score * 100).toFixed(0)}%
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-4)' }}>likelihood vs your profile</div>
          </div>
          {row.rationale && (
            <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.5 }}>{row.rationale}</div>
          )}
          {row.ttps_overlap && row.ttps_overlap.length > 0 && (
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                Overlapping TTPs ({row.ttps_overlap.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {row.ttps_overlap.slice(0, 10).map(t => <span key={t} className="tag mono">{t}</span>)}
                {row.ttps_overlap.length > 10 && <span className="tag">+{row.ttps_overlap.length - 10}</span>}
              </div>
            </div>
          )}
          <div style={{ fontSize: 10, color: 'var(--text-mute)' }}>
            Scored {new Date(row.scored_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- TTPs tab ---- */
function TTPsTab({ ttps }: { ttps: TTP[] }) {
  const tacticMap: Record<string, TTP[]> = {};
  for (const t of ttps) {
    const tid = t.technique_id.split('.')[0];
    const bucket = tid >= 'T1580' ? 'TA0040'
      : tid >= 'T1550' ? 'TA0010'
      : tid >= 'T1497' ? 'TA0011'
      : tid >= 'T1430' ? 'TA0009'
      : tid >= 'T1380' ? 'TA0008'
      : tid >= 'T1280' ? 'TA0007'
      : tid >= 'T1185' ? 'TA0006'
      : tid >= 'T1110' ? 'TA0005'
      : tid >= 'T1068' ? 'TA0004'
      : tid >= 'T1047' ? 'TA0003'
      : tid >= 'T1027' ? 'TA0002'
      : tid >= 'T1001' ? 'TA0001'
      : 'TA0043';
    if (!tacticMap[bucket]) tacticMap[bucket] = [];
    tacticMap[bucket].push(t);
  }

  if (ttps.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
        <Layers s={24} />
        <div style={{ marginTop: 12 }}>No TTPs recorded for this actor.</div>
        <div style={{ marginTop: 4 }}>Run the actors refresh job to pull from MITRE ATT&amp;CK.</div>
      </div>
    );
  }

  return (
    <div style={{ padding: 14 }}>
      <div className="card">
        <div className="card-h">
          <Layers s={13} />
          <div className="t">MITRE ATT&CK · TTP coverage</div>
          <div className="s">{ttps.length} techniques observed</div>
          <div className="right" style={{ display: 'flex', gap: 12, fontSize: 10.5, color: 'var(--text-4)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, background: 'rgba(248,81,73,0.22)', border: '1px solid rgba(248,81,73,0.4)', borderRadius: 2 }} />high (≥0.8)
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, background: 'rgba(210,153,34,0.18)', border: '1px solid rgba(210,153,34,0.35)', borderRadius: 2 }} />med (≥0.5)
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, background: 'rgba(88,166,255,0.12)', border: '1px solid rgba(88,166,255,0.25)', borderRadius: 2 }} />low
            </span>
          </div>
        </div>
        <div style={{ overflow: 'auto', padding: 10 }}>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${TACTICS.length}, minmax(88px, 1fr))`, gap: 4, minWidth: 700 }}>
            {TACTICS.map((tac) => (
              <div key={tac.id} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <div style={{ padding: '5px 4px', textAlign: 'center', borderBottom: '1px solid var(--border)', marginBottom: 4 }}>
                  <div style={{ fontSize: 9.5, fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap' }}>{tac.name}</div>
                  <div className="mono" style={{ fontSize: 8.5, color: 'var(--text-4)' }}>{tac.id}</div>
                </div>
                {(tacticMap[tac.id] ?? []).slice(0, 6).map((ttp) => (
                  <div key={ttp.technique_id} title={`${ttp.technique_id} — ${ttp.technique_name} (confidence: ${Math.round(ttp.confidence * 100)}%)`}
                       style={{ padding: '5px 6px', borderRadius: 4, border: `1px solid ${confBorder(ttp.confidence)}`, background: confColor(ttp.confidence), cursor: 'default', minHeight: 36 }}>
                    <div className="mono" style={{ fontSize: 9, opacity: 0.7 }}>{ttp.technique_id}</div>
                    <div style={{ fontSize: 10, marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ttp.technique_name}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* TTP table */}
      <div className="card" style={{ marginTop: 12 }}>
        <div className="card-h"><Layers s={13} /><div className="t">Full technique list</div><div className="s">{ttps.length} total</div></div>
        <div style={{ overflow: 'auto', maxHeight: 400 }}>
          <table className="tbl">
            <thead><tr>
              <th style={{ width: 110 }}>Technique</th>
              <th>Name</th>
              <th style={{ width: 100 }}>Sub-technique</th>
              <th style={{ width: 140 }}>Confidence</th>
              <th style={{ width: 100 }}>Source</th>
            </tr></thead>
            <tbody>
              {ttps.map(t => (
                <tr key={t.technique_id}>
                  <td><span className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>{t.technique_id}</span></td>
                  <td style={{ fontSize: 12 }}>{t.technique_name}</td>
                  <td><span className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>{t.sub_technique_id ?? '—'}</span></td>
                  <td>{confBar(t.confidence)}</td>
                  <td><span className="tag" style={{ fontSize: 10 }}>{t.source}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ---- IOCs tab ---- */
function IOCsTab({ actorName }: { actorName: string }) {
  const [localQ, setLocalQ] = useState(actorName);
  const [searchQ, setSearchQ] = useState(actorName);
  const { items: iocs, total, isLoading } = useIndicators({ q: searchQ, limit: 50 });
  const { sorted, sortKey, sortDir, toggle } = useSortable(iocs as Indicator[], 'last_seen', 'desc');

  return (
    <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="card">
        <div className="card-h">
          <Crosshair s={13} />
          <div className="t">IOC library search</div>
          <div className="s">{total} results for &quot;{searchQ}&quot;</div>
          <div className="right">
            <a href={`/iocs?q=${encodeURIComponent(searchQ)}`}
               style={{ fontSize: 11, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 4 }}>
              Open full library <ExternalLink s={10} />
            </a>
          </div>
        </div>

        {/* Search bar */}
        <div style={{ padding: '6px 12px 8px' }}>
          <div className="bar">
            <Search s={12} />
            <input
              value={localQ}
              onChange={e => setLocalQ(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && setSearchQ(localQ)}
              placeholder="Search IOC value or tag..."
              style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 12 }}
            />
            <button className="btn sm" onClick={() => setSearchQ(localQ)}>Search</button>
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', marginTop: 6 }}>
            Searches indicator values and tags across the IOC library. Press Enter or click Search.
          </div>
        </div>

        <div style={{ overflow: 'auto', maxHeight: 480 }}>
          <table className="tbl">
            <thead><tr>
              <th style={{ width: 80 }}>Type</th>
              <th>Value</th>
              <th style={{ width: 130 }}>Tags</th>
              <th style={{ width: 90 }}>Confidence</th>
              <SortHeader label="Last seen" sortKey="last_seen" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
            </tr></thead>
            <tbody>
              {isLoading && <tr><td colSpan={5} style={{ padding: 20, color: 'var(--text-4)' }}>Loading…</td></tr>}
              {!isLoading && sorted.length === 0 && (
                <tr><td colSpan={5} style={{ padding: 20, color: 'var(--text-4)', textAlign: 'center' }}>
                  No indicators found for &quot;{searchQ}&quot;. Try searching by malware family name or tool name.
                </td></tr>
              )}
              {(sorted as Indicator[]).map(ind => (
                <tr key={ind.id}>
                  <td><span className={`badge ${ind.type === 'ip' ? 'med' : ind.type === 'domain' ? 'high' : 'mute'}`}>{ind.type}</span></td>
                  <td>
                    <a href={`/iocs/${ind.id}`} className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>
                      {ind.normalized_value}
                    </a>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {ind.tags.slice(0, 3).map(t => <span key={t} className="tag" style={{ fontSize: 9.5 }}>{t}</span>)}
                      {ind.tags.length > 3 && <span className="tag" style={{ fontSize: 9.5 }}>+{ind.tags.length - 3}</span>}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ width: `${Math.round((ind.confidence_score ?? 0) * 100)}%`, height: '100%', background: 'var(--accent)', borderRadius: 2 }} />
                      </div>
                      <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>{Math.round((ind.confidence_score ?? 0) * 100)}%</span>
                    </div>
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>{ind.last_seen ? new Date(ind.last_seen).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ---- Intel tab ---- */
function IntelTab({ actorName }: { actorName: string }) {
  const { items: articles, isLoading } = useArticles({ q: actorName, limit: 20 });
  const { sorted, sortKey, sortDir, toggle } = useSortable(articles as Article[], 'published_at', 'desc');

  return (
    <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="card">
        <div className="card-h">
          <FileText s={13} />
          <div className="t">Related intelligence articles</div>
          <div className="s">{articles.length} found for &quot;{actorName}&quot;</div>
          <div className="right">
            <a href={`/intelligence/articles?q=${encodeURIComponent(actorName)}`}
               style={{ fontSize: 11, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 4 }}>
              View all articles <ExternalLink s={10} />
            </a>
          </div>
        </div>
        <div style={{ overflow: 'auto', maxHeight: 520 }}>
          <table className="tbl">
            <thead><tr>
              <SortHeader label="Date" sortKey="published_at" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
              <th>Title</th>
              <th style={{ width: 130 }}>Source</th>
              <th style={{ width: 120 }}>Tags</th>
            </tr></thead>
            <tbody>
              {isLoading && <tr><td colSpan={4} style={{ padding: 20, color: 'var(--text-4)' }}>Loading…</td></tr>}
              {!isLoading && sorted.length === 0 && (
                <tr><td colSpan={4} style={{ padding: 20, color: 'var(--text-4)', textAlign: 'center' }}>
                  No articles found mentioning &quot;{actorName}&quot;.
                </td></tr>
              )}
              {(sorted as Article[]).map(a => (
                <tr key={a.id}>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {a.published_at ? new Date(a.published_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'}
                  </td>
                  <td>
                    <a href={`/intelligence/articles/${a.id}`} style={{ fontSize: 12, color: 'var(--text)', textDecoration: 'none' }}
                       className="primary">
                      {a.title}
                    </a>
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--text-4)' }}>{a.source_name}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {a.tags.slice(0, 2).map(t => <span key={t} className="tag" style={{ fontSize: 9.5 }}>{t}</span>)}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ---- Ransomware Victims tab ---- */
function RansomwareTab({ actorName }: { actorName: string }) {
  const { items: groups } = useRansomwareGroups();
  const matched = (groups as RansomwareGroup[]).find(g =>
    g.name.toLowerCase() === actorName.toLowerCase() ||
    g.aliases.some(a => a.toLowerCase() === actorName.toLowerCase())
  );
  const { items: victims, isLoading } = useRansomwareVictims(
    matched ? { group_id: matched.id, limit: 200 } : undefined
  );
  const { sorted, sortKey, sortDir, toggle } = useSortable(victims as RansomwareVictim[], 'disclosed_at', 'desc');

  if (!matched) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-4)', fontSize: 12 }}>
        <Skull s={24} />
        <div style={{ marginTop: 12 }}>This actor is not linked to a tracked ransomware group.</div>
        <div style={{ marginTop: 4 }}>
          <a href="/actors/ransomware" style={{ color: 'var(--accent)' }}>Browse all ransomware groups →</a>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Group profile */}
      <div className="card">
        <div className="card-h"><Skull s={13} /><div className="t">Ransomware group profile</div></div>
        <div style={{ padding: '8px 14px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px 20px', fontSize: 12 }}>
          {[
            ['First seen', fmtDate(matched.first_seen)],
            ['Last active', fmtDate(matched.last_seen)],
            ['Variants', matched.variants?.join(', ') || '—'],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-soft)', padding: '4px 0' }}>
              <span style={{ color: 'var(--text-4)' }}>{k}</span>
              <span className="mono" style={{ color: 'var(--text-2)' }}>{v}</span>
            </div>
          ))}
        </div>
        {matched.leak_site_url && (
          <div style={{ padding: '4px 14px 10px' }}>
            <a href={matched.leak_site_url} target="_blank" rel="noopener noreferrer"
               style={{ fontSize: 11.5, color: 'var(--text-4)', display: 'flex', alignItems: 'center', gap: 4 }}>
              Leak site (use with caution) <ExternalLink s={10} />
            </a>
          </div>
        )}
      </div>

      {/* Victims */}
      <div className="card">
        <div className="card-h">
          <AlertTriangle s={13} />
          <div className="t">Known victims</div>
          <div className="s">{victims.length} tracked</div>
        </div>
        <div style={{ overflow: 'auto', maxHeight: 500 }}>
          <table className="tbl">
            <thead><tr>
              <SortHeader label="Date" sortKey="disclosed_at" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 110 }} />
              <SortHeader label="Victim" sortKey="victim_name" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} />
              <SortHeader label="Sector" sortKey="sector" currentKey={sortKey} currentDir={sortDir} onToggle={toggle} style={{ width: 120 }} />
              <th style={{ width: 80 }}>Country</th>
            </tr></thead>
            <tbody>
              {isLoading && <tr><td colSpan={4} style={{ padding: 20, color: 'var(--text-4)' }}>Loading…</td></tr>}
              {!isLoading && sorted.length === 0 && <tr><td colSpan={4} style={{ padding: 20, color: 'var(--text-4)', textAlign: 'center' }}>No victims tracked.</td></tr>}
              {(sorted as RansomwareVictim[]).map(v => (
                <tr key={v.id}>
                  <td className="mono" style={{ fontSize: 11 }}>{fmtDate(v.disclosed_at)}</td>
                  <td className="primary">{v.victim_name}</td>
                  <td><span className="tag" style={{ fontSize: 10 }}>{v.sector ?? '—'}</span></td>
                  <td>{v.country ? <Flag code={v.country} /> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ---- Main page ---- */
export default function ActorDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;
  const [tab, setTab] = useState<TabId>('overview');

  const { data: actor, isLoading } = useOne<ActorDetail>(id ? `/actors/${id}` : null);
  const { items: groups } = useRansomwareGroups();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)' }}>
        Loading actor profile…
      </div>
    );
  }

  if (!actor) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)', gap: 12 }}>
        <div>Actor not found</div>
        <button className="btn" onClick={() => router.back()}><ChevronLeft s={12} />Go back</button>
      </div>
    );
  }

  const ttps = actor.ttps ?? [];
  const tools = actor.tools ?? [];

  // Check if actor matches a ransomware group
  const hasRansomwareGroup = (groups as RansomwareGroup[]).some(g =>
    g.name.toLowerCase() === actor.name.toLowerCase() ||
    g.aliases.some(a => a.toLowerCase() === actor.name.toLowerCase())
  );

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '16px 18px 12px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(180deg, rgba(248,81,73,0.06), transparent 80%)', flexShrink: 0 }}>
        <div style={{ marginBottom: 10 }}>
          <button className="btn sm" onClick={() => router.back()}><ChevronLeft s={11} />Threat Actors</button>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
          {/* Avatar */}
          <div style={{ width: 52, height: 52, borderRadius: 8, background: 'var(--bg-elev)', border: '1px solid var(--border)', display: 'grid', placeItems: 'center', fontSize: 16, fontWeight: 700, color: 'var(--text)', fontFamily: 'var(--mono)', flexShrink: 0 }}>
            {actor.name.slice(0, 2).toUpperCase()}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
              <div style={{ fontSize: 21, fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.015em' }}>{actor.name}</div>
              {actor.mitre_id && <span className="mono" style={{ fontSize: 12, color: 'var(--accent)' }}>{actor.mitre_id}</span>}
              {actor.origin_country && <Flag code={actor.origin_country} />}
              <span className={`badge ${actor.status === 'active' ? 'crit' : 'mute'}`}>
                {actor.status === 'active' && <span className="dot pulse" />}{actor.status}
              </span>
              {hasRansomwareGroup && (
                <span className="badge high" style={{ cursor: 'pointer' }} onClick={() => setTab('ransomware')}>
                  ransomware group
                </span>
              )}
            </div>
            {actor.aliases.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>
                Aliases: <span className="mono" style={{ color: 'var(--text-2)' }}>{actor.aliases.join(' · ')}</span>
              </div>
            )}
            <div style={{ display: 'flex', gap: 5, marginTop: 6, flexWrap: 'wrap' }}>
              {actor.motivation.map(m => <span key={m} className="badge high" style={{ fontSize: 10 }}>{m}</span>)}
              {actor.target_sectors.slice(0, 4).map(s => <span key={s} className="tag" style={{ fontSize: 10 }}>{s}</span>)}
              {actor.target_sectors.length > 4 && <span className="tag" style={{ fontSize: 10 }}>+{actor.target_sectors.length - 4} sectors</span>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <button className="btn sm"><Refresh s={11} />Refresh</button>
            <button className="btn sm"><Pin s={11} />Pin</button>
            <button className="btn primary sm"><GitBranch s={11} />Override</button>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <TabBar active={tab} onChange={setTab} showRansomware={hasRansomwareGroup} />

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {tab === 'overview'   && <OverviewTab actor={actor} tools={tools} />}
        {tab === 'ttps'       && <TTPsTab ttps={ttps} />}
        {tab === 'iocs'       && <IOCsTab actorName={actor.name} />}
        {tab === 'intel'      && <IntelTab actorName={actor.name} />}
        {tab === 'ransomware' && <RansomwareTab actorName={actor.name} />}
      </div>
    </div>
  );
}
