import React from 'react';
import { Box, Alert } from '@mui/material';

interface SimilarTracksErrorStateProps {
  error: string;
}

/**
 * SimilarTracksErrorState - Shows error message when loading fails
 */
export const SimilarTracksErrorState: React.FC<SimilarTracksErrorStateProps> = ({ error }) => {
  return (
    <Box sx={{ p: 2 }}>
      <Alert severity="error" sx={{ fontSize: '0.875rem' }}>
        {error}
      </Alert>
    </Box>
  );
};

export default SimilarTracksErrorState;
