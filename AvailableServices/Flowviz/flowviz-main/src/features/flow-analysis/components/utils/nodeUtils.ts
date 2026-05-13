import { 
  AttackFlowNode, 
  AttackAction, 
  AttackAsset, 
  AttackCondition, 
  AttackOperator,
  Tool,
  Infrastructure
} from '../../types/attack-flow';
import { TACTIC_NAMES } from '../constants';

// Type guards
export const isAttackAction = (node: AttackFlowNode): node is AttackAction => {
  return node.type === 'action' || node.type === 'attack-action'; // Support both formats
};

export const isAttackAsset = (node: AttackFlowNode): node is AttackAsset => {
  return node.type === 'attack-asset';
};

export const isAttackCondition = (node: AttackFlowNode): node is AttackCondition => {
  return node.type === 'attack-condition';
};

export const isAttackOperator = (node: AttackFlowNode): node is AttackOperator => {
  return node.type === 'attack-operator';
};

export const isTool = (node: AttackFlowNode): node is Tool => {
  return node.type === 'tool';
};

export const isInfrastructure = (node: AttackFlowNode): node is Infrastructure => {
  return node.type === 'infrastructure';
};

// Helper functions
export const getMitreLink = (techniqueId: string): string => {
  return `https://attack.mitre.org/techniques/${techniqueId.replace('.', '/')}`;
};

export const getTacticName = (tacticId: string): string => {
  return TACTIC_NAMES[tacticId] || tacticId;
};

export const getNodeDisplayName = (node: AttackFlowNode): string => {
  if ('name' in node && node.name) {
    return node.name;
  }
  return node.type.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

export const getNodeTypeLabel = (type: string): string => {
  return type.split('-').pop()?.toUpperCase() || type.toUpperCase();
};