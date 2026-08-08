/**
 * Tooltip Primitive Component
 *
 * Tooltip for additional information on hover.
 *
 * Usage:
 *   <Tooltip title="Click to play"><IconButton>...</IconButton></Tooltip>
 *   <Tooltip title="Info" placement="top">...</Tooltip>
 *
 * @see docs/UI_DESIGN_GUIDELINES.md
 */

import { styled } from '@mui/material/styles';
import MuiTooltip, { TooltipProps as MuiTooltipProps } from '@mui/material/Tooltip';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

export type TooltipProps = MuiTooltipProps;

const StyledTooltip = styled(MuiTooltip)({
  '& .MuiTooltip-tooltip': {
    background: themeVars.surfaceRaised,
    color: themeVars.textPrimary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.medium,
    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    boxShadow: tokens.shadows.lg,
    border: `1px solid ${tokens.colors.border.light}`,
  },
  '& .MuiTooltip-arrow': {
    color: themeVars.surfaceRaised,
    '&::before': {
      border: `1px solid ${tokens.colors.border.light}`,
    },
  },
});

export const Tooltip = (props: TooltipProps) => {
  return <StyledTooltip {...props} />;
};

export default Tooltip;
