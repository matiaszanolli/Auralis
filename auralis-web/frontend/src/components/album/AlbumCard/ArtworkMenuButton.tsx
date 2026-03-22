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

export const ArtworkMenuButton = ({ onClick }: ArtworkMenuButtonProps) => {
  return (
    <IconButton
      onClick={onClick}
      aria-label="Album artwork options"
      sx={{
        position: 'absolute',
        top: 8,
        right: 8,
        color: tokens.colors.text.primary,
        background: tokens.colors.opacityScale.dark.standard,
        backdropFilter: 'blur(10px)',
        '&:hover': { background: tokens.colors.opacityScale.dark.veryStrong },
      }}
    >
      <MoreVert />
    </IconButton>
  );
};
