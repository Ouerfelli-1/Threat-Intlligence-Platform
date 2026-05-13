import { useEffect, useMemo, useState } from 'react';
import { useReactFlow, Node, Edge } from 'reactflow';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { getLayoutedElements } from '../utils/layoutUtils';
import { NODE_TYPES, EDGE_STYLES } from '../constants';
import { MarkerType } from 'reactflow';

export const useGraphLayout = (nodes: AttackFlowNode[], edges: FlowEdge[]) => {
  const reactFlowInstance = useReactFlow();

  // Convert nodes to React Flow format
  const flowNodes: Node[] = useMemo(() => {
    return nodes.map((node) => ({
      id: node.id,
      type: node.type as keyof typeof NODE_TYPES,
      data: node,
      position: { x: 0, y: 0 },
      draggable: true,
    }));
  }, [nodes]);

  // Convert edges to React Flow format with styles
  const flowEdges: Edge[] = useMemo(() => {
    return edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: 'default',
      style: EDGE_STYLES.default,
      labelStyle: {
        fontSize: 11,
        fontWeight: 500,
        fill: 'rgba(255, 255, 255, 0.7)',
      },
      labelBgStyle: {
        fill: 'rgba(13, 17, 23, 0.95)',
        fillOpacity: 0.9,
        rx: 3,
        ry: 3,
      },
      labelBgPadding: [4, 6],
      labelBgBorderRadius: 3,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 20,
        height: 20,
        color: 'rgba(255, 255, 255, 0.7)',
      },
    }));
  }, [edges]);

  // Apply layout only once initially, then preserve user modifications
  const [layoutedElements, setLayoutedElements] = useState<{ nodes: Node[], edges: Edge[] }>({ nodes: [], edges: [] });
  
  useEffect(() => {
    if (flowNodes.length === 0) {
      setLayoutedElements({ nodes: [], edges: [] });
      return;
    }
    
    // Only apply automatic layout if not done yet for this data
    const shouldReapplyLayout = layoutedElements.nodes.length === 0 || 
                                layoutedElements.nodes.length !== flowNodes.length;
    
    if (shouldReapplyLayout) {
      const newLayout = getLayoutedElements(flowNodes, flowEdges);
      setLayoutedElements(newLayout);
    }
  }, [flowNodes, flowEdges, layoutedElements.nodes.length]);

  // Fit view when layout changes
  useEffect(() => {
    if (layoutedElements.nodes.length > 0 && reactFlowInstance) {
      setTimeout(() => {
        reactFlowInstance.fitView({ padding: 0.1 });
      }, 50);
    }
  }, [layoutedElements, reactFlowInstance]);

  return layoutedElements;
};