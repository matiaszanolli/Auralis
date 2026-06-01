import { createTheme, Theme } from '@mui/material/styles';
import { tokens } from '@/design-system';

// ============================================================================
// AURORA GRADIENTS — derived from tokens (single source of truth, #2766)
// ============================================================================
// #3597: every gradient endpoint resolves to a token. Hand-tuned hex strings
// previously fragmented the brand identity between gradient stops.
const _COSMIC_DEEP = '#0F2027';   // deepened bg.level0 for the cosmicBlue ramp
const _COSMIC_MID = '#203A43';
const _COSMIC_END = '#2C5364';

export const gradients = {
  aurora: tokens.gradients.aurora,
  // #3949 / DS-12: the dark accent stop now resolves to accent.primaryDark
  // (was a duplicated raw hex literal here and in the MUI palette below).
  auroraReverse: `linear-gradient(135deg, ${tokens.colors.accent.primary} 100%, ${tokens.colors.accent.primaryDark} 0%)`,
  neonSunset: `linear-gradient(135deg, ${tokens.colors.audioSemantic.harmonic} 0%, ${tokens.colors.accent.energy} 100%)`,
  deepOcean: `linear-gradient(135deg, ${tokens.colors.semantic.info} 0%, ${tokens.colors.semantic.success} 100%)`,
  electricPurple: `linear-gradient(135deg, ${tokens.colors.audioSemantic.harmonic} 0%, ${tokens.colors.accent.primary} 100%)`,
  cosmicBlue: `linear-gradient(135deg, ${_COSMIC_DEEP} 0%, ${_COSMIC_MID} 50%, ${_COSMIC_END} 100%)`,
  // Light theme gradients (softer) — derive from semantic info / harmonic accents
  auroraLight: `linear-gradient(135deg, ${tokens.colors.semantic.info} 0%, ${tokens.colors.audioSemantic.harmonic} 100%)`,
  sunsetLight: `linear-gradient(135deg, ${tokens.colors.audioSemantic.harmonic} 0%, ${tokens.colors.accent.energy} 100%)`,
};

// ============================================================================
// DARK THEME COLORS — derived from tokens (single source of truth, #2766)
// ============================================================================
export const darkColors = {
  background: {
    primary: tokens.colors.bg.level0,
    secondary: tokens.colors.bg.level1,
    surface: tokens.colors.bg.level2,
    hover: tokens.colors.bg.level3,
    glass: tokens.glass.subtle.background,
  },
  text: {
    primary: tokens.colors.text.primaryFull,
    secondary: tokens.colors.accent.tertiary,
    disabled: tokens.colors.text.disabled,
  },
  accent: {
    success: tokens.colors.semantic.success,
    error: tokens.colors.semantic.error,
    warning: tokens.colors.semantic.warning,
    info: tokens.colors.accent.secondary,
  },
  neon: {
    pink: tokens.colors.audioSemantic.harmonic,
    // #3597: dark-mode purple/magenta accent — kept distinct from the
    // primary brand violet so neon highlights have their own identity.
    // Sourced from the harmonic palette at lower lightness (#3949).
    purple: tokens.colors.audioSemantic.harmonicDark,
    blue: tokens.colors.semantic.info,
    cyan: tokens.colors.semantic.success,
    orange: tokens.colors.accent.energy,
  },
  glass: {
    border: tokens.colors.opacityScale.white.light,
    highlight: tokens.colors.opacityScale.white.veryLight,
  },
};

// ============================================================================
// LIGHT THEME COLORS (#3597 — sourced from tokens.colors.lightMode)
// ============================================================================
// Semantic colors share hue with the dark mode (`semantic.*`) so state
// identity is consistent across themes; surface lifts and neon dimming
// account for the brighter canvas.
export const lightColors = {
  background: tokens.colors.lightMode.background,
  text: tokens.colors.lightMode.text,
  accent: tokens.colors.lightMode.accent,
  neon: tokens.colors.lightMode.neon,
  glass: {
    border: tokens.colors.opacityScale.accent.lighter,
    highlight: tokens.colors.opacityScale.accent.minimal,
  },
};

// ============================================================================
// GLASSMORPHISM UTILITIES - Auralis Design Language v1.2.0
// Subtle glass borders catch light - depth via borders, spacing, and shadow (§4.1)
// ============================================================================
export const glassEffects = {
  // Subtle glass panel (cards, sidebars) - Enhanced for glossy aesthetic
  panel: (isDark: boolean) => ({
    background: isDark ? tokens.glass.subtle.background : lightColors.background.glass,
    backdropFilter: 'blur(20px) saturate(1.1)',
    WebkitBackdropFilter: 'blur(20px) saturate(1.1)',
    border: '1px solid ' + (isDark
      ? tokens.colors.opacityScale.white.light
      : tokens.colors.opacityScale.accent.light),
    boxShadow: isDark
      ? '0 4px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px ' + tokens.colors.opacityScale.white.veryLight
      : '0 4px 16px ' + tokens.colors.opacityScale.accent.ultraLight + ', 0 0 0 1px ' + tokens.colors.opacityScale.white.light,
  }),

  // Strong glass (modals, popovers) - Maximum glossy effect
  strong: (isDark: boolean) => ({
    // #3948: token-backed per-mode backgrounds (was raw rgba literals).
    background: isDark
      ? tokens.glass.strong.backgroundDark
      : tokens.glass.strong.backgroundLight,
    backdropFilter: 'blur(32px) saturate(1.2)',     // Maximum blur + saturation
    WebkitBackdropFilter: 'blur(32px) saturate(1.2)',
    border: '1px solid ' + (isDark
      ? tokens.colors.opacityScale.white.lighter
      : tokens.colors.opacityScale.accent.standard),
    boxShadow: isDark
      ? '0 16px 48px rgba(0, 0, 0, 0.24), 0 0 0 1px ' + tokens.colors.opacityScale.white.light
      : '0 16px 48px ' + tokens.colors.opacityScale.accent.light + ', 0 0 0 1px ' + tokens.colors.opacityScale.white.lighter,
  }),

  // Minimal glass (hover states, tooltips) - Medium strength
  minimal: (isDark: boolean) => ({
    // #3948: token-backed per-mode backgrounds (was raw rgba literals). Maps to
    // the medium glass token — "minimal" here is medium strength per the label.
    background: isDark
      ? tokens.glass.medium.backgroundDark
      : tokens.glass.medium.backgroundLight,
    backdropFilter: 'blur(28px) saturate(1.15)',    // Stronger blur + saturation
    WebkitBackdropFilter: 'blur(28px) saturate(1.15)',
    border: '1px solid ' + (isDark
      ? tokens.colors.opacityScale.white.light
      : tokens.colors.opacityScale.accent.light),
  }),

  // Glow effect for active elements
  glow: (isDark: boolean, color: string = tokens.colors.accent.primary) => ({
    boxShadow: isDark
      ? `0 0 20px ${color}66, 0 0 40px ${color}33`
      : `0 0 20px ${color}33, 0 0 40px ${color}1a`,
  }),
};

// ============================================================================
// CREATE THEME FUNCTION
// ============================================================================
export const createAuralisTheme = (mode: 'light' | 'dark'): Theme => {
  const isDark = mode === 'dark';
  const colors = isDark ? darkColors : lightColors;

  // #3597/#3949: MUI light/dark variants derived from the brand accents. MUI
  // uses these for auto-generated hover/focus shades; we pre-compute them to
  // keep the palette stable across MUI updates instead of relying on its
  // internal colorManipulator heuristics. Now token-backed (no magic hex).
  const PRIMARY_LIGHT = tokens.colors.accent.primaryLight;
  const PRIMARY_DARK = tokens.colors.accent.primaryDark;
  const SECONDARY_LIGHT = tokens.colors.accent.secondaryLight;
  const SECONDARY_DARK = tokens.colors.accent.secondaryDark;

  return createTheme({
    // Opt out of MUI v6's CSS-variables-by-default theme. The custom
    // --bg-* / --text-* / --glass-border variables written from
    // ThemeContext.tsx live in a separate namespace from MUI's --mui-*,
    // but the explicit opt-out documents the deliberate split (#3487).
    cssVariables: false,
    palette: {
      mode,
      primary: {
        main: tokens.colors.accent.primary,
        light: PRIMARY_LIGHT,
        dark: PRIMARY_DARK,
      },
      secondary: {
        main: tokens.colors.accent.secondary,
        light: SECONDARY_LIGHT,
        dark: SECONDARY_DARK,
      },
      background: {
        default: colors.background.primary,
        paper: colors.background.secondary,
      },
      text: {
        primary: colors.text.primary,
        secondary: colors.text.secondary,
        disabled: colors.text.disabled,
      },
      success: {
        main: colors.accent.success,
      },
      error: {
        main: colors.accent.error,
      },
      warning: {
        main: colors.accent.warning,
      },
      info: {
        main: colors.accent.info,
      },
    },
    typography: {
      fontFamily: tokens.typography.fontFamily.primary,
      h1: {
        fontSize: tokens.typography.fontSize['3xl'],
        fontWeight: tokens.typography.fontWeight.bold,
        letterSpacing: '-0.5px',
      },
      h2: {
        fontSize: tokens.typography.fontSize.xl,
        fontWeight: tokens.typography.fontWeight.semibold,
        letterSpacing: '-0.25px',
      },
      h3: {
        fontSize: tokens.typography.fontSize.lg,
        fontWeight: tokens.typography.fontWeight.semibold,
      },
      h4: {
        fontSize: tokens.typography.fontSize.lg,
        fontWeight: tokens.typography.fontWeight.semibold,
      },
      body1: {
        fontSize: tokens.typography.fontSize.md,
        lineHeight: tokens.typography.lineHeight.normal,
      },
      body2: {
        fontSize: tokens.typography.fontSize.base,
        lineHeight: tokens.typography.lineHeight.normal,
      },
      caption: {
        fontSize: tokens.typography.fontSize.xs,
        color: colors.text.secondary,
        letterSpacing: '0.5px',
      },
      button: {
        textTransform: 'none',
        fontWeight: tokens.typography.fontWeight.semibold,
      },
    },
    shape: {
      borderRadius: parseInt(tokens.borderRadius.sm),
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: tokens.borderRadius.sm,
            padding: '10px 24px',
            fontWeight: tokens.typography.fontWeight.semibold,
            transition: tokens.transitions.state_inOut,
          },
          contained: {
            boxShadow: 'none',
            '&:hover': {
              boxShadow: isDark
                ? '0 4px 12px rgba(0, 0, 0, 0.3)'
                : `0 4px 12px ${tokens.colors.opacityScale.accent.standard}`,
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            ...glassEffects.panel(isDark),
            backgroundImage: 'none',
            transition: tokens.transitions.state_inOut,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            ...glassEffects.strong(isDark),
          },
        },
      },
      MuiSlider: {
        styleOverrides: {
          root: {
            color: tokens.colors.accent.primary,
            height: 6,
          },
          thumb: {
            width: 16,
            height: 16,
            backgroundColor: tokens.colors.text.primaryFull,
            border: isDark ? 'none' : `2px solid ${tokens.colors.accent.primary}`,
            '&:hover, &.Mui-focusVisible': {
              boxShadow: `0 0 0 8px ${tokens.colors.opacityScale.accent.lighter}`,
            },
          },
          track: {
            height: 6,
            borderRadius: 3,
          },
          rail: {
            height: 6,
            borderRadius: 3,
            backgroundColor: colors.background.surface,
            opacity: 1,
          },
        },
      },
      MuiSwitch: {
        styleOverrides: {
          root: {
            width: 52,
            height: 32,
            padding: 0,
          },
          switchBase: {
            padding: 4,
            '&.Mui-checked': {
              transform: 'translateX(20px)',
              color: tokens.colors.text.primaryFull,
              '& + .MuiSwitch-track': {
                background: gradients.aurora,
                opacity: 1,
              },
            },
          },
          thumb: {
            width: 24,
            height: 24,
            boxShadow: isDark
              ? '0 2px 4px rgba(0, 0, 0, 0.2)'
              : '0 2px 4px rgba(0, 0, 0, 0.1)',
          },
          track: {
            borderRadius: 16,
            backgroundColor: colors.background.surface,
            opacity: 1,
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            transition: tokens.transitions.state_inOut,
            '&:hover': {
              transform: 'scale(1.1)',
              background: isDark
                ? tokens.colors.opacityScale.white.veryLight
                : tokens.colors.opacityScale.accent.minimal,
            },
          },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            ...glassEffects.strong(isDark),
            fontSize: tokens.typography.fontSize.xs,
          },
        },
      },
    },
  });
};

// Export default dark theme for backward compatibility
export const auralisTheme = createAuralisTheme('dark');
export { darkColors as colors }; // For backward compatibility
export default auralisTheme;
