import { v4 as uuidv4 } from 'uuid';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { ExtractedAttackInfo } from '../types';
import { INodeConverter } from './base/INodeConverter';

export class InfrastructureNodeConverter implements INodeConverter {
  async convertNodes(
    extractedInfo: ExtractedAttackInfo,
    existingNodes: AttackFlowNode[],
    existingEdges: FlowEdge[]
  ): Promise<{ nodes: AttackFlowNode[]; edges: FlowEdge[] }> {
    const nodes: AttackFlowNode[] = [...existingNodes];
    const edges: FlowEdge[] = [...existingEdges];
    
    console.log('=== Creating Infrastructure Nodes ===');
    
    extractedInfo.infrastructure?.forEach((infra, index) => {
      const id = `infrastructure-${index}`;
      
      nodes.push({
        id,
        type: 'infrastructure',
        spec_version: '2.1',
        name: infra.name,
        description: infra.description,
        infrastructure_types: [infra.type || 'server'],
        source_snippet: infra.source_snippet || '',
        confidence: infra.confidence || 'medium',
      });
      
      console.log(`Created infrastructure node: ${infra.name} (${infra.type})`);
      
      this.connectInfrastructureToActions(infra, id, nodes, edges);
    });
    
    return { nodes, edges };
  }
  
  private connectInfrastructureToActions(infra: any, infraId: string, nodes: AttackFlowNode[], edges: FlowEdge[]): void {
    infra.used_by?.forEach((techniqueId: string) => {
      const actionNode = nodes.find(n => n.type === 'attack-action' && n.technique_id === techniqueId);
      if (actionNode) {
        edges.push({
          id: uuidv4(),
          source: actionNode.id,
          target: infraId,
          label: 'Uses'
        });
        console.log(`✅ Connected: Action "${actionNode.name}" uses infrastructure "${infra.name}"`);
      } else {
        console.log(`❌ No action found with technique ID: ${techniqueId} for infrastructure "${infra.name}"`);
      }
    });
  }
}