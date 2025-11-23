import React from 'react';
import { CircularProgress, Typography } from '@mui/material';
import { tokens } from '../../../design-system/tokens';
import { EmptyState } from './LyricsPanel.styles';

/**
 * LyricsLoadingState - Shows loading spinner while fetching lyrics
 */
export const LyricsLoadingState: React.FC = () => {
  return (
    <EmptyState>
      <CircularProgress size={40} sx={{ color: tokens.colors.accent.purple }} />
      <Typography sx={{ mt: 2, color: tokens.colors.text.secondary }}>
        Loading lyrics...
      </Typography>
    </EmptyState>
  );
};

export default LyricsLoadingState;
