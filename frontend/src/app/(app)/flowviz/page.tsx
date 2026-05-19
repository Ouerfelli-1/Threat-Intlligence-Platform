'use client';

import { useCallback, useState } from 'react';
import { Activity, Play, Refresh, ChevronRight, Download } from '@/components/icons';
import { api } from '@/lib/api';
import AttackFlowGraph from '@/components/shared/AttackFlowGraph';

/* ── types ──────────────────────────────────────────────────────────────────
 *
 * The flowviz backend returns FlowOut shaped like:
 *   { id, input_hash, output: { nodes: [{id,type,data:{label,description,...}}],
 *                                edges: [{id,source,target,type,label}] },
 *     model_name, generated_at }
 *
 * The display label/description/technique_* fields live inside node.data — the
 * ReactFlow convention preserved from the legacy frontend. We unwrap once at
 * render time so the rest of the component stays clean.
 */

interface FlowNodeData {
  label?: string;
  description?: string;
  technique_id?: string;
  technique_name?: string;
  [key: string]: unknown;
}

interface FlowNode {
  id: string;
  type: string;
  data: FlowNodeData;
}

interface FlowEdge {
  id?: string;
  source: string;
  target: string;
  label?: string;
}

interface FlowOutput {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

interface FlowResult {
  id: string;
  output: FlowOutput;
  model_name?: string;
  generated_at?: string;
}

/* ── page ────────────────────────────────────────────────────────────────── */

export default function FlowvizPage() {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FlowResult | null>(null);
  const [error, setError] = useState('');
  const [showRaw, setShowRaw] = useState(false);

  const handleGenerate = useCallback(async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await api.post<FlowResult>('/flows', { input: input.trim() });
      setResult(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to generate attack flow';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [input]);

  const handleExport = useCallback(() => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `attack-flow-${result.id?.slice(0, 8) ?? 'export'}.json`;
    a.click();
  }, [result]);

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Attack flow</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          Describe a threat scenario to generate an ATT&CK attack chain
        </div>
      </div>

      {/* Input area */}
      <div className="card" style={{ marginBottom: 12, padding: 14 }}>
        <textarea
          className="input"
          rows={5}
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Describe the threat scenario, e.g.: 'An APT group sends a spear-phishing email with a macro-enabled document. The macro downloads a second-stage payload via PowerShell, establishes persistence through a scheduled task, then exfiltrates data via encrypted DNS tunneling.'"
          style={{ height: 'auto', padding: 12, fontFamily: 'var(--sans)', width: '100%', fontSize: 13, lineHeight: 1.5, resize: 'vertical' }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
          <button
            className="btn primary"
            onClick={handleGenerate}
            disabled={loading || !input.trim()}
          >
            {loading ? <><Refresh s={12} />Generating...</> : <><Play s={12} />Generate attack flow</>}
          </button>
          {result && (
            <button className="btn" onClick={handleExport}><Download s={12} />Export JSON</button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{ padding: '10px 14px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.25)', borderRadius: 6, marginBottom: 12, color: '#f85149', fontSize: 12.5 }}>
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="card" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center', color: 'var(--text-4)' }}>
            <Activity s={28} />
            <div style={{ marginTop: 10, fontSize: 13 }}>Analyzing threat scenario and mapping to ATT&CK...</div>
            <div style={{ fontSize: 11, marginTop: 4 }}>This may take 10-30 seconds</div>
          </div>
        </div>
      )}

      {/* Result */}
      {!loading && result && (() => {
        const nodes = result.output?.nodes ?? [];
        const edges = result.output?.edges ?? [];
        return (
        <div className="card" style={{ flex: 1, overflow: 'auto', padding: 0 }}>
          <div className="card-h" style={{ padding: '8px 14px' }}>
            <Activity s={13} />
            <div className="t">Attack chain</div>
            <div className="s">{nodes.length} nodes, {edges.length} edges</div>
            <button className="btn sm" style={{ marginLeft: 'auto' }} onClick={() => setShowRaw(r => !r)}>
              {showRaw ? 'Flow view' : 'Raw JSON'}
            </button>
          </div>

          {showRaw ? (
            <pre style={{ padding: 14, fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', margin: 0 }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          ) : (
            <div style={{ padding: 0 }}>
              {/* ReactFlow canvas — pannable, zoomable, dagre auto-layout. */}
              <AttackFlowGraph nodes={nodes} edges={edges} height={620} />

              {/* Edge relationships (if any carry labels) — surfaced below the
                  graph because graph labels are abbreviated on long flows. */}
              {edges.some(e => e.label) && (
                <div style={{ padding: 14 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Relationships</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {edges.filter(e => e.label).map((e, i) => (
                      <div key={e.id ?? i} style={{ fontSize: 11.5, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>{e.source}</span>
                        <ChevronRight s={9} />
                        <span style={{ color: 'var(--text-2)' }}>{e.label}</span>
                        <ChevronRight s={9} />
                        <span className="mono" style={{ fontSize: 10, color: 'var(--text-4)' }}>{e.target}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
        );
      })()}

      {/* Empty state */}
      {!loading && !result && !error && (
        <div className="card" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center', color: 'var(--text-4)' }}>
            <Activity s={32} />
            <div style={{ marginTop: 10, fontSize: 14, fontWeight: 500 }}>Describe a threat to visualize the attack chain</div>
            <div style={{ fontSize: 12, marginTop: 4, maxWidth: 400 }}>
              Enter a threat description above and click Generate. The AI will map it to MITRE ATT&CK techniques and produce a visual attack flow.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
