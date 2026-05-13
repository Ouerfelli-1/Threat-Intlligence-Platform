import { memo } from 'react';
import { NodeProps } from 'reactflow';
import { Box } from '@mui/material';
import { getBaseNodeStyle, getNodeColor } from './shared/nodeStyles';
import { NodeHandles } from './shared/NodeHandles';
import { NodeHeader } from './shared/NodeHeader';
import { NodeContent } from './shared/NodeContent';

function ToolNode({ data, selected }: NodeProps) {
  const isNewNode = data.isNewNode;
  const nodeColor = getNodeColor(data.type);
  
  // Special styling for tool nodes with enhanced left border
  const toolNodeStyle = {
    ...getBaseNodeStyle(data.type, selected, isNewNode),
    position: 'relative',
    '&::before': {
      content: '""',
      position: 'absolute',
      top: 0,
      left: -4,
      width: 4,
      height: '100%',
      background: selected 
        ? 'transparent' 
        : `linear-gradient(to bottom, ${nodeColor}, ${nodeColor}88)`,
      borderRadius: `4px 0 0 4px`,
    }
  };
  
  return (
    <Box 
      sx={{
        ...toolNodeStyle,
        overflow: 'visible',
        padding: 2
      }}
    >
      <Box sx={{ mb: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <NodeHeader nodeType={data.type} />
      </Box>

      <NodeContent 
        data={data} 
        showCommandLine={true}
      />

      <NodeHandles />
    </Box>
  );
}

export default memo(ToolNode);