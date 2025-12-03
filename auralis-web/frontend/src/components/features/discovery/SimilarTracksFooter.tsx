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
export const SimilarTracksFooter: React.FC<SimilarTracksFooterProps> = ({ useGraph, tracksCount }) => {
  return (
    <Box sx={{ px: 2, py: 1, borderTop: `1px solid rgba(102, 126, 234, 0.1)` }}>
      <Typography variant="caption" sx={{ color: tokens.colors.text.secondary, fontSize: '0.7rem' }}>
        {useGraph ? '⚡ Fast lookup' : '🔍 Real-time search'} • {tracksCount} tracks
      </Typography>
    </Box>
  );
};

export default SimilarTracksFooter;
