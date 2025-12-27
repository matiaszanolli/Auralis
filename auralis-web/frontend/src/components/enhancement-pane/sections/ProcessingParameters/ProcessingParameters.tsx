/**
 * ProcessingParameters Component
 *
 * Displays applied processing parameters extracted from audio analysis.
 * Shows loudness targets, EQ adjustments, dynamics, and stereo width.
 *
 * Orchestrates ParameterRow components with formatting via custom hook.
 */

import React from 'react';
import { Box, Typography, Stack } from '@mui/material';
import { GraphicEq, VolumeUp, Compress } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { ParameterRow } from './ParameterRow';
import { useParameterFormatting } from '../../hooks/useParameterFormatting';

interface ProcessingParams {
  target_lufs: number;
  peak_target_db: number;
  bass_boost: number;
  air_boost: number;
  compression_amount: number;
  expansion_amount: number;
  stereo_width: number;
}

interface ProcessingParametersProps {
  params: ProcessingParams;
}

const ProcessingParameters: React.FC<ProcessingParametersProps> = React.memo(({ params }) => {
  const {
    formatTargetLoudness,
    formatPeakTarget,
    formatBassBoost,
    formatAirBoost,
    formatCompression,
    formatExpansion,
    formatStereoWidth,
  } = useParameterFormatting(params);

  // Get all formatted parameters
  const loudness = formatTargetLoudness();
  const peak = formatPeakTarget();
  const bass = formatBassBoost();
  const air = formatAirBoost();
  const compression = formatCompression();
  const expansion = formatExpansion();
  const stereoWidth = formatStereoWidth();

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
        <GraphicEq sx={{ fontSize: tokens.typography.fontSize.sm, mr: tokens.spacing.xs, verticalAlign: 'middle' }} />
        Applied Processing
      </Typography>

      <Stack spacing={tokens.spacing.lg}> {/* Increased from md for better separation */}
        <ParameterRow label={loudness.label} value={loudness.value} icon={VolumeUp} />
        <ParameterRow label={peak.label} value={peak.value} />
        {bass.shouldShow && <ParameterRow label={bass.label} value={bass.value} valueColor={bass.valueColor} />}
        {air.shouldShow && <ParameterRow label={air.label} value={air.value} valueColor={air.valueColor} />}
        {compression.shouldShow && <ParameterRow label={compression.label} value={compression.value} icon={Compress} />}
        {expansion.shouldShow && <ParameterRow label={expansion.label} value={expansion.value} valueColor={expansion.valueColor} />}
        <ParameterRow label={stereoWidth.label} value={stereoWidth.value} />
      </Stack>
    </Box>
  );
});

ProcessingParameters.displayName = 'ProcessingParameters';

export default ProcessingParameters;
