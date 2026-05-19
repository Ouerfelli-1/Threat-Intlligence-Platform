'use client';
/**
 * AttackFlowGraph — renders the flowviz output as a real graph (not a stack
 * of cards under each other).
 *
 * Design choices:
 *   - ReactFlow for the canvas + zooming + minimap + edge routing.
 *   - Dagre for auto-layout: top-to-bottom by default. We rebuild positions
 *     whenever the nodes/edges prop changes so we never persist stale coords.
 *   - Custom node renderer matches the MITRE Attack Flow Builder aesthetic
 *     (colored type header, structured body with description/technique/etc.)
 *     so an analyst familiar with the CTID UI feels at home.
 *   - "Floating" smooth-step edges with arrow markers, mirroring the legacy
 *     Flowviz React app's edge style.
 *
 * Props:
 *   nodes / edges — raw flowviz output. We adapt them once here.
 *   height        — px height of the canvas. Caller controls layout.
 *   readOnly      — disables drag/select; we're a viewer, not an editor.
 */
import { useEffect, useMemo, useState, useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import dagre from 'dagre';

// ReactFlow ships a stylesheet that we must import once globally; the layout
// in (app)/layout.tsx loads it. If you embed AttackFlowGraph somewhere new,
// make sure `import 'reactflow/dist/style.css'` is in scope.

// `data` is intentionally untyped here — flowviz outputs slightly different
// fields depending on the upstream model (label vs name, technique_id vs
// tactic_id, etc.). We pluck what we need defensively inside the renderer.
// Using `unknown` instead of `Record<string, unknown>` so strictly-typed
// upstream interfaces (e.g. the threat detail page's local `FlowNodeData`)
// are structurally compatible.
interface RawFlowNode {
  id: string;
  type: string;
  data?: unknown;
}

interface RawFlowEdge {
  id?: string;
  source: string;
  target: string;
  label?: string;
}

// Color palette modeled on the MITRE Attack Flow Builder header bands.
// Each TYPE → header color. Body is always the elevated card background.
const NODE_COLORS: Record<string, { header: string; accent: string }> = {
  action:         { header: '#1f6feb', accent: '#58a6ff' },
  malware:        { header: '#7d1f1f', accent: '#f85149' },
  tool:           { header: '#5a32a3', accent: '#a371f7' },
  asset:          { header: '#9e6a03', accent: '#d29922' },
  infrastructure: { header: '#9e6a03', accent: '#d29922' },
  vulnerability:  { header: '#9e6a03', accent: '#f0883e' },
  threat_actor:   { header: '#161b22', accent: '#8b949e' },
  process:        { header: '#1f4c8f', accent: '#79c0ff' },
  file:           { header: '#30363d', accent: '#8b949e' },
  url:            { header: '#1f6feb', accent: '#58a6ff' },
  operator:       { header: '#5a32a3', accent: '#bc8cff' },
};

function colorFor(type: string): { header: string; accent: string } {
  return NODE_COLORS[type.toLowerCase()] ?? { header: '#30363d', accent: '#8b949e' };
}

/* ── Custom node component ─────────────────────────────────────────────────
 * One renderer for every node type. We get a "card with a header" — the same
 * visual pattern as the MITRE Attack Flow Builder, where the analyst can
 * scan a graph and read each node's purpose at a glance.
 */
interface FlowCardData {
  id: string;
  type: string;
  data?: Record<string, unknown>;
  _color: { header: string; accent: string };
}

function FlowNodeCard({ data }: NodeProps<FlowCardData>) {
  const color = data._color;
  const d = (data.data ?? {}) as Record<string, unknown>;
  const label = (d.label as string | undefined) ?? (d.name as string | undefined) ?? data.id;
  const desc = d.description as string | undefined;
  const tid = d.technique_id as string | undefined;
  const tname = d.technique_name as string | undefined;
  const tactic = d.tactic_id as string | undefined;

  return (
    <div style={{
      minWidth: 200, maxWidth: 260,
      border: `1px solid ${color.accent}55`,
      borderRadius: 6,
      background: '#0d1117',
      overflow: 'hidden',
      fontSize: 11.5,
      color: '#e6edf3',
      fontFamily: 'var(--sans)',
      boxShadow: '0 2px 8px rgba(0,0,0,0.45)',
    }}>
      <Handle type="target" position={Position.Top} style={{ background: color.accent, width: 7, height: 7, border: 'none' }} />
      <div style={{
        background: color.header,
        padding: '4px 8px',
        fontSize: 9, fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '0.07em',
        color: '#fff',
        opacity: 0.95,
      }}>
        {data.type.replace(/_/g, ' ')}
      </div>
      <div style={{ padding: '7px 9px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ fontWeight: 600, fontSize: 12, lineHeight: 1.3 }}>{label}</div>
        {(tactic || tid) && (
          <div style={{ display: 'flex', gap: 6, fontSize: 9.5, color: '#8b949e', fontFamily: 'var(--mono)' }}>
            {tactic && <span>TACT. {tactic}</span>}
            {tid && <span>TECH. {tid}</span>}
          </div>
        )}
        {tname && !desc && (
          <div style={{ fontSize: 10.5, color: '#8b949e', lineHeight: 1.4 }}>{tname}</div>
        )}
        {desc && (
          <div style={{ fontSize: 10.5, color: '#8b949e', lineHeight: 1.4 }}>
            {tname && <span style={{ color: '#c9d1d9' }}>{tname} — </span>}
            {desc}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: color.accent, width: 7, height: 7, border: 'none' }} />
    </div>
  );
}

const NODE_TYPES = { flowCard: FlowNodeCard };

/* ── Dagre auto-layout ─────────────────────────────────────────────────────
 * We push nodes through dagre to get sensible coordinates. Node size is a
 * worst-case estimate; ReactFlow handles the actual rendering. Top-to-bottom
 * because attack flows read as a kill chain from initial access downward.
 */
function autoLayout(nodes: Node[], edges: Edge[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: 50, ranksep: 70, marginx: 20, marginy: 20 });
  g.setDefaultEdgeLabel(() => ({}));

  const nodeW = 230;
  const nodeH = 110;

  for (const n of nodes) g.setNode(n.id, { width: nodeW, height: nodeH });
  for (const e of edges) g.setEdge(e.source, e.target);

  dagre.layout(g);

  return {
    nodes: nodes.map(n => {
      const pos = g.node(n.id);
      return { ...n, position: { x: pos.x - nodeW / 2, y: pos.y - nodeH / 2 } };
    }),
    edges,
  };
}

export default function AttackFlowGraph({
  nodes: rawNodes,
  edges: rawEdges,
  height = 480,
}: {
  nodes: RawFlowNode[];
  edges: RawFlowEdge[];
  height?: number;
}) {
  // Adapt the raw flow into ReactFlow shapes (one effect on prop change).
  const initial = useMemo(() => {
    const rfNodes: Node[] = rawNodes.map(n => ({
      id: n.id,
      type: 'flowCard',
      position: { x: 0, y: 0 },                  // overridden by dagre below
      data: { ...n, _color: colorFor(n.type) } as Record<string, unknown>,
    }));
    const rfEdges: Edge[] = rawEdges.map((e, i) => ({
      id: e.id ?? `e-${i}`,
      source: e.source,
      target: e.target,
      label: e.label,
      type: 'smoothstep',
      style: { stroke: '#58a6ff', strokeWidth: 1.5 },
      labelStyle: { fontSize: 10, fill: '#8b949e' },
      labelBgStyle: { fill: '#0d1117', fillOpacity: 0.85 },
      markerEnd: { type: MarkerType.ArrowClosed, color: '#58a6ff', width: 16, height: 16 },
    }));
    return autoLayout(rfNodes, rfEdges);
  }, [rawNodes, rawEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  // Re-layout when the prop changes (e.g. user re-analyzes the threat).
  useEffect(() => {
    setNodes(initial.nodes);
    setEdges(initial.edges);
  }, [initial, setNodes, setEdges]);

  // Track ReactFlow's fitView opportunity: trigger once nodes mount.
  const [mounted, setMounted] = useState(false);
  const onInit = useCallback(() => setMounted(true), []);

  if (rawNodes.length === 0) {
    return (
      <div style={{
        height, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#0d1117', border: '1px solid #21262d', borderRadius: 6,
        color: '#484f58', fontSize: 12,
      }}>
        No nodes in this attack flow.
      </div>
    );
  }

  return (
    <div style={{
      height,
      background: '#010409',
      border: '1px solid #21262d',
      borderRadius: 6,
      overflow: 'hidden',
    }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.18, maxZoom: 1.15 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.2}
        maxZoom={2.5}
        nodesDraggable
        elementsSelectable
        zoomOnScroll
        panOnDrag
        // Re-fit when nodes change identity so a re-analyzed flow centres itself.
        key={`flow-${nodes.length}-${edges.length}-${mounted ? 'ready' : 'init'}`}
      >
        <Background gap={20} size={1} color="#21262d" />
        <Controls
          showInteractive={false}
          style={{ background: '#0d1117', border: '1px solid #21262d' }}
        />
        <MiniMap
          nodeColor={n => {
            const raw = (n.data as { _color?: { accent?: string } } | undefined)?._color?.accent;
            return raw ?? '#58a6ff';
          }}
          maskColor="rgba(1,4,9,0.7)"
          style={{ background: '#0d1117', border: '1px solid #21262d' }}
        />
      </ReactFlow>
    </div>
  );
}
