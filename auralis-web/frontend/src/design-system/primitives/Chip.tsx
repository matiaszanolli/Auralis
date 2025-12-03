/**
 * Chip Primitive Component
 *
 * Compact, dismissible tag component for displaying labels, categories, or selections.
 *
 * Usage:
 *   <Chip label="React" />
 *   <Chip label="Delete me" onDelete={() => {}} />
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import MuiChip, { ChipProps as MuiChipProps } from '@mui/material/Chip';
import { styled } from '@mui/material/styles';
import { tokens } from '../tokens';

export type ChipProps = MuiChipProps;

const StyledChip = styled(MuiChip)({
  backgroundColor: tokens.colors.bg.level3,
  color: tokens.colors.text.primary,
  fontSize: tokens.typography.fontSize.sm,
  fontWeight: tokens.typography.fontWeight.medium,
  border: `1px solid ${tokens.colors.border.light}`,

  '&:hover': {
    backgroundColor: tokens.colors.bg.level4,
  },

  '& .MuiChip-deleteIcon': {
    color: tokens.colors.text.secondary,
    '&:hover': {
      color: tokens.colors.semantic.error,
    },
  },

  // Variant support
  '&.MuiChip-filled': {
    backgroundColor: tokens.colors.bg.level3,
  },

  '&.MuiChip-outlined': {
    border: `1px solid ${tokens.colors.border.medium}`,
    backgroundColor: 'transparent',
  },
});

export const Chip: React.FC<ChipProps> = (props) => {
  return <StyledChip {...props} />;
};

export default Chip;
