/**
 * EnhancementToggle Component
 *
 * Master toggle switch for enabling/disabling auto-mastering.
 * Displays current state and status messages.
 */

import React from 'react';
import { Paper, Typography, Switch, FormControlLabel } from '@mui/material';
import { tokens } from '../../design-system/tokens';

interface EnhancementToggleProps {
  enabled: boolean;
  isProcessing: boolean;
  onToggle: (enabled: boolean) => void;
}

const EnhancementToggle: React.FC<EnhancementToggleProps> = React.memo(({
  enabled,
  isProcessing,
  onToggle,
}) => {
  return (
    <Paper
      elevation={0}
      sx={{
        p: tokens.spacing.md,
        mb: tokens.spacing.lg,
        borderRadius: tokens.borderRadius.md,
        background: enabled
          ? `${tokens.colors.accent.primary}1A` // 1A = ~10% opacity
          : tokens.colors.bg.tertiary,
        border: `1px solid ${
          enabled
            ? `${tokens.colors.accent.primary}4D` // 4D = ~30% opacity
            : tokens.colors.border.light
        }`,
        transition: tokens.transitions.all,
        opacity: isProcessing ? 0.7 : 1,
      }}
    >
      <FormControlLabel
        control={
          <Switch
            checked={enabled}
            onChange={(e) => onToggle(e.target.checked)}
            disabled={isProcessing}
            sx={{
              '& .MuiSwitch-switchBase.Mui-checked': {
                color: tokens.colors.accent.primary,
              },
              '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                backgroundColor: tokens.colors.accent.primary,
              },
            }}
          />
        }
        label={
          <Typography
            variant="body2"
            sx={{
              fontFamily: tokens.typography.fontFamily.primary,
              fontWeight: tokens.typography.fontWeight.semibold,
              color: tokens.colors.text.primary,
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            Enable Auto-Mastering
          </Typography>
        }
      />
      <Typography
        variant="caption"
        sx={{
          display: 'block',
          mt: tokens.spacing.xs,
          ml: `calc(${tokens.spacing.xxl} + ${tokens.spacing.xs})`, // Switch width + gap
          color: tokens.colors.text.secondary,
          fontSize: tokens.typography.fontSize.xs,
          fontFamily: tokens.typography.fontFamily.primary,
        }}
      >
        {enabled
          ? 'Analyzing audio and applying intelligent processing'
          : 'Turn on to enhance your music automatically'}
      </Typography>
    </Paper>
  );
});

EnhancementToggle.displayName = 'EnhancementToggle';

export default EnhancementToggle;
