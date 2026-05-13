import { AttackFlowNode, FlowEdge } from '../types/attack-flow';
import { ExtractedAttackInfo } from './types';
import {
  AssetNodeConverter,
  ActionNodeConverter,
  ToolNodeConverter,
  VulnerabilityNodeConverter,
  MalwareNodeConverter,
  InfrastructureNodeConverter,
  UrlNodeConverter,
  OperatorNodeConverter
} from './converters';
import type { INodeConverter } from './converters';

export class FlowConverterRefactored {
  private converters: INodeConverter[];
  
  constructor(apiKey?: string) {
    // Initialize converters in the order they should be processed
    // Assets first, then actions, then other supporting nodes
    this.converters = [
      new AssetNodeConverter(),
      new ActionNodeConverter(),
      new OperatorNodeConverter(),
      new VulnerabilityNodeConverter(),
      new ToolNodeConverter(),
      new MalwareNodeConverter(),
      new InfrastructureNodeConverter(),
      new UrlNodeConverter(),
    ];
  }

  async convertToAttackFlow(extractedInfo: ExtractedAttackInfo): Promise<{ nodes: AttackFlowNode[], edges: FlowEdge[] }> {
    console.log('=== CONVERT TO ATTACK FLOW: Starting Conversion (Refactored) ===');
    
    let nodes: AttackFlowNode[] = [];
    let edges: FlowEdge[] = [];
    
    // Process each converter in sequence
    for (const converter of this.converters) {
      try {
        const result = await converter.convertNodes(extractedInfo, nodes, edges);
        nodes = result.nodes;
        edges = result.edges;
      } catch (error) {
        console.error(`Error in converter ${converter.constructor.name}:`, error);
        // Continue with other converters even if one fails
      }
    }
    
    this.logFinalStatistics(nodes, edges);
    
    return { nodes, edges };
  }

  private logFinalStatistics(nodes: AttackFlowNode[], edges: FlowEdge[]): void {
    console.log('=== ATTACK FLOW CONVERSION COMPLETE (Refactored) ===');
    console.log('=== Final Node Statistics ===');
    console.log(`Total nodes created: ${nodes.length}`);
    console.log('Node breakdown:');
    
    // Count nodes by type
    const nodeTypeCounts = nodes.reduce((acc, node) => {
      acc[node.type] = (acc[node.type] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    Object.entries(nodeTypeCounts).forEach(([type, count]) => {
      console.log(`- ${type} nodes: ${count}`);
    });
    
    console.log(`Total edges created: ${edges.length}`);
    console.log('Edge breakdown:');
    
    // Count edges by label
    const edgeTypeCounts = edges.reduce((acc, edge) => {
      acc[edge.label] = (acc[edge.label] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    Object.entries(edgeTypeCounts).forEach(([label, count]) => {
      console.log(`- ${label}: ${count}`);
    });
  }
}