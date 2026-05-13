import { AttackAction, AttackOperator } from '../../../types/attack-flow';

// Text handling utilities
export const getTextStyle = (text: string) => {
  if (!text) return { text, style: {} };
  
  // Check if any word is very long (URLs, hashes, paths)
  const hasLongWord = text.split(/\s+/).some(word => word.length > 25);
  
  if (hasLongWord) {
    // Truncate text with long unbroken words
    const truncatedText = text.length > 40 ? text.slice(0, 40).trim() + '...' : text;
    return {
      text: truncatedText,
      style: {
        whiteSpace: 'nowrap' as const,
        textOverflow: 'ellipsis',
        overflow: 'hidden'
      }
    };
  } else {
    // Normal word wrapping
    return {
      text,
      style: {
        whiteSpace: 'normal' as const
      }
    };
  }
};

// MITRE ATT&CK link utility
export const getMitreLink = (techniqueId: string) => {
  return `https://attack.mitre.org/techniques/${techniqueId.replace('.', '/')}`;
};

// Type guards
export const isAttackAction = (node: any): node is AttackAction => {
  return node.type === 'action' || node.type === 'attack-action';
};

export const isOperator = (node: any): node is AttackOperator => {
  return node.type === 'AND_operator' || node.type === 'OR_operator';
};

export const hasDescription = (node: any): boolean => {
  return 'description' in node && typeof node.description === 'string';
};

export const hasName = (node: any): boolean => {
  return 'name' in node && typeof node.name === 'string';
};

// Node type display names
export const getNodeTypeDisplay = (type: string): string => {
  const typeMap: Record<string, string> = {
    'action': 'technique',
    'attack-action': 'technique',
    'tool': 'tool',
    'malware': 'malware',
    'asset': 'asset',
    'infrastructure': 'infrastructure',
    'url': 'url',
    'vulnerability': 'vulnerability',
    'AND_operator': 'AND',
    'OR_operator': 'OR'
  };
  
  return typeMap[type] || type;
};