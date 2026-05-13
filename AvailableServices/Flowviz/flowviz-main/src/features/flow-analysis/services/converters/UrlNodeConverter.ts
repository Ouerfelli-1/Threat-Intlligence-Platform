import { v4 as uuidv4 } from 'uuid';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { ExtractedAttackInfo } from '../types';
import { INodeConverter } from './base/INodeConverter';

export class UrlNodeConverter implements INodeConverter {
  async convertNodes(
    extractedInfo: ExtractedAttackInfo,
    existingNodes: AttackFlowNode[],
    existingEdges: FlowEdge[]
  ): Promise<{ nodes: AttackFlowNode[]; edges: FlowEdge[] }> {
    const nodes: AttackFlowNode[] = [...existingNodes];
    const edges: FlowEdge[] = [...existingEdges];
    
    console.log('=== Creating URL Nodes ===');
    
    extractedInfo.urls?.forEach((url, index) => {
      const id = `url-${index}`;
      
      nodes.push({
        id,
        type: 'url',
        spec_version: '2.1',
        name: url.name.length > 50 ? url.name.substring(0, 47) + '...' : url.name,
        description: url.description,
        value: url.value || url.name,
        source_snippet: url.source_snippet || '',
        confidence: url.confidence || 'medium',
      });
      
      console.log(`Created URL node: ${url.name}`);
      
      this.connectUrlToActions(url, id, nodes, edges);
    });
    
    return { nodes, edges };
  }
  
  private connectUrlToActions(url: any, urlId: string, nodes: AttackFlowNode[], edges: FlowEdge[]): void {
    url.used_by?.forEach((techniqueId: string) => {
      const actionNode = nodes.find(n => n.type === 'attack-action' && n.technique_id === techniqueId);
      if (actionNode) {
        edges.push({
          id: uuidv4(),
          source: actionNode.id,
          target: urlId,
          label: 'Uses'
        });
        console.log(`✅ Connected: Action "${actionNode.name}" uses URL "${url.name}"`);
      } else {
        console.log(`❌ No action found with technique ID: ${techniqueId} for URL "${url.name}"`);
      }
    });
  }
}