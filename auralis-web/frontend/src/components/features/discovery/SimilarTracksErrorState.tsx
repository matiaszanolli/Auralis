import React from 'react';
import { Box } from '@mui/material';
import { Alert } from '@/design-system';

interface SimilarTracksErrorStateProps {
  error: string;
}

/**
 * SimilarTracksErrorState - Shows error message when loading fails
 */
export const SimilarTracksErrorState: React.FC<SimilarTracksErrorStateProps> = ({ error }) => {
  return (
    <Box sx={{ p: 2 }}>
      <Alert variant="error">
        {error}
      </Alert>
    </Box>
  );
};

export default SimilarTracksErrorState;
