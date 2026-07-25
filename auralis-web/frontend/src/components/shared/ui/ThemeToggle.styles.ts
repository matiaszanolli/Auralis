
import { tokens } from '@/design-system';
import { IconButton } from '@/design-system';
import { styled, Box } from '@mui/material';
import { themeVars } from '@/theme/semanticTheme';

export const ThemeToggleContainer = styled(Box)({
  display: 'inline-flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
});

export const ThemeToggleButton = styled(IconButton, {
  shouldForwardProp: (prop) => prop !== 'buttonSize' && prop !== 'isDark',
})<{ buttonSize: number; isDark: boolean }>(({ buttonSize }) => ({
  width: buttonSize,
  height: buttonSize,
  background: themeVars.surfaceSecondary,
  border: `1px solid ${themeVars.borderDefault}`,
  color: themeVars.textSecondary,
  transition: tokens.transitions.hover_out,
  overflow: 'hidden',
  position: 'relative',
  '&:hover': {
    background: themeVars.accentSoft,
    color: themeVars.textPrimary,
    borderColor: themeVars.borderStrong,
  },
  '&:active': {
    background: themeVars.surfaceRaised,
  },
}));

export const ThemeToggleBackground = styled(Box)({
  position: 'absolute',
  inset: 0,
  background: themeVars.accent,
  opacity: 0,
  transition: tokens.transitions.slow_inOut,
});

export const ThemeToggleIconContainer = styled(Box)({
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: tokens.transitions.state_inOut,
});

export const ThemeToggleLabel = styled(Box)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.semibold,
  textTransform: 'uppercase',
  letterSpacing: tokens.typography.letterSpacing.loose,
});
