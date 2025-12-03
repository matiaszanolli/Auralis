/**
 * ArtworkMenuButton - Positioned menu button overlay for artwork actions
 *
 * Shows in top-right corner with semi-transparent background.
 */

import React from 'react';

import { MoreVert } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { IconButton } from '@/design-system';

interface ArtworkMenuButtonProps {
  onClick: (e: React.MouseEvent<HTMLElement>) => void;
}

export const ArtworkMenuButton: React.FC<ArtworkMenuButtonProps> = ({ onClick }) => {
  return (
    <IconButton
      onClick={onClick}
      sx={{
        position: 'absolute',
        top: 8,
        right: 8,
        color: tokens.colors.text.primary,
        background: 'rgba(0, 0, 0, 0.19)',
        backdropFilter: 'blur(10px)',
        '&:hover': { background: 'rgba(0, 0, 0, 0.42)' },
      }}
    >
      <MoreVert />
    </IconButton>
  );
};
