import { v4 as uuidv4 } from 'uuid';
import { AttackFlowNode, FlowEdge } from '../../types/attack-flow';
import { ExtractedAttackInfo } from '../types';
import { INodeConverter } from './base/INodeConverter';

export class OperatorNodeConverter implements INodeConverter {
  async convertNodes(
    extractedInfo: ExtractedAttackInfo,
    existingNodes: AttackFlowNode[],
    existingEdges: FlowEdge[]
  ): Promise<{ nodes: AttackFlowNode[]; edges: FlowEdge[] }> {
    const nodes: AttackFlowNode[] = [...existingNodes];
    const edges: FlowEdge[] = [...existingEdges];
    
    console.log('=== Creating Operator Nodes ===');
    
    extractedInfo.operators?.forEach((operator, index) => {
      const id = `operator-${index}`;
      
      nodes.push({
        id,
        type: operator.operator === 'AND' ? 'AND_operator' : 'OR_operator',
        spec_version: '2.1',
        name: operator.name || `Operator ${index + 1}`,
        operator: operator.operator,
      });
      
      console.log(`Created operator node: ${operator.name} (${operator.operator})`);
      
      // Connect input conditions to operator
      this.connectOperatorInputs(operator, id, nodes, edges);
      
      // Connect operator to output actions
      this.connectOperatorOutputs(operator, id, nodes, edges);
    });
    
    return { nodes, edges };
  }
  
  private connectOperatorInputs(operator: any, operatorId: string, nodes: AttackFlowNode[], edges: FlowEdge[]): void {
    operator.input_conditions?.forEach((conditionName: string) => {
      const conditionNode = nodes.find(n => 
        (n.type === 'AND_operator' || n.type === 'OR_operator') && n.name === conditionName
      );
      if (conditionNode) {
        edges.push({
          id: uuidv4(),
          source: conditionNode.id,
          target: operatorId,
          label: 'Feeds into'
        });
        console.log(`Connected condition "${conditionName}" to operator "${operator.name}"`);
      }
    });
  }
  
  private connectOperatorOutputs(operator: any, operatorId: string, nodes: AttackFlowNode[], edges: FlowEdge[]): void {
    operator.output_actions?.forEach((actionTechniqueId: string) => {
      const actionNode = nodes.find(n => 
        n.type === 'attack-action' && n.technique_id === actionTechniqueId
      );
      if (actionNode) {
        edges.push({
          id: uuidv4(),
          source: operatorId,
          target: actionNode.id,
          label: operator.operator === 'AND' ? 'All required for' : 'Enables'
        });
        console.log(`Connected operator "${operator.name}" to action "${actionNode.name}"`);
      }
    });
  }
}