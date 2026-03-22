import React from 'react';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';

interface SimilarTracksFooterProps {
  useGraph: boolean;
  tracksCount: number;
}

/**
 * SimilarTracksFooter - Footer with usage info
 */
export const SimilarTracksFooter = ({ useGraph, tracksCount }: SimilarTracksFooterProps) => {
  return (
    <Box sx={{ px: 2, py: 1, borderTop: `1px solid ${tokens.colors.opacityScale.accent.veryLight}` }}>
      <Typography variant="caption" sx={{ color: tokens.colors.text.secondary, fontSize: '0.7rem' }}>
        {useGraph ? '⚡ Fast lookup' : '🔍 Real-time search'} • {tracksCount} tracks
      </Typography>
    </Box>
  );
};

export default SimilarTracksFooter;
