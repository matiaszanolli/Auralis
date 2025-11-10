/**
 * ParameterBar Component
 *
 * Reusable progress bar with label and chip for visualizing parameter values.
 * Supports custom gradients for visual differentiation.
 */

import React from 'react';
import { Box, Typography, LinearProgress } from '@mui/material';
import { tokens } from '../../design-system/tokens';
import ParameterChip from './ParameterChip';

interface ParameterBarProps {
  label: string;
  value: number; // 0-1
  gradient: string;
  chipLabel: string;
}

const ParameterBar: React.FC<ParameterBarProps> = React.memo(({
  label,
  value,
  gradient,
  chipLabel,
}) => {
  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: tokens.spacing.xs,
        }}
      >
        <Typography
          variant="body2"
          sx={{
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: tokens.typography.fontWeight.medium,
          }}
        >
          {label}
        </Typography>
        <ParameterChip label={chipLabel} gradient={gradient} />
      </Box>
      <LinearProgress
        variant="determinate"
        value={value * 100}
        sx={{
          height: tokens.spacing.xs,
          borderRadius: tokens.borderRadius.sm,
          backgroundColor: tokens.colors.border.light,
          '& .MuiLinearProgress-bar': {
            background: gradient,
            borderRadius: tokens.borderRadius.sm,
            transition: tokens.transitions.base,
          },
        }}
      />
    </Box>
  );
});

ParameterBar.displayName = 'ParameterBar';

export default ParameterBar;
