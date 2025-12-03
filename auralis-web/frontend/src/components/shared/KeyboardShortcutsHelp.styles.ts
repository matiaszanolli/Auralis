import { styled, Paper, Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';

export const CategorySection = styled(Paper)(({ theme }) => ({
  background: tokens.colors.bg.level3,
  border: `1px solid ${tokens.colors.border.light}`,
  borderRadius: tokens.borderRadius.lg,
  padding: tokens.spacing.md,
  marginBottom: tokens.spacing.md,
}));

export const ShortcutRow = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: `${tokens.spacing.sm} 0`,
  borderBottom: `1px solid ${tokens.colors.bg.level3}`,
  '&:last-child': {
    borderBottom: 'none',
  },
}));

export const ShortcutKey = styled(Box)(({ theme }) => ({
  background: tokens.colors.bg.level2,
  border: `1px solid ${tokens.colors.border.heavy}`,
  borderRadius: tokens.borderRadius.sm,
  padding: `${tokens.spacing.sm} 12px`,
  fontFamily: tokens.typography.fontFamily.mono,
  fontSize: tokens.typography.fontSize.base,
  fontWeight: tokens.typography.fontWeight.bold,
  color: tokens.colors.accent.primary,
  minWidth: '80px',
  textAlign: 'center',
  boxShadow: tokens.shadows.sm,
}));

export const ShortcutDescription = styled(Typography)(({ theme }) => ({
  color: tokens.colors.text.tertiary,
  fontSize: tokens.typography.fontSize.base,
}));

export const CategoryTitle = styled(Typography)(({ theme }) => ({
  color: tokens.colors.accent.primary,
  fontWeight: tokens.typography.fontWeight.bold,
  fontSize: tokens.typography.fontSize.md,
  marginBottom: tokens.spacing.sm,
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
}));

export const EmptyStateBox = styled(Box)(({ theme }) => ({
  textAlign: 'center',
  padding: `40px ${tokens.spacing.md}`,
  color: tokens.colors.text.muted,
}));

export const DialogContentBoxStyles = {
  p: 3,
};
