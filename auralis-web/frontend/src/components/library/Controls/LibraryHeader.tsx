/**
 * LibraryHeader - Library View Header Component
 *
 * Extracted from CozyLibraryView for better modularity.
 * Displays the main title and subtitle based on the current view.
 *
 * 100% design token compliant - no hardcoded values.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';

interface LibraryHeaderProps {
  view: string;
}

export const LibraryHeader: React.FC<LibraryHeaderProps> = React.memo(({ view }) => {
  return (
    <Box sx={{ mb: tokens.spacing.xl }}>
      <Typography
        variant="h3"
        component="h1"
        fontWeight={tokens.typography.fontWeight.bold}
        gutterBottom
        sx={{
          background: tokens.gradients.aurora,
          backgroundClip: 'text',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}
      >
        {view === 'favourites' ? '❤️ Your Favorites' : '🎵 Your Music Collection'}
      </Typography>
      <Typography variant="subtitle1" color={tokens.colors.text.secondary}>
        {view === 'favourites' ? 'Your most loved tracks' : 'Rediscover the magic in every song'}
      </Typography>
    </Box>
  );
});

LibraryHeader.displayName = 'LibraryHeader';

export default LibraryHeader;
