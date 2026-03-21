import { createTheme, Theme } from '@mui/material/styles';
import { tokens } from '@/design-system';

// ============================================================================
// AURORA GRADIENTS — derived from tokens (single source of truth, #2766)
// ============================================================================
export const gradients = {
  aurora: tokens.gradients.aurora,
  auroraReverse: `linear-gradient(135deg, ${tokens.colors.accent.primary} 100%, #5A5CC4 0%)`,
  neonSunset: `linear-gradient(135deg, ${tokens.colors.audioSemantic.harmonic} 0%, ${tokens.colors.accent.energy} 100%)`,
  deepOcean: `linear-gradient(135deg, ${tokens.colors.semantic.info} 0%, ${tokens.colors.semantic.success} 100%)`,
  electricPurple: `linear-gradient(135deg, ${tokens.colors.audioSemantic.harmonic} 0%, ${tokens.colors.accent.primary} 100%)`,
  cosmicBlue: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',
  // Light theme gradients (softer)
  auroraLight: 'linear-gradient(135deg, #8b9cf7 0%, #9668c4 100%)',
  sunsetLight: 'linear-gradient(135deg, #ffb3cc 0%, #ffd699 100%)',
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
    purple: '#c44569',
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
// LIGHT THEME COLORS (Clean, minimal — uses token brand colors, #2766)
// ============================================================================
export const lightColors = {
  background: {
    primary: '#f8f9fd',
    secondary: '#ffffff',
    surface: '#fafbff',
    hover: '#f0f2f8',
    glass: 'rgba(255, 255, 255, 0.7)',
  },
  text: {
    primary: '#1a1f3a',
    secondary: '#5a6280',
    disabled: '#9ca3b8',
  },
  accent: {
    success: '#00a388',
    error: '#e63946',
    warning: '#e68a00',
    info: '#3d68d4',
  },
  neon: {
    pink: '#d9577e',
    purple: '#a03d5a',
    blue: '#3d68d4',
    cyan: '#1fb874',
    orange: '#e68a00',
  },
  glass: {
    border: `rgba(115, 102, 240, 0.15)`,    // Uses accent.primary RGB
    highlight: `rgba(115, 102, 240, 0.05)`,
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
    background: isDark
      ? 'rgba(21, 29, 47, 0.65)'                    // Increased opacity for solid presence
      : 'rgba(255, 255, 255, 0.85)',
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
    background: isDark
      ? 'rgba(21, 29, 47, 0.45)'                    // Increased opacity
      : 'rgba(255, 255, 255, 0.6)',
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

  return createTheme({
    palette: {
      mode,
      primary: {
        main: tokens.colors.accent.primary,
        light: '#8B7CF7',
        dark: '#5A5CC4',
      },
      secondary: {
        main: tokens.colors.accent.secondary,
        light: '#6FE0FF',
        dark: '#00BCC4',
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
        fontWeight: 600,
      },
    },
    shape: {
      borderRadius: 8,
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: '8px',
            padding: '10px 24px',
            fontWeight: 600,
            transition: 'all 0.3s ease',
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
            transition: 'all 0.3s ease',
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
            backgroundColor: '#fff',
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
              color: '#fff',
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
            transition: 'all 0.3s ease',
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
            fontSize: '12px',
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
