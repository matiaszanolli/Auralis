import { styled, Box, IconButton } from '@mui/material';
import { gradients, auroraOpacity } from '../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

export const ThemeToggleContainer = styled(Box)({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
});

export const ThemeToggleButton = styled(IconButton, {
  shouldForwardProp: (prop) => prop !== 'buttonSize' && prop !== 'isDark',
})<{ buttonSize: number; isDark: boolean }>(({ buttonSize, isDark }) => ({
  width: buttonSize,
  height: buttonSize,
  background: isDark ? tokens.colors.border.light : auroraOpacity.ultraLight,
  backdropFilter: 'blur(10px)',
  border: `1px solid ${isDark ? tokens.colors.border.medium : auroraOpacity.lighter}`,
  transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
  overflow: 'hidden',
  position: 'relative',
  '&:hover': {
    background: isDark ? tokens.colors.border.medium : auroraOpacity.light,
    transform: 'scale(1.05) rotate(15deg)',
    boxShadow: isDark
      ? `0 4px 20px ${auroraOpacity.strong}`
      : `0 4px 20px ${auroraOpacity.standard}`,
  },
  '&:active': {
    transform: 'scale(0.95) rotate(0deg)',
  },
}));

export const ThemeToggleBackground = styled(Box)({
  position: 'absolute',
  inset: 0,
  background: gradients.aurora,
  opacity: 0,
  transition: 'opacity 0.4s ease',
});

export const ThemeToggleIconContainer = styled(Box)({
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
});

export const ThemeToggleLabel = styled(Box)({
  fontSize: 12,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 1,
});
