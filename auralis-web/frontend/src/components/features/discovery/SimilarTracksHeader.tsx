import React from 'react';
import { Box, Typography } from '@mui/material';
import { AutoAwesome as SparklesIcon } from '@mui/icons-material';
import { tokens } from '@/design-system';

/**
 * SimilarTracksHeader - Header with title and description
 */
export const SimilarTracksHeader: React.FC = () => {
  return (
    <Box sx={{ px: 2, py: 1.5, borderBottom: `1px solid rgba(102, 126, 234, 0.1)` }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <SparklesIcon sx={{ fontSize: 20, color: tokens.colors.accent.primary }} />
        <Typography variant="subtitle2" sx={{ color: tokens.colors.text.primary, fontWeight: 600 }}>
          Similar Tracks
        </Typography>
      </Box>
      <Typography variant="caption" sx={{ color: tokens.colors.text.secondary, mt: 0.5, display: 'block' }}>
        Based on acoustic fingerprint analysis
      </Typography>
    </Box>
  );
};

export default SimilarTracksHeader;
