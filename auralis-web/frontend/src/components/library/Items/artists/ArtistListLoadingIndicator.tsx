/**
 * ArtistListLoadingIndicator - Spinning loader with progress text
 *
 * Displays during infinite scroll pagination of artist list.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';

interface ArtistListLoadingIndicatorProps {
  currentCount: number;
  totalCount: number;
}

export const ArtistListLoadingIndicator: React.FC<ArtistListLoadingIndicatorProps> = ({
  currentCount,
  totalCount,
}) => {
  return (
    <Box
      sx={{
        height: '100px',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Box
        sx={{
          width: 20,
          height: 20,
          border: '2px solid',
          borderColor: 'primary.main',
          borderRightColor: 'transparent',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
          '@keyframes spin': {
            '0%': { transform: 'rotate(0deg)' },
            '100%': { transform: 'rotate(360deg)' },
          },
        }}
      />
      <Typography variant="body2" color="text.secondary" sx={{ ml: 2 }}>
        Loading more artists... ({currentCount}/{totalCount})
      </Typography>
    </Box>
  );
};
