import { useState, useCallback } from 'react';
import { Node, Edge } from 'reactflow';
import { AttackFlowNode } from '../../types/attack-flow';
import { HighlightedElements } from '../types';

export const useNodeSelection = () => {
  const [selectedNode, setSelectedNode] = useState<AttackFlowNode | null>(null);
  const [highlightedElements, setHighlightedElements] = useState<HighlightedElements>({
    nodes: [],
    edges: []
  });

  const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.data as AttackFlowNode);
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null);
    setHighlightedElements({ nodes: [], edges: [] });
  }, []);

  const closeNodeDetails = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const highlightConnectedElements = useCallback(
    (nodeId: string, nodes: Node[], edges: Edge[]) => {
      const connectedEdges = edges.filter(
        (edge) => edge.source === nodeId || edge.target === nodeId
      );
      
      const connectedNodeIds = new Set<string>();
      connectedEdges.forEach((edge) => {
        connectedNodeIds.add(edge.source);
        connectedNodeIds.add(edge.target);
      });
      
      const connectedNodes = nodes.filter((node) => 
        connectedNodeIds.has(node.id)
      );

      setHighlightedElements({
        nodes: connectedNodes,
        edges: connectedEdges
      });
    },
    []
  );

  return {
    selectedNode,
    highlightedElements,
    handleNodeClick,
    handlePaneClick,
    closeNodeDetails,
    highlightConnectedElements
  };
};