import { AttackFlowNode, FlowEdge } from '../../../types/attack-flow';
import { ExtractedAttackInfo } from '../../types';

export interface INodeConverter {
  convertNodes(
    extractedInfo: ExtractedAttackInfo,
    existingNodes: AttackFlowNode[],
    existingEdges: FlowEdge[]
  ): Promise<{
    nodes: AttackFlowNode[];
    edges: FlowEdge[];
  }>;
}

export interface NodeConverterResult {
  nodes: AttackFlowNode[];
  edges: FlowEdge[];
}