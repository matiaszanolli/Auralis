/**
 * SearchBar Styled Components
 */

import { tokens } from '@/design-system';
import { IconButton } from '@/design-system';
import { styled, Typography } from '@mui/material';

export const ClearButton = styled(IconButton)({
  padding: tokens.spacing.cluster,
  color: tokens.colors.text.secondary,
  transition: tokens.transitions.hover_out,

  '&:hover': {
    color: tokens.colors.text.primary,
    background: tokens.colors.opacityScale.accent.ultraLight,
  },
});

export const ResultCount = styled(Typography)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.medium,
  color: tokens.colors.text.secondary,
  padding: `0 ${tokens.spacing.md}`,
  whiteSpace: 'nowrap',
});
