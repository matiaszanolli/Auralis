/**
 * ArtworkSquareContainer - Square aspect ratio container for artwork
 *
 * Maintains 1:1 aspect ratio for album artwork display.
 */

import React from 'react';
import { Box } from '@mui/material';
import { tokens } from '@/design-system/tokens';

interface ArtworkSquareContainerProps {
  children: React.ReactNode;
}

export const ArtworkSquareContainer: React.FC<ArtworkSquareContainerProps> = ({ children }) => {
  return (
    <Box
      sx={{
        position: 'relative',
        width: '100%',
        paddingBottom: '100%', // Creates 1:1 (square) aspect ratio
        overflow: 'hidden',
        backgroundColor: tokens.colors.bg.primary,
        flexShrink: 0,
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
        }}
      >
        {children}
      </Box>
    </Box>
  );
};
