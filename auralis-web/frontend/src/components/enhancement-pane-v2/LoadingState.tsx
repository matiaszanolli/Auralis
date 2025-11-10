/**
 * LoadingState Component
 *
 * Displayed when analyzing audio for auto-mastering parameters.
 * Features pulsing animation for visual feedback.
 */

import React from 'react';
import { Paper, Typography } from '@mui/material';
import { AutoAwesome } from '@mui/icons-material';
import { tokens } from '../../design-system/tokens';

const LoadingState: React.FC = React.memo(() => {
  return (
    <Paper
      elevation={0}
      sx={{
        p: tokens.spacing.xl,
        borderRadius: tokens.borderRadius.md,
        background: tokens.colors.bg.tertiary,
        border: `1px solid ${tokens.colors.border.light}`,
        textAlign: 'center',
      }}
    >
      <AutoAwesome
        sx={{
          fontSize: tokens.typography.fontSize['4xl'],
          color: tokens.colors.accent.primary,
          mb: tokens.spacing.md,
          animation: `${tokens.animations.pulse.keyframes} pulse ${tokens.animations.pulse.duration} ${tokens.animations.pulse.timing} ${tokens.animations.pulse.iteration}`,
        }}
      />
      <Typography
        variant="body2"
        sx={{
          color: tokens.colors.text.secondary,
          fontSize: tokens.typography.fontSize.sm,
        }}
      >
        Analyzing audio...
      </Typography>
    </Paper>
  );
});

LoadingState.displayName = 'LoadingState';

export default LoadingState;
