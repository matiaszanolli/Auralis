/**
 * AlbumMetadata - Display album metadata (year, track count, duration, genre)
 *
 * Shows secondary information about album beneath title.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system/tokens';

interface AlbumMetadataProps {
  year?: number;
  trackCount: number;
  totalDuration: number;
  genre?: string;
}

const formatTotalDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours} hr ${mins} min`;
  }
  return `${mins} min`;
};

export const AlbumMetadata: React.FC<AlbumMetadataProps> = ({
  year,
  trackCount,
  totalDuration,
  genre,
}) => {
  return (
    <Box>
      <Typography variant="body2" sx={{
        color: tokens.colors.text.tertiary,
        mb: tokens.spacing.sm,
        fontSize: tokens.typography.fontSize.sm,
        fontWeight: tokens.typography.fontWeight.regular,
      }}>
        {year && `${year} • `}
        {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
        {' • '}
        {formatTotalDuration(totalDuration)}
      </Typography>
      {genre && (
        <Typography variant="body2" sx={{
          color: tokens.colors.text.tertiary,
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.regular,
        }}>
          Genre: {genre}
        </Typography>
      )}
    </Box>
  );
};
