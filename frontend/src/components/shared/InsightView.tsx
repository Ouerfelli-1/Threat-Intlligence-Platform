'use client';
/**
 * InsightView — shared renderer for the v2 threat/actor insight payload.
 *
 * Shape (produced by threat-intel /threats/{id}/analyze AND threat-actors
 * /actors/{id}/analyze):
 *   {
 *     iocs_extracted:        [{type, value, context, confidence?}, ...]
 *     hunting_hypothesis:    {hypothesis, wazuh_rule, key_artifacts:[{name,note}],
 *                              mitre_techniques:[]}
 *     attack_flow:           {id, output:{nodes,edges}}    (flowviz shape)
 *     source_blob_excerpt:   string                         (for debugging)
 *     *_error:               optional per-section error string
 *     *_carried_over:        optional bool — true when a leg failed and the
 *                             cached previous result was reused
 *   }
 *
 * `confidence` on individual IOCs intentionally NOT rendered (operator
 * dropped numeric confidence metrics platform-wide).
 *
 * Old payloads (v1, or shapes that don't match this contract) fall through
 * to a JSON dump so nothing renders as `[object Object]`.
 */
import { Refresh } from '@/components/icons';
import AttackFlowGraph from '@/components/shared/AttackFlowGraph';

export interface IocRow {
  type: string;
  value: string;
  context?: string;
  // confidence field still arrives from backend but is no longer rendered.
}
export interface KeyArtifact { name: string; note?: string; }
export interface HuntingHypothesis {
  hypothesis?: string;
  wazuh_rule?: string;
  key_artifacts?: KeyArtifact[];
  mitre_techniques?: string[];
}
interface FlowNodeData { label?: string; description?: string; technique_id?: string; technique_name?: string; }
export interface FlowNode { id: string; type: string; data?: FlowNodeData; }
export interface FlowEdge { id?: string; source: string; target: string; label?: string; }
export interface AttackFlow { id?: string; output?: { nodes?: FlowNode[]; edges?: FlowEdge[] }; }

export interface InsightPayload {
  iocs_extracted?: IocRow[];
  hunting_hypothesis?: HuntingHypothesis;
  attack_flow?: AttackFlow;
  iocs_extracted_error?: string;
  hunting_hypothesis_error?: string;
  hunting_hypothesis_carried_over?: boolean;
  iocs_extracted_carried_over?: boolean;
  attack_flow_carried_over?: boolean;
  [k: string]: unknown;
}

export interface InsightEnvelope {
  payload: InsightPayload;
  analyst_override: Record<string, unknown> | null;
  model_name: string;
  prompt_version: string;
  generated_at: string;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

const IOC_COLOR: Record<string, string> = {
  ip:          '#58a6ff',
  domain:      '#a371f7',
  url:         '#a371f7',
  email:       '#d29922',
  hash_md5:    '#f0883e',
  hash_sha1:   '#f0883e',
  hash_sha256: '#f85149',
  cve:         '#3fb950',
};

export default function InsightView({
  insight,
  analyzing,
  onReanalyze,
  flowHeight = 420,
}: {
  insight: InsightEnvelope;
  analyzing: boolean;
  onReanalyze: () => void;
  flowHeight?: number;
}) {
  const p = insight.payload ?? {};
  const iocs = p.iocs_extracted ?? [];
  const hh = p.hunting_hypothesis ?? {};
  const flow = p.attack_flow ?? {};
  const nodes = flow.output?.nodes ?? [];
  const edges = flow.output?.edges ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {insight.analyst_override && (
        <div style={{ padding: '8px 10px', background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.25)', borderRadius: 6, fontSize: 12 }}>
          <div style={{ fontWeight: 600, color: '#d29922', marginBottom: 4 }}>Analyst Override</div>
          <pre style={{ fontSize: 11, color: 'var(--text-2)', margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)' }}>
            {JSON.stringify(insight.analyst_override, null, 2)}
          </pre>
        </div>
      )}

      {/* Hunting hypothesis — top of the panel because it's the most actionable. */}
      {hh.hypothesis && (
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
            Hunting hypothesis
            {p.hunting_hypothesis_carried_over && (
              <span style={{ marginLeft: 8, color: 'var(--text-4)', textTransform: 'none', letterSpacing: 0 }}>
                · carried over from previous run
              </span>
            )}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.55 }}>{hh.hypothesis}</div>
          {hh.mitre_techniques && hh.mitre_techniques.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {hh.mitre_techniques.map(t => (
                <a key={t}
                   href={`https://attack.mitre.org/techniques/${t.replace('.', '/')}/`}
                   target="_blank" rel="noreferrer"
                   className="tag mono"
                   style={{ background: 'rgba(88,166,255,0.10)', color: '#58a6ff', border: '1px solid rgba(88,166,255,0.3)', textDecoration: 'none' }}
                >{t}</a>
              ))}
            </div>
          )}
        </div>
      )}

      {hh.key_artifacts && hh.key_artifacts.length > 0 && (
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
            Key artifacts to hunt
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {hh.key_artifacts.map((k, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                <span className="mono" style={{ fontSize: 11.5, color: 'var(--accent)' }}>{k.name}</span>
                {k.note && <span style={{ fontSize: 11.5, color: 'var(--text-3)' }}>{k.note}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {hh.wazuh_rule && (
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
            Wazuh rule
            <button
              className="btn sm"
              style={{ marginLeft: 'auto', padding: '2px 6px' }}
              onClick={() => navigator.clipboard.writeText(hh.wazuh_rule ?? '')}
              title="Copy"
            >Copy</button>
          </div>
          <pre style={{ fontSize: 11, color: 'var(--text-2)', margin: 0, padding: '8px 10px', background: 'var(--bg-page)', border: '1px solid var(--border-soft)', borderRadius: 4, whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)' }}>
            {hh.wazuh_rule}
          </pre>
        </div>
      )}

      {/* IOCs extracted */}
      {iocs.length > 0 ? (
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
            IOCs extracted ({iocs.length})
            {p.iocs_extracted_carried_over && (
              <span style={{ marginLeft: 8, color: 'var(--text-4)', textTransform: 'none', letterSpacing: 0 }}>
                · carried over from previous run
              </span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {iocs.map((ioc, i) => {
              const color = IOC_COLOR[ioc.type] ?? 'var(--text-3)';
              return (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '90px 1fr', gap: 8, padding: '4px 0', borderBottom: i < iocs.length - 1 ? '1px solid var(--border-soft)' : 'none', alignItems: 'baseline' }}>
                  <span className="mono" style={{ fontSize: 10, color, fontWeight: 600 }}>{ioc.type}</span>
                  <div>
                    <span className="mono" style={{ fontSize: 11.5, color: 'var(--text)', wordBreak: 'break-all' }}>{ioc.value}</span>
                    {ioc.context && (
                      <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 2, lineHeight: 1.4 }}>{ioc.context}</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : p.iocs_extracted_error ? (
        <div className="card" style={{ padding: 12, fontSize: 11.5, color: '#f85149' }}>
          IOC extraction failed: {p.iocs_extracted_error}
        </div>
      ) : null}

      {/* Attack flow — ReactFlow graph (pannable + dagre auto-layout). */}
      {nodes.length > 0 && (
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
            Attack flow ({nodes.length} nodes · {edges.length} edges)
            {p.attack_flow_carried_over && (
              <span style={{ marginLeft: 8, color: 'var(--text-4)', textTransform: 'none', letterSpacing: 0 }}>
                · carried over from previous run
              </span>
            )}
          </div>
          <AttackFlowGraph nodes={nodes} edges={edges} height={flowHeight} />
        </div>
      )}

      {/* Backward compat: shapes that don't match v2 fall through to raw JSON. */}
      {!hh.hypothesis && iocs.length === 0 && nodes.length === 0 && (
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Raw payload</div>
          <pre style={{ fontSize: 10.5, color: 'var(--text-3)', margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)' }}>{JSON.stringify(p, null, 2)}</pre>
        </div>
      )}

      {/* Footer: just the timestamp. Model name + prompt version intentionally
          omitted (operator: not user-facing metadata). */}
      <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 4 }}>
        {fmtDate(insight.generated_at)}
      </div>
      <button className="btn sm" onClick={onReanalyze} disabled={analyzing} style={{ alignSelf: 'flex-start' }}>
        <Refresh s={11} />{analyzing ? 'Re-analyzing...' : 'Re-analyze'}
      </button>
    </div>
  );
}
