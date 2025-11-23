/**
 * LoadingOverlay Component
 *
 * Displays loading indicator during artwork operations
 * Shows while downloading or extracting artwork
 */

import React from 'react';
import { Box, CircularProgress } from '@mui/material';
import { auroraOpacity } from '../../library/Styles/Color.styles';

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
      <CircularProgress size={40} sx={{ color: auroraOpacity.veryStrong }} />
    </Box>
  );
};

export default LoadingOverlay;
