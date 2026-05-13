import { v4 as uuidv4 } from 'uuid';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { ExtractedAttackInfo } from '../types';
import { INodeConverter } from './base/INodeConverter';

export class ToolNodeConverter implements INodeConverter {
  async convertNodes(
    extractedInfo: ExtractedAttackInfo,
    existingNodes: AttackFlowNode[],
    existingEdges: FlowEdge[]
  ): Promise<{ nodes: AttackFlowNode[]; edges: FlowEdge[] }> {
    const nodes: AttackFlowNode[] = [...existingNodes];
    const edges: FlowEdge[] = [...existingEdges];
    
    console.log('=== Creating Tool Nodes ===');
    
    extractedInfo.tools?.forEach((tool, index) => {
      const id = `tool-${index}`;
      
      nodes.push({
        id,
        type: 'tool',
        spec_version: '2.1',
        name: tool.name,
        description: tool.description,
        command_line: tool.command_line && tool.command_line.trim() ? tool.command_line : undefined,
        tool_types: [tool.tool_type || 'software'],
        source_snippet: tool.source_snippet || '',
        confidence: tool.confidence || 'medium',
      });
      
      console.log(`Created tool node: ${tool.name} (command: ${tool.command_line || 'none'})`);
      
      this.connectToolToActions(tool, id, nodes, edges);
      this.connectToolToAssets(tool, id, nodes, edges);
    });
    
    return { nodes, edges };
  }
  
  private connectToolToActions(tool: any, toolId: string, nodes: AttackFlowNode[], edges: FlowEdge[]): void {
    tool.used_by?.forEach((techniqueId: string) => {
      const actionNode = nodes.find(n => n.type === 'attack-action' && n.technique_id === techniqueId);
      if (actionNode) {
        edges.push({
          id: uuidv4(),
          source: actionNode.id,
          target: toolId,
          label: 'Uses'
        });
        console.log(`✅ Connected: Action "${actionNode.name}" uses tool "${tool.name}"`);
      } else {
        console.log(`❌ No action found with technique ID: ${techniqueId} for tool "${tool.name}"`);
      }
    });
  }
  
  private connectToolToAssets(tool: any, toolId: string, nodes: AttackFlowNode[], edges: FlowEdge[]): void {
    tool.targets_assets?.forEach((assetName: string) => {
      const assetNode = nodes.find(n => n.type === 'asset' && n.name === assetName);
      if (assetNode) {
        edges.push({
          id: uuidv4(),
          source: toolId,
          target: assetNode.id,
          label: 'Targets'
        });
        console.log(`Tool "${tool.name}" targets asset "${assetName}"`);
      }
    });
  }
}