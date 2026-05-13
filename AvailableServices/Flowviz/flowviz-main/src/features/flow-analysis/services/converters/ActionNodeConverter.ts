import { v4 as uuidv4 } from 'uuid';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { ExtractedAttackInfo } from '../types';
import { TACTIC_DEFINITIONS } from '../config';
import { INodeConverter } from './base/INodeConverter';

export interface TacticResult {
  key: string;
  prefix: string;
  count: number;
  firstActionId: string;
  lastActionId: string;
}

export class ActionNodeConverter implements INodeConverter {
  private processedActions: Map<string, string> = new Map();

  async convertNodes(
    extractedInfo: ExtractedAttackInfo,
    existingNodes: AttackFlowNode[],
    existingEdges: FlowEdge[]
  ): Promise<{ nodes: AttackFlowNode[]; edges: FlowEdge[] }> {
    const nodes: AttackFlowNode[] = [...existingNodes];
    const edges: FlowEdge[] = [...existingEdges];
    
    this.processedActions.clear();
    
    const createdTactics = await this.createActionNodes(extractedInfo, nodes, edges);
    this.connectTactics(createdTactics, extractedInfo, edges);
    
    return { nodes, edges };
  }
  
  async createActionNodes(
    extractedInfo: ExtractedAttackInfo,
    nodes: AttackFlowNode[],
    edges: FlowEdge[]
  ): Promise<TacticResult[]> {
    const presentTactics = this.determinePresentTactics(extractedInfo);
    const tacticalOrder = this.sortTacticsLogically(presentTactics, extractedInfo);
    
    console.log('=== Dynamic Tactical Ordering ===');
    console.log('Tactics present in this attack:');
    tacticalOrder.forEach((tactic, index) => {
      const actions = extractedInfo[tactic.key as keyof ExtractedAttackInfo] as any[];
      console.log(`${index + 1}. ${tactic.key} (${tactic.tacticId}): ${actions?.length || 0} actions`);
    });

    const createdTactics: TacticResult[] = [];
    let globalActionIndex = 0;

    for (const { key, prefix, tacticId } of tacticalOrder) {
      const actions = extractedInfo[key as keyof ExtractedAttackInfo] as any[];
      if (!actions?.length) continue;

      console.log(`=== Creating ${key} nodes ===`);
      console.log(`Processing ${actions.length} ${key} actions`);

      let firstActionId = '';
      let currentLastActionId = '';
      let deduplicatedCount = 0;

      for (let index = 0; index < actions.length; index++) {
        const action = actions[index];
        const actionHash = `${action.technique || ''}_${(action.description || '').toLowerCase().trim()}`;
        const existingNodeId = this.processedActions.get(actionHash);
        
        let id: string;
        if (existingNodeId && action.technique) {
          id = existingNodeId;
          deduplicatedCount++;
          console.log(`Deduplicating action: ${action.name} (reusing ${id})`);
        } else {
          id = await this.createActionNode(action, globalActionIndex, tacticId, extractedInfo, nodes, edges);
          if (action.technique) {
            this.processedActions.set(actionHash, id);
          }
          globalActionIndex++;
        }
        
        if (index === 0) {
          firstActionId = id;
        }
        
        // Connect sequential actions within the same tactic
        if (index > 0 && currentLastActionId !== id) {
          const shouldConnect = this.shouldConnectSequentialActionsHeuristic(actions[index - 1], action, index === 1);
          const edgeExists = edges.some(e => e.source === currentLastActionId && e.target === id);
          
          if (shouldConnect.connect && !edgeExists) {
            edges.push({
              id: uuidv4(),
              source: currentLastActionId,
              target: id,
              label: shouldConnect.relationshipType
            });
            console.log(`Connected sequential actions: ${currentLastActionId} -> ${id} (${shouldConnect.relationshipType}, confidence: ${shouldConnect.confidence})`);
          }
        }
        
        currentLastActionId = id;
      }
      
      createdTactics.push({ 
        key, 
        prefix, 
        count: actions.length - deduplicatedCount, 
        firstActionId, 
        lastActionId: currentLastActionId 
      });
      console.log(`Completed ${key} nodes: ${actions.length - deduplicatedCount} unique nodes created (${deduplicatedCount} duplicates removed)`);
    }

    return createdTactics;
  }

  private determinePresentTactics(extractedInfo: ExtractedAttackInfo) {
    return TACTIC_DEFINITIONS.filter(tactic => {
      const actions = extractedInfo[tactic.key as keyof ExtractedAttackInfo] as any[];
      return actions && actions.length > 0;
    });
  }

  private sortTacticsLogically(presentTactics: typeof TACTIC_DEFINITIONS[number][], extractedInfo: ExtractedAttackInfo) {
    return presentTactics.sort((a, b) => {
      const aActions = extractedInfo[a.key as keyof ExtractedAttackInfo] as any[];
      const bActions = extractedInfo[b.key as keyof ExtractedAttackInfo] as any[];
      
      if (!aActions?.length || !bActions?.length) return 0;
      
      // Check for temporal indicators
      const aHasEarly = aActions.some(action => 
        action.description?.toLowerCase().includes('first') || 
        action.description?.toLowerCase().includes('initial') ||
        action.description?.toLowerCase().includes('began') ||
        action.description?.toLowerCase().includes('started')
      );
      
      const bHasEarly = bActions.some(action => 
        action.description?.toLowerCase().includes('first') || 
        action.description?.toLowerCase().includes('initial') ||
        action.description?.toLowerCase().includes('began') ||
        action.description?.toLowerCase().includes('started')
      );
      
      if (aHasEarly && !bHasEarly) return -1;
      if (!aHasEarly && bHasEarly) return 1;
      
      // Fall back to standard MITRE ordering
      const aIndex = TACTIC_DEFINITIONS.findIndex(t => t.key === a.key);
      const bIndex = TACTIC_DEFINITIONS.findIndex(t => t.key === b.key);
      return aIndex - bIndex;
    });
  }

  private async createActionNode(
    action: any, 
    index: number, 
    tacticId?: string, 
    extractedInfo?: ExtractedAttackInfo,
    nodes?: AttackFlowNode[],
    edges?: FlowEdge[]
  ): Promise<string> {
    const id = `action-${index}`;
    
    const targetedAssets = this.getTargetedAssets(action, extractedInfo);
    
    const actionNode: AttackFlowNode = {
      id,
      type: 'attack-action',
      spec_version: '2.1',
      name: action.name || `Action ${index + 1}`,
      description: action.description || 'No description available',
      technique_id: action.technique || action.technique_id,
      tactic_id: tacticId,
      tactic_name: action.tacticName || action.tactic,
      source_excerpt: action.source_snippet || '',
      confidence: action.confidence || 'medium',
      targeted_assets: targetedAssets,
      asset_impact_level: (targetedAssets.length > 0 ? 
        (targetedAssets.length > 2 ? 'high' : 'medium') : 'low') as 'low' | 'medium' | 'high'
    };
    
    nodes?.push(actionNode);
    console.log(`Created action node: ${actionNode.name}`, {
      technique_id: actionNode.technique_id,
      tactic: actionNode.tactic_name,
      targets_assets: targetedAssets.length,
      targeted_asset_ids: targetedAssets
    });
    
    // Create edges to targeted assets
    if (nodes && edges) {
      await this.connectToTargetedAssets(id, targetedAssets, actionNode, nodes, edges);
    }
    
    return id;
  }

  private getTargetedAssets(action: any, extractedInfo?: ExtractedAttackInfo): string[] {
    const targetedAssets: string[] = [];
    
    // First priority: Use explicit targets_assets from Claude
    if (action.targets_assets && Array.isArray(action.targets_assets)) {
      action.targets_assets.forEach((targetAssetName: string) => {
        // Find matching asset by name
        extractedInfo?.assets?.forEach((asset, assetIndex) => {
          if (asset.name && asset.name.toLowerCase() === targetAssetName.toLowerCase()) {
            targetedAssets.push(`asset-${assetIndex}`);
            console.log(`✅ Action "${action.name}" explicitly targets asset: ${asset.name} (asset-${assetIndex})`);
          }
        });
      });
    }
    
    // Fallback: Try to infer from action description if no explicit targets
    if (targetedAssets.length === 0) {
      const description = (action.description || '').toLowerCase();
      
      extractedInfo?.assets?.forEach((asset, assetIndex) => {
        const assetName = (asset.name || '').toLowerCase();
        
        // Check if action mentions this asset directly
        if (description.includes(assetName)) {
          targetedAssets.push(`asset-${assetIndex}`);
          console.log(`🔍 Action "${action.name}" inferred to target asset: ${asset.name} (asset-${assetIndex})`);
        }
      });
    }
    
    return targetedAssets;
  }

  private async connectToTargetedAssets(
    actionId: string, 
    targetedAssets: string[], 
    actionNode: AttackFlowNode,
    nodes: AttackFlowNode[],
    edges: FlowEdge[]
  ): Promise<void> {
    if (targetedAssets.length === 0) return;
    
    targetedAssets.forEach(assetId => {
      const assetNode = nodes.find(node => node.id === assetId);
      if (!assetNode) return;
      
      edges.push({
        id: uuidv4(),
        source: actionId,
        target: assetId,
        label: 'Targets',
      });
      
      if (assetNode && assetNode.type === 'asset') {
        if (!assetNode.affected_by) {
          assetNode.affected_by = [];
        }
        assetNode.affected_by.push(actionId);
        console.log(`Action ${actionNode.name} targets asset ${assetNode.name}`);
      }
    });
  }

  private connectTactics(createdTactics: TacticResult[], extractedInfo: ExtractedAttackInfo, edges: FlowEdge[]): void {
    console.log('=== Creating Inter-Tactic Connections ===');
    for (let i = 0; i < createdTactics.length - 1; i++) {
      const currentTactic = createdTactics[i];
      const nextTactic = createdTactics[i + 1];
      
      // Only create direct connections if there are no operators managing the flow
      const hasOperatorFlow = extractedInfo.operators && extractedInfo.operators.length > 0;
      
      if (!hasOperatorFlow) {
        edges.push({
          id: `${currentTactic.prefix}-to-${nextTactic.prefix}`,
          source: currentTactic.lastActionId,
          target: nextTactic.firstActionId,
          label: 'Followed by'
        });
        
        console.log(`Connected tactics: ${currentTactic.lastActionId} -> ${nextTactic.firstActionId}`);
      }
    }
  }

  private shouldConnectSequentialActionsHeuristic(
    prevAction: any, 
    currentAction: any, 
    isFirstConnection: boolean
  ): { connect: boolean, relationshipType: string, confidence: number } {
    // Simple heuristic fallback - connect sequential actions with medium confidence
    return { 
      connect: true, 
      relationshipType: 'Followed by', 
      confidence: 0.7 
    };
  }
}