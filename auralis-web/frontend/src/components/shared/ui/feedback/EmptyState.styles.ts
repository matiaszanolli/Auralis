/**
 * EmptyState Styled Components
 *
 * Centralized styling for EmptyState and related components.
 */

import { Box, Typography, styled } from '@mui/material';
import { auroraOpacity } from '../../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

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
    color: auroraOpacity.strong,
    transition: 'all 200ms ease',
  },

  '&:hover .MuiSvgIcon-root': {
    color: auroraOpacity.veryStrong,
    transform: 'scale(1.1)',
  },
});

export const Title = styled(Typography)({
  fontSize: '24px',
  fontWeight: 600,
  color: tokens.colors.text.primary,
  marginBottom: tokens.spacing.sm,
});

export const Description = styled(Typography)({
  fontSize: '14px',
  color: tokens.colors.text.secondary,
  marginBottom: tokens.spacing.lg,
  maxWidth: '400px',
  lineHeight: 1.6,
});
