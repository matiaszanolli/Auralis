/**
 * InfoBox Component
 *
 * Information panel explaining auto-mastering functionality.
 * Uses design tokens for consistent styling.
 */

import React from 'react';
import { Paper, Typography } from '@mui/material';
import { tokens } from '../../design-system/tokens';

const InfoBox: React.FC = React.memo(() => {
  return (
    <Paper
      elevation={0}
      sx={{
        p: tokens.spacing.md,
        borderRadius: tokens.borderRadius.md,
        background: `${tokens.colors.semantic.info}22`, // 22 = ~13% opacity
        border: `1px solid ${tokens.colors.semantic.info}55`, // 55 = ~33% opacity
      }}
    >
      <Typography
        variant="caption"
        sx={{
          color: tokens.colors.text.secondary,
          fontSize: tokens.typography.fontSize.xs,
          lineHeight: tokens.typography.lineHeight.relaxed,
          display: 'block',
        }}
      >
        <strong style={{ color: tokens.colors.text.primary }}>Auto-Mastering</strong> analyzes your music in real-time
        and applies intelligent processing tailored to each track's unique characteristics.
        No presets needed!
      </Typography>
    </Paper>
  );
});

InfoBox.displayName = 'InfoBox';

export default InfoBox;
