import React from 'react';
import { Box, Typography } from '@mui/material';
import {
  MusicNote as MusicNoteIcon,
  AutoAwesome as SparklesIcon
} from '@mui/icons-material';
import { tokens } from '@/design-system';

interface SimilarTracksEmptyStateProps {
  trackId: number | null;
}

/**
 * SimilarTracksEmptyState - Shows when no similar tracks found or no track selected
 */
export const SimilarTracksEmptyState: React.FC<SimilarTracksEmptyStateProps> = ({ trackId }) => {
  if (!trackId) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <MusicNoteIcon sx={{ fontSize: 48, color: tokens.colors.accent.primary, opacity: 0.5, mb: 1 }} />
        <Typography variant="body2" sx={{ color: tokens.colors.text.secondary }}>
          Play a track to discover similar music
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2, textAlign: 'center' }}>
      <SparklesIcon sx={{ fontSize: 48, color: tokens.colors.accent.primary, opacity: 0.5, mb: 1 }} />
      <Typography variant="body2" sx={{ color: tokens.colors.text.secondary }}>
        No similar tracks found
      </Typography>
      <Typography variant="caption" sx={{ color: tokens.colors.text.secondary, mt: 0.5, display: 'block' }}>
        Try playing a different track
      </Typography>
    </Box>
  );
};

export default SimilarTracksEmptyState;
