/**
 * AlbumMetadata - Display album metadata (year, track count, duration, genre)
 *
 * Shows secondary information about album beneath title.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';

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
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
        {year && `${year} • `}
        {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
        {' • '}
        {formatTotalDuration(totalDuration)}
      </Typography>
      {genre && (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Genre: {genre}
        </Typography>
      )}
    </Box>
  );
};
