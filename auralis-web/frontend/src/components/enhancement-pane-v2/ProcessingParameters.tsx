/**
 * ProcessingParameters Component
 *
 * Displays applied processing parameters extracted from audio analysis.
 * Shows loudness targets, EQ adjustments, dynamics, and stereo width.
 */

import React from 'react';
import { Box, Typography, Stack } from '@mui/material';
import { GraphicEq, VolumeUp, Compress } from '@mui/icons-material';
import { tokens } from '../../design-system/tokens';

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
  const formatParam = (value: number, decimals: number = 1): string => {
    return value.toFixed(decimals);
  };

  return (
    <Box>
      <Typography
        variant="caption"
        sx={{
          color: tokens.colors.text.secondary,
          textTransform: 'uppercase',
          letterSpacing: 1,
          fontWeight: tokens.typography.fontWeight.semibold,
          mb: tokens.spacing.md,
          display: 'block',
          fontSize: tokens.typography.fontSize.xs,
        }}
      >
        <GraphicEq sx={{ fontSize: tokens.typography.fontSize.sm, mr: tokens.spacing.xs, verticalAlign: 'middle' }} />
        Applied Processing
      </Typography>

      <Stack spacing={tokens.spacing.md}>
        {/* Target Loudness */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
            <VolumeUp sx={{ fontSize: tokens.typography.fontSize.sm, mr: tokens.spacing.xs, verticalAlign: 'middle' }} />
            Target Loudness
          </Typography>
          <Typography
            variant="body2"
            sx={{
              color: tokens.colors.text.primary,
              fontWeight: tokens.typography.fontWeight.semibold,
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            {formatParam(params.target_lufs)} LUFS
          </Typography>
        </Box>

        {/* Peak Target */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
            Peak Level
          </Typography>
          <Typography
            variant="body2"
            sx={{
              color: tokens.colors.text.primary,
              fontWeight: tokens.typography.fontWeight.semibold,
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            {formatParam(params.peak_target_db)} dB
          </Typography>
        </Box>

        {/* Bass Adjustment (conditional) */}
        {Math.abs(params.bass_boost) > 0.1 && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
              Bass Adjustment
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: params.bass_boost > 0 ? tokens.colors.accent.success : tokens.colors.accent.warning,
                fontWeight: tokens.typography.fontWeight.semibold,
                fontSize: tokens.typography.fontSize.sm,
              }}
            >
              {params.bass_boost > 0 ? '+' : ''}{formatParam(params.bass_boost)} dB
            </Typography>
          </Box>
        )}

        {/* Air Adjustment (conditional) */}
        {Math.abs(params.air_boost) > 0.1 && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
              Air Adjustment
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: params.air_boost > 0 ? tokens.colors.accent.success : tokens.colors.accent.warning,
                fontWeight: tokens.typography.fontWeight.semibold,
                fontSize: tokens.typography.fontSize.sm,
              }}
            >
              {params.air_boost > 0 ? '+' : ''}{formatParam(params.air_boost)} dB
            </Typography>
          </Box>
        )}

        {/* Compression (conditional) */}
        {params.compression_amount > 0.05 && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
              <Compress sx={{ fontSize: tokens.typography.fontSize.sm, mr: tokens.spacing.xs, verticalAlign: 'middle' }} />
              Compression
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: tokens.colors.text.primary,
                fontWeight: tokens.typography.fontWeight.semibold,
                fontSize: tokens.typography.fontSize.sm,
              }}
            >
              {Math.round(params.compression_amount * 100)}%
            </Typography>
          </Box>
        )}

        {/* Expansion (conditional) */}
        {params.expansion_amount > 0.05 && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
              Expansion
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: tokens.colors.accent.info,
                fontWeight: tokens.typography.fontWeight.semibold,
                fontSize: tokens.typography.fontSize.sm,
              }}
            >
              {Math.round(params.expansion_amount * 100)}%
            </Typography>
          </Box>
        )}

        {/* Stereo Width */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
            Stereo Width
          </Typography>
          <Typography
            variant="body2"
            sx={{
              color: tokens.colors.text.primary,
              fontWeight: tokens.typography.fontWeight.semibold,
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            {Math.round(params.stereo_width * 100)}%
          </Typography>
        </Box>
      </Stack>
    </Box>
  );
});

ProcessingParameters.displayName = 'ProcessingParameters';

export default ProcessingParameters;
