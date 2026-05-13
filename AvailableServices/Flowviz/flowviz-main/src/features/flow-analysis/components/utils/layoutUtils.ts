import dagre from 'dagre';
import { Node, Edge } from 'reactflow';
import { LAYOUT_CONFIG } from '../constants';

export const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  dagreGraph.setGraph({ 
    rankdir: LAYOUT_CONFIG.rankdir,
    ranksep: LAYOUT_CONFIG.ranksep,
    nodesep: LAYOUT_CONFIG.nodesep,
    edgesep: LAYOUT_CONFIG.edgesep,
    marginx: LAYOUT_CONFIG.marginx,
    marginy: LAYOUT_CONFIG.marginy
  });

  // Add nodes with adjusted dimensions
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { 
      width: LAYOUT_CONFIG.nodeWidth, 
      height: LAYOUT_CONFIG.nodeHeight,
      paddingLeft: LAYOUT_CONFIG.paddingLeft,
      paddingRight: LAYOUT_CONFIG.paddingRight
    });
  });

  // Add edges to the graph with weights to prioritize the technique backbone
  edges.forEach((edge) => {
    const sourceNode = nodes.find(n => n.id === edge.source);
    const targetNode = nodes.find(n => n.id === edge.target);
    
    // Give action-to-action edges higher weight to form the main backbone
    const weight = (sourceNode?.type === 'attack-action' && targetNode?.type === 'attack-action') ? 10 : 1;
    
    dagreGraph.setEdge(edge.source, edge.target, { weight });
  });

  // Calculate the layout
  dagre.layout(dagreGraph);

  // Get the positioned nodes with minimal adjustments
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - LAYOUT_CONFIG.nodeWidth / 2,
        y: nodeWithPosition.y - LAYOUT_CONFIG.nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};