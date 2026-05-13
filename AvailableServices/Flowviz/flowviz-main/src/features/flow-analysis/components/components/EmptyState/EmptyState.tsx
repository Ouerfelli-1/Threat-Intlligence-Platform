import React from 'react';
import { Box, Typography } from '@mui/material';
import { THEME } from '../../constants';

const EmptyState: React.FC = () => {
  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      height="100%"
      sx={{
        color: THEME.text.secondary,
        textAlign: 'center',
        p: 4
      }}
    >
      <Typography variant="h6" sx={{ mb: 2, color: THEME.text.primary }}>
        No attack flow data available
      </Typography>
      <Typography variant="body2" sx={{ maxWidth: 400 }}>
        Analyze a security article to generate an interactive MITRE ATT&CK flow visualization.
      </Typography>
    </Box>
  );
};

export default EmptyState;