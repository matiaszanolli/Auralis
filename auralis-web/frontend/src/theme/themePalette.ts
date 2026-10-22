import type { PaletteOptions } from '@mui/material/styles';
import { tokens } from '@/design-system';
import type { SemanticTheme, ThemeMode } from './semanticTheme';

/**
 * MUI palette for a mode. Split out of themeConfig.ts (#5841).
 *
 * #3597/#3949: MUI light/dark variants are derived from the brand accents.
 * MUI uses these for auto-generated hover/focus shades; we pre-compute them to
 * keep the palette stable across MUI updates instead of relying on its
 * internal colorManipulator heuristics. Token-backed (no magic hex).
 */
export const createPalette = (mode: ThemeMode, semantic: SemanticTheme): PaletteOptions => {
  const PRIMARY_LIGHT = tokens.colors.accent.primaryLight;
  const PRIMARY_DARK = tokens.colors.accent.primaryDark;
  const SECONDARY_LIGHT = tokens.colors.accent.secondaryLight;
  const SECONDARY_DARK = tokens.colors.accent.secondaryDark;

  return   {
    mode,
    primary: {
      main: tokens.colors.accent.primary,
      light: PRIMARY_LIGHT,
      dark: PRIMARY_DARK,
      contrastText: semantic.onAccent,
    },
    secondary: {
      main: tokens.colors.accent.secondary,
      light: SECONDARY_LIGHT,
      dark: SECONDARY_DARK,
      contrastText: semantic.onAccent,
    },
    background: {
      default: semantic.canvas,
      paper: semantic.surfacePrimary,
    },
    text: {
      primary: semantic.textPrimary,
      secondary: semantic.textSecondary,
      disabled: semantic.textDisabled,
    },
    success: {
      main: semantic.success,
    },
    error: {
      main: semantic.error,
      contrastText: semantic.onError,
    },
    warning: {
      main: semantic.warning,
    },
    info: {
      main: semantic.info,
    },
  };
};
