// Shared node styling utilities
export const NODE_COLORS: Record<string, string> = {
  'action': '#3b82f6',
  'tool': '#10b981',
  'malware': '#ef4444',
  'asset': '#f59e0b',
  'infrastructure': '#06b6d4',
  'url': '#8b5cf6',
  'vulnerability': '#f43f5e',
  'AND_operator': '#64748b',
  'OR_operator': '#64748b'
};

export const getNodeColor = (type: string): string => {
  return NODE_COLORS[type] || '#64748b';
};

export const getBaseNodeStyle = (
  type: string, 
  isSelected: boolean, 
  isNewNode: boolean = false
) => {
  const nodeColor = getNodeColor(type);
  const borderRadiusValue = '8px';

  return {
    minWidth: 200,
    maxWidth: 280,
    backgroundColor: 'rgba(22, 27, 34, 0.95)',
    backdropFilter: 'blur(10px)',
    boxShadow: isSelected 
      ? `0 0 0 2px ${nodeColor}80, 0 0 15px 2px ${nodeColor}40`
      : '0 4px 20px rgba(0, 0, 0, 0.4)',
    border: isSelected 
      ? `2px solid ${nodeColor}` 
      : '1px solid rgba(255, 255, 255, 0.12)',
    borderLeft: isSelected 
      ? `2px solid ${nodeColor}` 
      : `4px solid ${nodeColor}`,
    borderRadius: borderRadiusValue,
    transition: isNewNode ? 'opacity 0.6s ease-out, transform 0.6s ease-out' : 'none',
    opacity: isNewNode ? 0 : 1,
    transform: isNewNode ? 'scale(0.8) translateY(-20px)' : 'scale(1) translateY(0px)',
    cursor: 'grab',
    pointerEvents: 'auto',
    userSelect: 'none',
    '&:active': {
      cursor: 'grabbing',
    },
    zIndex: isSelected ? 10 : 'auto',
    position: 'relative',
    overflow: 'visible',
    '&:hover': {
      boxShadow: isSelected 
        ? `0 0 0 2px ${nodeColor}80`
        : '0 6px 20px rgba(0, 0, 0, 0.5)',
      border: isSelected 
        ? `2px solid ${nodeColor}` 
        : '1px solid rgba(255, 255, 255, 0.2)',
      borderLeft: isSelected 
        ? `2px solid ${nodeColor}` 
        : `4px solid ${nodeColor}`,
    }
  };
};

export const getOperatorNodeStyle = (
  isSelected: boolean, 
  isNewNode: boolean = false
) => {
  const borderRadiusValue = '8px';
  
  return {
    minWidth: 240,
    maxWidth: 240,
    height: 44,
    backgroundColor: isSelected ? 'rgba(245, 158, 11, 0.2)' : 'rgba(245, 158, 11, 0.1)',
    backdropFilter: 'blur(10px)',
    border: isSelected ? '2px solid rgba(245, 158, 11, 0.7)' : '1px solid rgba(245, 158, 11, 0.2)',
    borderRadius: borderRadiusValue,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    transition: isNewNode ? 'opacity 0.6s ease-out, transform 0.6s ease-out' : 'none',
    opacity: isNewNode ? 0 : 1,
    transform: isNewNode ? 'scale(0.8) translateY(-20px)' : 'scale(1) translateY(0px)',
    boxShadow: isSelected 
      ? '0 0 0 2px rgba(245, 158, 11, 0.4), 0 0 15px 2px rgba(245, 158, 11, 0.2)'
      : '0 4px 20px rgba(0, 0, 0, 0.4)',
    zIndex: isSelected ? 10 : 'auto',
    overflow: 'visible',
    cursor: 'grab',
    '&:active': {
      cursor: 'grabbing',
    },
    '&:hover': {
      boxShadow: isSelected 
        ? '0 0 0 2px rgba(245, 158, 11, 0.4), 0 0 10px 2px rgba(245, 158, 11, 0.2)'
        : '0 6px 20px rgba(0, 0, 0, 0.5)',
      backgroundColor: isSelected ? 'rgba(245, 158, 11, 0.2)' : 'rgba(245, 158, 11, 0.15)',
      border: isSelected ? '2px solid rgba(245, 158, 11, 0.7)' : '1px solid rgba(245, 158, 11, 0.3)',
    },
    '&::before': {
      content: '""',
      position: 'absolute',
      inset: 0,
      borderRadius: 'inherit',
      padding: '1px',
      background: isSelected 
        ? 'linear-gradient(90deg, rgba(245, 158, 11, 0.6), rgba(245, 158, 11, 0.8), rgba(245, 158, 11, 0.6))'
        : 'linear-gradient(90deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.4), rgba(245, 158, 11, 0.2))',
      WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
      WebkitMaskComposite: 'xor',
      maskComposite: 'exclude',
    }
  };
};