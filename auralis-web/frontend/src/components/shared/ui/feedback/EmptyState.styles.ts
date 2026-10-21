/**
 * EmptyState Styled Components
 *
 * Centralized styling for EmptyState and related components.
 */

import { Box, Typography, styled } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

export const Container = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: `${tokens.spacing.xxxl} ${tokens.spacing.xl}`,
  textAlign: 'center',
  minHeight: '300px',
});

export const IconContainer = styled(Box)({
  marginBottom: tokens.spacing.lg,
  '& .MuiSvgIcon-root': {
    // #3639: tokens.typography.fontSize.huge (80px) — named display scale
    // for empty-state placeholder glyphs.
    fontSize: tokens.typography.fontSize.huge,
    color: themeVars.textMuted,
    transition: tokens.transitions.base_inOut,
  },

  '&:hover .MuiSvgIcon-root': {
    // #5641 sibling: fixed cyan #47D6FF is ~1.6:1 on a light tint; the accent
    // is the readable-on-both-modes brand color.
    color: themeVars.accent,
    transform: 'scale(1.1)',
  },
});

export const Title = styled(Typography)({
  fontSize: tokens.typography.fontSize['2xl'],
  fontWeight: tokens.typography.fontWeight.semibold,
  color: themeVars.textPrimary,
  marginBottom: tokens.spacing.sm,
});

export const Description = styled(Typography)({
  fontSize: tokens.typography.fontSize.base,
  color: themeVars.textSecondary,
  marginBottom: tokens.spacing.lg,
  maxWidth: '400px',
  lineHeight: tokens.typography.lineHeight.relaxed,
});
