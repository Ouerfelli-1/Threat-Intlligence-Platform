import { memo } from 'react';
import { NodeProps } from 'reactflow';
import { Typography, Box } from '@mui/material';
import { getOperatorNodeStyle } from './shared/nodeStyles';
import { NodeHandles } from './shared/NodeHandles';
import { hasName } from './shared/nodeUtils';

function OperatorNode({ data, selected }: NodeProps) {
  const isNewNode = data.isNewNode;
  
  return (
    <Box 
      sx={{
        ...getOperatorNodeStyle(selected, isNewNode),
      }}
    >
      <Box sx={{ 
        position: 'relative',
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        px: 2,
      }}>
        <Box
          component="span"
          sx={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            backgroundColor: 'rgb(245, 158, 11)',
            boxShadow: '0 0 10px rgba(245, 158, 11, 0.5)',
            mr: 1.5,
          }}
        />
        <Typography
          variant="body2"
          sx={{
            color: 'rgb(245, 158, 11)',
            fontWeight: 600,
            fontSize: '0.875rem',
            letterSpacing: '0.01em',
            textShadow: '0 2px 4px rgba(0, 0, 0, 0.2)',
          }}
        >
          {hasName(data) ? data.name : 'Network Access Check'}
        </Typography>
      </Box>
      <NodeHandles type="operator" />
    </Box>
  );
}

export default memo(OperatorNode);