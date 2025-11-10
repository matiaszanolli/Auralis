/**
 * EmptyState Component
 *
 * Displayed when no track is loaded and auto-mastering is enabled.
 * Provides visual feedback and guidance to the user.
 */

import React from 'react';
import { Paper, Typography } from '@mui/material';
import { AutoAwesome } from '@mui/icons-material';
import { tokens } from '../../design-system/tokens';

const EmptyState: React.FC = React.memo(() => {
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
          opacity: 0.5,
        }}
      />
      <Typography
        variant="body2"
        sx={{
          color: tokens.colors.text.secondary,
          fontSize: tokens.typography.fontSize.sm,
        }}
      >
        Play a track to see auto-mastering parameters
      </Typography>
    </Paper>
  );
});

EmptyState.displayName = 'EmptyState';

export default EmptyState;
