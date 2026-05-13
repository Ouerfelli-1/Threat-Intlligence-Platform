import { Typography } from '@mui/material';
import { getNodeTypeDisplay } from './nodeUtils';

interface NodeHeaderProps {
  nodeType: string;
}

export function NodeHeader({ nodeType }: NodeHeaderProps) {
  return (
    <Typography
      variant="caption"
      sx={{
        color: 'rgba(255, 255, 255, 0.7)',
        textTransform: 'uppercase',
        fontSize: '0.75rem',
        letterSpacing: '0.05em',
        fontWeight: 600
      }}
    >
      {getNodeTypeDisplay(nodeType)}
    </Typography>
  );
}