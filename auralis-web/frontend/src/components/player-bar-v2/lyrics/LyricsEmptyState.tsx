import React from 'react';
import { Typography } from '@mui/material';
import { MusicNote as MusicNoteIcon } from '@mui/icons-material';
import { tokens } from '../../../design-system/tokens';
import { EmptyState } from './LyricsPanel.styles';

/**
 * LyricsEmptyState - Shows when no lyrics are available for track
 */
export const LyricsEmptyState: React.FC = () => {
  return (
    <EmptyState>
      <MusicNoteIcon sx={{ fontSize: 64, color: tokens.colors.text.disabled, mb: 2 }} />
      <Typography variant="h6" sx={{ color: tokens.colors.text.primary, mb: 1 }}>
        No Lyrics Available
      </Typography>
      <Typography sx={{ color: tokens.colors.text.secondary, fontSize: '14px' }}>
        This track doesn't have embedded lyrics
      </Typography>
    </EmptyState>
  );
};

export default LyricsEmptyState;
