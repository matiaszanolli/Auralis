/**
 * ParameterBar Component
 *
 * Reusable progress bar with label and chip for visualizing parameter values.
 * Supports custom gradients for visual differentiation.
 */

import React from 'react';

import { tokens } from '@/design-system';
import ParameterChip from './ParameterChip';
import { LinearProgress } from '@/design-system';
import { Box, Typography } from '@mui/material';

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
          mb: tokens.spacing.sm, // Increased from xs for more breathing room
        }}
      >
        <Typography
          variant="body2"
          sx={{
            color: tokens.colors.text.tertiary, // Changed from primary to tertiary (less visual weight)
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: tokens.typography.fontWeight.normal, // Reduced from medium
            opacity: 0.85, // Fade by ~15% to make labels less prominent
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
          height: '3px', // Reduced from 4px (tokens.spacing.xs) for less visual weight
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
