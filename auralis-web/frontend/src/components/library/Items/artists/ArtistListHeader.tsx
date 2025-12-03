/**
 * ArtistListHeader - Library stats display
 *
 * Shows count of loaded artists vs total library size.
 */

import React from 'react';
import { Typography } from '@mui/material';
import { SectionHeader } from '../../Styles/ArtistList.styles';

interface ArtistListHeaderProps {
  loadedCount: number;
  totalCount: number;
}

export const ArtistListHeader: React.FC<ArtistListHeaderProps> = ({
  loadedCount,
  totalCount,
}) => {
  return (
    <SectionHeader>
      <Typography variant="body2" color="text.secondary">
        {loadedCount} {loadedCount !== totalCount ? `of ${totalCount}` : ''} artists in your library
      </Typography>
    </SectionHeader>
  );
};
