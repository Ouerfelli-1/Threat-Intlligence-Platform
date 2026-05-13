import { useState, useCallback, useRef } from 'react';
import { Node, Edge } from 'reactflow';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { FlowConverterRefactored } from '../../services';
import { StreamingProgressUpdate, ExtractedAttackInfo } from '../../services/types';
import { getLayoutedElements } from '../utils/layoutUtils';

export interface StreamingGraphState {
  nodes: Node[];
  edges: Edge[];
  isStreaming: boolean;
  currentSection: string | null;
  error: string | null;
  accumulatedJson: string;
}

export interface UseStreamingGraphResult {
  graphState: StreamingGraphState;
  processStreamingUpdate: (update: StreamingProgressUpdate) => void;
  resetGraph: () => void;
}

export function useStreamingGraph(): UseStreamingGraphResult {
  const [graphState, setGraphState] = useState<StreamingGraphState>({
    nodes: [],
    edges: [],
    isStreaming: false,
    currentSection: null,
    error: null,
    accumulatedJson: ''
  });

  const flowConverter = useRef(new FlowConverterRefactored());
  const processedSections = useRef(new Set<string>());

  const resetGraph = useCallback(() => {
    setGraphState({
      nodes: [],
      edges: [],
      isStreaming: false,
      currentSection: null,
      error: null,
      accumulatedJson: ''
    });
    processedSections.current.clear();
  }, []);

  const processStreamingUpdate = useCallback(async (update: StreamingProgressUpdate) => {
    console.log('🔄 Processing streaming update:', update.type);

    switch (update.type) {
      case 'json_partial':
        setGraphState(prev => ({
          ...prev,
          isStreaming: true,
          accumulatedJson: update.accumulatedJson || '',
          error: null
        }));
        break;

      case 'section_complete':
        if (update.sectionName && update.data && !processedSections.current.has(update.sectionName)) {
          console.log(`✅ New section complete: ${update.sectionName}`);
          processedSections.current.add(update.sectionName);

          try {
            // Convert the new section data to nodes and edges
            const { nodes: attackFlowNodes, edges: attackFlowEdges } = await flowConverter.current.convertToAttackFlow(update.data as ExtractedAttackInfo);
            
            setGraphState(prev => {
              // Merge new nodes with existing ones
              const allNodes = [...prev.nodes];
              const allEdges = [...prev.edges];
              
              // Convert AttackFlowNode[] to React Flow Node[] format
              const newNodes: Node[] = attackFlowNodes.map((node, index) => ({
                id: node.id || `node-${index}`,
                type: node.type,
                data: {
                  ...node,
                  isNewNode: true // Flag for animation
                },
                position: { x: 0, y: 0 } // Will be set by layout
              }));
              
              // Add new nodes
              newNodes.forEach(node => {
                // Check if node already exists
                const existingNodeIndex = allNodes.findIndex(n => n.id === node.id);
                if (existingNodeIndex === -1) {
                  allNodes.push(node);
                }
              });

              // Convert FlowEdge[] to React Flow Edge[] format
              const newEdges: Edge[] = attackFlowEdges.map((edge, index) => ({
                id: edge.id || `edge-${index}`,
                source: edge.source,
                target: edge.target,
                label: edge.label,
                type: 'default'
              }));
              
              // Add new edges
              newEdges.forEach(edge => {
                const existingEdgeIndex = allEdges.findIndex(e => e.id === edge.id);
                if (existingEdgeIndex === -1) {
                  allEdges.push(edge);
                }
              });

              // Apply layout to all nodes
              const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(allNodes, allEdges);

              return {
                ...prev,
                nodes: layoutedNodes,
                edges: layoutedEdges,
                currentSection: update.sectionName || null,
                isStreaming: true
              };
            });

            // Trigger fade-in animation for new nodes
            setTimeout(() => {
              setGraphState(prev => ({
                ...prev,
                nodes: prev.nodes.map(node => ({
                  ...node,
                  data: {
                    ...node.data,
                    isNewNode: false
                  }
                }))
              }));
            }, 50);

          } catch (error) {
            console.error('❌ Error processing section:', error);
            setGraphState(prev => ({
              ...prev,
              error: error instanceof Error ? error.message : 'Unknown error'
            }));
          }
        }
        break;

      case 'complete':
        console.log('✅ Streaming complete');
        
        // If no sections processed yet, process final data all at once
        if (update.data && processedSections.current.size === 0) {
          console.log('🔄 No sections parsed during streaming, processing final data...');
          try {
            const { nodes: attackFlowNodes, edges: attackFlowEdges } = await flowConverter.current.convertToAttackFlow(update.data as ExtractedAttackInfo);
            
            // Convert AttackFlowNode[] to React Flow Node[] format
            const reactFlowNodes: Node[] = attackFlowNodes.map((node, index) => ({
              id: node.id || `node-${index}`,
              type: node.type,
              data: node,
              position: { x: 0, y: 0 }
            }));
            
            // Convert FlowEdge[] to React Flow Edge[] format
            const reactFlowEdges: Edge[] = attackFlowEdges.map((edge, index) => ({
              id: edge.id || `edge-${index}`,
              source: edge.source,
              target: edge.target,
              label: edge.label,
              type: 'default'
            }));
            
            setGraphState(prev => {
              const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(reactFlowNodes, reactFlowEdges);
              return {
                ...prev,
                nodes: layoutedNodes,
                edges: layoutedEdges,
                isStreaming: false,
                currentSection: null
              };
            });
          } catch (error) {
            console.error('❌ Error processing final data:', error);
            setGraphState(prev => ({
              ...prev,
              error: error instanceof Error ? error.message : 'Unknown error',
              isStreaming: false,
              currentSection: null
            }));
          }
        } else {
          setGraphState(prev => ({
            ...prev,
            isStreaming: false,
            currentSection: null
          }));
        }
        break;

      case 'error':
        console.error('❌ Streaming error:', update.error);
        setGraphState(prev => ({
          ...prev,
          isStreaming: false,
          error: update.error || 'Unknown error',
          currentSection: null
        }));
        break;
    }
  }, []);

  return {
    graphState,
    processStreamingUpdate,
    resetGraph
  };
}