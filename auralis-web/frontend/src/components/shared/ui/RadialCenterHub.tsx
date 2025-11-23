/**
 * RadialCenterHub - Center display showing current preset
 *
 * Displays preset icon and label with animated pulse and gradient background.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { Preset } from './presetConfig';
import { auroraOpacity, colorAuroraPrimary } from '@/components/library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

interface RadialCenterHubProps {
  preset: Preset;
  size: number; // Diameter of selector
}

export const RadialCenterHub: React.FC<RadialCenterHubProps> = ({ preset, size }) => {
  const centerSize = size / 3;

  return (
    <Box
      sx={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: centerSize,
        height: centerSize,
        borderRadius: '50%',
        background: preset.gradient,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: `0 0 40px ${preset.gradient.match(/#[0-9a-f]{6}/i)?.[0] || colorAuroraPrimary}66`,
        transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        border: `3px solid ${auroraOpacity.lighter}`,
        backdropFilter: 'blur(10px)',
      }}
    >
      <Box
        sx={{
          fontSize: 32,
          color: tokens.colors.text.primary,
          mb: 0.5,
          filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))',
          animation: 'pulse 2s ease-in-out infinite',
          '@keyframes pulse': {
            '0%, 100%': { transform: 'scale(1)' },
            '50%': { transform: 'scale(1.1)' },
          },
        }}
      >
        {preset.icon}
      </Box>
      <Typography
        variant="caption"
        sx={{
          color: tokens.colors.text.primary,
          fontWeight: 700,
          fontSize: 13,
          textTransform: 'uppercase',
          letterSpacing: 1.2,
          textShadow: '0 2px 4px rgba(0,0,0,0.3)',
        }}
      >
        {preset.label}
      </Typography>
    </Box>
  );
};
