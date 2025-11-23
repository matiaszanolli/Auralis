/**
 * PlayOverlay Component
 *
 * Displays play button overlay that appears on hover
 * Reusable for any media item with playback capability
 */

import React from 'react';
import { Box, IconButton } from '@mui/material';
import { PlayArrow } from '@mui/icons-material';
import { gradients } from '../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

export interface PlayOverlayProps {
  isHovered: boolean;
  onClick: (e: React.MouseEvent) => void;
}

export const PlayOverlay: React.FC<PlayOverlayProps> = ({ isHovered, onClick }) => {
  return (
    <Box
      sx={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: isHovered ? 'rgba(0, 0, 0, 0.19)' : 'transparent',
        backdropFilter: isHovered ? 'blur(4px)' : 'none',
        transition: 'all 0.3s ease',
        opacity: isHovered ? 1 : 0,
        pointerEvents: isHovered ? 'auto' : 'none',
      }}
    >
      <IconButton
        sx={{
          width: 56,
          height: 56,
          background: gradients.aurora,
          color: tokens.colors.text.primary,
          transform: isHovered ? 'scale(1)' : 'scale(0.8)',
          transition: 'all 0.3s ease',
          '&:hover': {
            background: gradients.electricPurple,
            transform: 'scale(1.1)',
          },
        }}
        onClick={onClick}
      >
        <PlayArrow sx={{ fontSize: 32 }} />
      </IconButton>
    </Box>
  );
};

export default PlayOverlay;
