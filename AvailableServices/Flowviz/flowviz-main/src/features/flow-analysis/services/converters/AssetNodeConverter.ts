import { v4 as uuidv4 } from 'uuid';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { ExtractedAttackInfo } from '../types';
import { INodeConverter } from './base/INodeConverter';

export class AssetNodeConverter implements INodeConverter {
  async convertNodes(
    extractedInfo: ExtractedAttackInfo,
    existingNodes: AttackFlowNode[],
    existingEdges: FlowEdge[]
  ): Promise<{ nodes: AttackFlowNode[]; edges: FlowEdge[] }> {
    const nodes: AttackFlowNode[] = [...existingNodes];
    const edges: FlowEdge[] = [...existingEdges];
    
    console.log('=== Creating Asset Nodes ===');
    
    extractedInfo.assets?.forEach((asset, index) => {
      const id = `asset-${index}`;
      
      const assetNode: AttackFlowNode = {
        id,
        type: 'asset',
        spec_version: '2.1',
        name: asset.name,
        description: asset.description,
        role: asset.role,
        impact: asset.impact,
        details: asset.details,
        asset_type: asset.asset_type || 'system',
        source_snippet: asset.source_snippet || '',
        confidence: asset.confidence || 'medium',
        affected_by: [],
      };
      
      nodes.push(assetNode);
      console.log(`Created asset node: ${asset.name} (${id})`);
    });
    
    // Create asset-to-asset connections
    this.createAssetConnections(extractedInfo, edges);
    
    return { nodes, edges };
  }
  
  private createAssetConnections(extractedInfo: ExtractedAttackInfo, edges: FlowEdge[]): void {
    extractedInfo.assets?.forEach((asset, index) => {
      const sourceId = `asset-${index}`;
      
      asset.connects_to?.forEach((targetAssetName: string) => {
        // Find the target asset by name
        const targetAssetIndex = extractedInfo.assets?.findIndex(a => a.name === targetAssetName);
        if (targetAssetIndex !== undefined && targetAssetIndex !== -1) {
          const targetId = `asset-${targetAssetIndex}`;
          
          edges.push({
            id: uuidv4(),
            source: sourceId,
            target: targetId,
            label: 'Connects to'
          });
          
          console.log(`Connected assets: ${asset.name} → ${targetAssetName}`);
        }
      });
    });
  }
}