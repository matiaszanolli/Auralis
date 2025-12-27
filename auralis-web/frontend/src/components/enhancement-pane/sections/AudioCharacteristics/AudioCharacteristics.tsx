/**
 * AudioCharacteristics Component
 *
 * Displays 3D space visualization of audio characteristics:
 * - Spectral Balance (0=dark, 1=bright)
 * - Dynamic Range (0=compressed, 1=dynamic)
 * - Energy Level (0=quiet, 1=loud)
 */

import React from 'react';
import { Box, Typography, Stack } from '@mui/material';
import { Audiotrack } from '@mui/icons-material';
import { tokens } from '@/design-system';
import ParameterBar from '../ProcessingParameters/ParameterBar';

interface ProcessingParams {
  spectral_balance: number;
  dynamic_range: number;
  energy_level: number;
}

interface AudioCharacteristicsProps {
  params: ProcessingParams;
}

// Define gradients for each parameter using design system tokens
const GRADIENTS = {
  spectralBalance: `linear-gradient(135deg, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.secondary} 100%)`, // Soft Violet to Electric Aqua gradient
  dynamicRange: `linear-gradient(135deg, #3B82F6 0%, ${tokens.colors.accent.primary} 100%)`,     // Blue to Soft Violet gradient
  energyLevel: `linear-gradient(135deg, ${tokens.colors.semantic.success} 0%, #26de81 100%)`,      // Green gradient
};

const AudioCharacteristics: React.FC<AudioCharacteristicsProps> = React.memo(({ params }) => {
  // Helper to get spectral balance label
  const getSpectralLabel = (value: number): string => {
    if (value < 0.3) return 'Dark';
    if (value < 0.7) return 'Balanced';
    return 'Bright';
  };

  // Helper to get dynamic range label
  const getDynamicLabel = (value: number): string => {
    if (value < 0.3) return 'Compressed';
    if (value < 0.7) return 'Moderate';
    return 'Dynamic';
  };

  // Helper to get energy level label
  const getEnergyLabel = (value: number): string => {
    if (value < 0.3) return 'Quiet';
    if (value < 0.7) return 'Moderate';
    return 'Loud';
  };

  return (
    <Box>
      <Typography
        variant="caption"
        sx={{
          color: tokens.colors.text.tertiary, // Changed from secondary to tertiary (less visual weight)
          textTransform: 'uppercase',
          letterSpacing: 1,
          fontWeight: tokens.typography.fontWeight.medium, // Reduced from semibold
          mb: tokens.spacing.lg, // Increased from md for more breathing room
          display: 'block',
          fontSize: tokens.typography.fontSize.xs,
          opacity: 0.8, // Fade by ~20% to reduce visual noise
        }}
      >
        <Audiotrack sx={{ fontSize: tokens.typography.fontSize.sm, mr: tokens.spacing.xs, verticalAlign: 'middle' }} />
        Audio Characteristics
      </Typography>

      <Stack spacing={tokens.spacing.lg}> {/* Increased from md for better separation */}
        {/* Spectral Balance */}
        <ParameterBar
          label="Spectral Balance"
          value={params.spectral_balance}
          gradient={GRADIENTS.spectralBalance}
          chipLabel={getSpectralLabel(params.spectral_balance)}
        />

        {/* Dynamic Range */}
        <ParameterBar
          label="Dynamic Range"
          value={params.dynamic_range}
          gradient={GRADIENTS.dynamicRange}
          chipLabel={getDynamicLabel(params.dynamic_range)}
        />

        {/* Energy Level */}
        <ParameterBar
          label="Energy Level"
          value={params.energy_level}
          gradient={GRADIENTS.energyLevel}
          chipLabel={getEnergyLabel(params.energy_level)}
        />
      </Stack>
    </Box>
  );
});

AudioCharacteristics.displayName = 'AudioCharacteristics';

export default AudioCharacteristics;
