/**
 * LibraryHeader - Library View Header Component
 *
 * Extracted from CozyLibraryView for better modularity.
 * Displays the main title and subtitle based on the current view.
 *
 * 100% design token compliant - no hardcoded values.
 */

import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';

interface LibraryHeaderProps {
  view: string;
}

export const LibraryHeader = memo<LibraryHeaderProps>(({ view }) => {
  return (
    <Box sx={{ mb: tokens.spacing.xl }}>
      <Typography
        variant="h3"
        component="h1"
        gutterBottom
        sx={{
          fontWeight: tokens.typography.fontWeight.bold,

          // Manrope for dramatic headers (R4)
          fontFamily: tokens.typography.fontFamily.header,

          // 56px - dramatic scale (R4)
          fontSize: tokens.typography.fontSize['4xl'],

          // Tight tracking for large headers
          letterSpacing: '-0.02em',

          background: tokens.gradients.aurora,
          backgroundClip: 'text',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}>
        {view === 'favourites'
          ? <><span aria-hidden="true">❤️ </span>Your Favorites</>
          : <><span aria-hidden="true">🎵 </span>Your Music Collection</>}
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
