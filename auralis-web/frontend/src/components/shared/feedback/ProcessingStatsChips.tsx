/**
 * ProcessingStatsChips - Display of processing performance metrics
 *
 * Shows cache hit, processing speed, and progress percentage as chips.
 */

import React from 'react';
import { Stack, Chip } from '@mui/material';
import { TrendingUp, Speed, Memory } from '@mui/icons-material';
import { tokens } from '@/design-system';

interface ProcessingStatsChipsProps {
  cacheHit?: boolean;
  processingSpeed?: number;
  currentChunk?: number;
  totalChunks?: number;
}

export const ProcessingStatsChips: React.FC<ProcessingStatsChipsProps> = ({
  cacheHit,
  processingSpeed,
  currentChunk,
  totalChunks,
}) => {
  return (
    <Stack direction="row" spacing={tokens.spacing.xs} flexWrap="wrap" gap={tokens.spacing.xs}>
      {cacheHit && (
        <Chip
          icon={<TrendingUp sx={{ fontSize: tokens.typography.fontSize.sm }} />}
          label="8x faster"
          size="small"
          sx={{
            height: '22px',
            backgroundColor: `${tokens.colors.semantic.success}1A`,
            color: tokens.colors.semantic.success,
            fontSize: tokens.typography.fontSize.xs,
            '& .MuiChip-icon': {
              color: tokens.colors.semantic.success,
            },
          }}
        />
      )}

      {processingSpeed && processingSpeed > 1 && (
        <Chip
          icon={<Speed sx={{ fontSize: tokens.typography.fontSize.sm }} />}
          label={`${processingSpeed.toFixed(1)}x RT`}
          size="small"
          sx={{
            height: '22px',
            backgroundColor: `${tokens.colors.accent.primary}1A`,
            color: tokens.colors.accent.primary,
            fontSize: tokens.typography.fontSize.xs,
            '& .MuiChip-icon': {
              color: tokens.colors.accent.primary,
            },
          }}
        />
      )}

      {currentChunk !== undefined && (
        <Chip
          icon={<Memory sx={{ fontSize: tokens.typography.fontSize.sm }} />}
          label={`${((currentChunk / (totalChunks || 1)) * 100).toFixed(0)}%`}
          size="small"
          sx={{
            height: '22px',
            backgroundColor: `${tokens.colors.text.secondary}1A`,
            color: tokens.colors.text.secondary,
            fontSize: tokens.typography.fontSize.xs,
            '& .MuiChip-icon': {
              color: tokens.colors.text.secondary,
            },
          }}
        />
      )}
    </Stack>
  );
};
