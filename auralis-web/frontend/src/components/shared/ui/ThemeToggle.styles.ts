import { styled, Box, IconButton } from '@mui/material';
import { tokens } from '@/design-system';

export const ThemeToggleContainer = styled(Box)({
  display: 'inline-flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
});

export const ThemeToggleButton = styled(IconButton, {
  shouldForwardProp: (prop) => prop !== 'buttonSize' && prop !== 'isDark',
})<{ buttonSize: number; isDark: boolean }>(({ buttonSize, isDark }) => ({
  width: buttonSize,
  height: buttonSize,
  background: isDark ? tokens.colors.border.light : tokens.colors.bg.level3,
  backdropFilter: 'blur(10px)',
  border: `1px solid ${isDark ? tokens.colors.border.medium : tokens.colors.border.light}`,
  transition: tokens.transitions.slow_inOut,
  overflow: 'hidden',
  position: 'relative',
  '&:hover': {
    background: isDark ? tokens.colors.border.medium : tokens.colors.bg.level4,
    transform: 'scale(1.05) rotate(15deg)',
    boxShadow: isDark
      ? tokens.shadows.lg
      : tokens.shadows.md,
  },
  '&:active': {
    transform: 'scale(0.95) rotate(0deg)',
  },
}));

export const ThemeToggleBackground = styled(Box)({
  position: 'absolute',
  inset: 0,
  background: tokens.gradients.aurora,
  opacity: 0,
  transition: tokens.transitions.slow_inOut,
});

export const ThemeToggleIconContainer = styled(Box)({
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: tokens.transitions.verySlow_inOut,
});

export const ThemeToggleLabel = styled(Box)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.semibold,
  textTransform: 'uppercase',
  letterSpacing: tokens.typography.letterSpacing.loose,
});
