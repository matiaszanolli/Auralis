/**
 * EmptyState Styled Components
 *
 * Centralized styling for EmptyState and related components.
 */

import { Box, Typography, styled } from '@mui/material';
import { tokens } from '@/design-system';

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
    fontSize: '80px',
    color: tokens.colors.text.tertiary,
    transition: tokens.transitions.base_inOut,
  },

  '&:hover .MuiSvgIcon-root': {
    color: tokens.colors.accent.secondary,
    transform: 'scale(1.1)',
  },
});

export const Title = styled(Typography)({
  fontSize: tokens.typography.fontSize['2xl'],
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.primary,
  marginBottom: tokens.spacing.sm,
});

export const Description = styled(Typography)({
  fontSize: tokens.typography.fontSize.base,
  color: tokens.colors.text.secondary,
  marginBottom: tokens.spacing.lg,
  maxWidth: '400px',
  lineHeight: tokens.typography.lineHeight.relaxed,
});
