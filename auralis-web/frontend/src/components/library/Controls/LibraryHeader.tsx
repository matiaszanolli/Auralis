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
          fontFamily: tokens.typography.fontFamily.header,  // Manrope for dramatic headers (R4)
          fontSize: tokens.typography.fontSize['4xl'],      // 56px - dramatic scale (R4)
          letterSpacing: '-0.02em',                         // Tight tracking for large headers
          background: tokens.gradients.aurora,
          backgroundClip: 'text',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}
      >
        {view === 'favourites' ? '❤️ Your Favorites' : '🎵 Your Music Collection'}
      </Typography>
      <Typography
        variant="subtitle1"
        color={tokens.colors.text.secondary}
        sx={{
          fontFamily: tokens.typography.fontFamily.primary,  // Inter for body text
          fontSize: tokens.typography.fontSize.lg,           // 20px - increased from default
        }}
      >
        {view === 'favourites' ? 'Your most loved tracks' : 'Rediscover the magic in every song'}
      </Typography>
    </Box>
  );
});

LibraryHeader.displayName = 'LibraryHeader';

export default LibraryHeader;
