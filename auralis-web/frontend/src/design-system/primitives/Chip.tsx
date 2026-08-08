/**
 * Chip Primitive Component
 *
 * Compact, dismissible tag component for displaying labels, categories, or selections.
 *
 * Usage:
 *   <Chip label="React" />
 *   <Chip label="Delete me" onDelete={() => {}} />
 *
 * @see docs/UI_DESIGN_GUIDELINES.md
 */

import MuiChip, { ChipProps as MuiChipProps } from '@mui/material/Chip';
import { styled } from '@mui/material/styles';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

export type ChipProps = MuiChipProps;

const StyledChip = styled(MuiChip)({
  backgroundColor: themeVars.surfaceRaised,
  color: themeVars.textPrimary,
  fontSize: tokens.typography.fontSize.sm,
  fontWeight: tokens.typography.fontWeight.medium,
  border: `1px solid ${tokens.colors.border.light}`,

  '&:hover': {
    backgroundColor: themeVars.surfaceOverlay,
  },

  '& .MuiChip-deleteIcon': {
    color: themeVars.textSecondary,
    '&:hover': {
      color: tokens.colors.semantic.error,
    },
  },

  // Variant support
  '&.MuiChip-filled': {
    backgroundColor: themeVars.surfaceRaised,
  },

  '&.MuiChip-outlined': {
    border: `1px solid ${tokens.colors.border.medium}`,
    backgroundColor: 'transparent',
  },
});

export const Chip = (props: ChipProps) => {
  return <StyledChip {...props} />;
};

export default Chip;
