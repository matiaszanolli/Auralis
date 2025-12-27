/**
 * ParameterRow Component
 *
 * Reusable row for displaying a single processing parameter.
 * Handles label, icon, value display, and conditional rendering.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { SvgIconProps } from '@mui/material';
import { tokens } from '@/design-system';

interface ParameterRowProps {
  label: string;
  value: string;
  icon?: React.ComponentType<SvgIconProps>;
  valueColor?: string;
}

export const ParameterRow: React.FC<ParameterRowProps> = React.memo(
  ({
    label,
    value,
    icon: Icon,
    valueColor = tokens.colors.text.primary,
  }) => {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography
          variant="body2"
          sx={{
            color: tokens.colors.text.tertiary, // Changed from secondary to tertiary (less visual weight)
            fontSize: tokens.typography.fontSize.sm,
            opacity: 0.85, // Fade by ~15% to make labels less prominent
          }}
        >
          {Icon && (
            <Icon sx={{ fontSize: tokens.typography.fontSize.sm, mr: tokens.spacing.xs, verticalAlign: 'middle', opacity: 0.7 }} />
          )}
          {label}
        </Typography>
        <Typography
          variant="body2"
          sx={{
            color: valueColor,
            fontWeight: tokens.typography.fontWeight.medium, // Reduced from semibold
            fontSize: tokens.typography.fontSize.sm,
          }}
        >
          {value}
        </Typography>
      </Box>
    );
  }
);

ParameterRow.displayName = 'ParameterRow';
