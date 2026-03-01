/**
 * LoadingOverlay Component
 *
 * Displays loading indicator during artwork operations
 * Shows while downloading or extracting artwork
 */

import React from 'react';
import { Box } from '@mui/material';
import { CircularProgress, tokens } from '@/design-system';

export interface LoadingOverlayProps {
  show: boolean;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({ show }) => {
  if (!show) return null;

  return (
    <Box
      sx={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.42)',
        backdropFilter: 'blur(4px)',
      }}
    >
      <CircularProgress size={40} sx={{ color: tokens.colors.opacityScale.accent.veryStrong }} />
    </Box>
  );
};

export default LoadingOverlay;
