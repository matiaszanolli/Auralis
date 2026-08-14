/**
 * SearchBar Styled Components
 */

import { tokens } from '@/design-system';
import { IconButton } from '@/design-system';
import { styled, Typography } from '@mui/material';
import { themeVars } from '@/theme/semanticTheme';

export const ClearButton = styled(IconButton)({
  padding: tokens.spacing.cluster,
  color: themeVars.textSecondary,
  transition: tokens.transitions.hover_out,

  '&:hover': {
    color: themeVars.textPrimary,
    background: tokens.colors.opacityScale.accent.ultraLight,
  },
});

export const ResultCount = styled(Typography)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.medium,
  color: themeVars.textSecondary,
  padding: `0 ${tokens.spacing.md}`,
  whiteSpace: 'nowrap',
});
