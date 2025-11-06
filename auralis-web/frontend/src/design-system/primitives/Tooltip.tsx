/**
 * Tooltip Primitive Component
 *
 * Tooltip for additional information on hover.
 *
 * Usage:
 *   <Tooltip title="Click to play"><IconButton>...</IconButton></Tooltip>
 *   <Tooltip title="Info" placement="top">...</Tooltip>
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import MuiTooltip, { TooltipProps as MuiTooltipProps } from '@mui/material/Tooltip';
import { tokens } from '../tokens';

export type TooltipProps = MuiTooltipProps;

const StyledTooltip = styled(MuiTooltip)({
  '& .MuiTooltip-tooltip': {
    background: tokens.colors.bg.elevated,
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.medium,
    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    boxShadow: tokens.shadows.lg,
    border: `1px solid ${tokens.colors.border.light}`,
  },
  '& .MuiTooltip-arrow': {
    color: tokens.colors.bg.elevated,
    '&::before': {
      border: `1px solid ${tokens.colors.border.light}`,
    },
  },
});

export const Tooltip: React.FC<TooltipProps> = (props) => {
  return <StyledTooltip {...props} />;
};

export default Tooltip;
