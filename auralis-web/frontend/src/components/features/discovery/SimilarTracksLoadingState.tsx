import React from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import { tokens } from '@/design-system/tokens';

/**
 * SimilarTracksLoadingState - Shows loading spinner while fetching similar tracks
 */
export const SimilarTracksLoadingState: React.FC = () => {
  return (
    <Box sx={{ p: 2, textAlign: 'center' }}>
      <CircularProgress size={24} sx={{ color: tokens.colors.accent.purple }} />
      <Typography variant="body2" sx={{ mt: 1, color: tokens.colors.text.secondary }}>
        Finding similar tracks...
      </Typography>
    </Box>
  );
};

export default SimilarTracksLoadingState;
