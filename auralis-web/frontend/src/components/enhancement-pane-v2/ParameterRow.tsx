/**
 * ParameterRow Component
 *
 * Reusable row for displaying a single processing parameter.
 * Handles label, icon, value display, and conditional rendering.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { SvgIconProps } from '@mui/material';
import { tokens } from '../../design-system/tokens';

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
        <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
          {Icon && (
            <Icon sx={{ fontSize: tokens.typography.fontSize.sm, mr: tokens.spacing.xs, verticalAlign: 'middle' }} />
          )}
          {label}
        </Typography>
        <Typography
          variant="body2"
          sx={{
            color: valueColor,
            fontWeight: tokens.typography.fontWeight.semibold,
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
