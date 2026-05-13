import { Node, Edge } from 'reactflow';
import { AttackFlowNode, FlowEdge } from '../types/attack-flow';

export interface FlowVisualizationProps {
  data: {
    nodes: AttackFlowNode[];
    edges: FlowEdge[];
  };
  onExportAvailable?: (exportFn: (format: ExportOptions['format']) => void) => void;
}

export interface DirectFlowVisualizationProps {
  data: {
    nodes: Node[];
    edges: Edge[];
  };
  onExportAvailable?: (exportFn: (format: ExportOptions['format']) => void) => void;
  onClearAvailable?: (clearFn: () => void) => void;
}

export interface LayoutedElements {
  nodes: Node[];
  edges: Edge[];
}

export interface HighlightedElements {
  edges: Edge[];
  nodes: Node[];
}

export interface ExportOptions {
  format: 'png' | 'json' | 'flowviz';
  filename?: string;
}

export interface NodeDetailsProps {
  node: AttackFlowNode;
  onClose: () => void;
}
