import { createTheme, Theme } from '@mui/material/styles';

// ============================================================================
// AURORA GRADIENTS (Shared between themes)
// ============================================================================
export const gradients = {
  aurora: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  auroraReverse: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
  neonSunset: 'linear-gradient(135deg, #ff6b9d 0%, #ffa502 100%)',
  deepOcean: 'linear-gradient(135deg, #4b7bec 0%, #26de81 100%)',
  electricPurple: 'linear-gradient(135deg, #c44569 0%, #667eea 100%)',
  cosmicBlue: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',
  // Light theme gradients (softer)
  auroraLight: 'linear-gradient(135deg, #8b9cf7 0%, #9668c4 100%)',
  sunsetLight: 'linear-gradient(135deg, #ffb3cc 0%, #ffd699 100%)',
};

// ============================================================================
// DARK THEME COLORS - Auralis Design Language v1.2.0
// ============================================================================
export const darkColors = {
  background: {
    primary: '#0B1020',      // Deep blue-black (canonical base - Design Language §2.1)
    secondary: '#101729',    // Slightly lifted navy
    surface: '#151D2F',      // Surfaces (subtle lift)
    hover: '#1A2338',        // Hover states
    glass: 'rgba(21, 29, 47, 0.30)',  // Glassmorphism background (calm by default)
  },
  text: {
    primary: '#FFFFFF',      // Ultra White - titles, emphasis
    secondary: '#C1C8EF',    // Lavender Smoke - secondary text, labels
    disabled: '#4A5073',     // Disabled text (very muted)
  },
  accent: {
    success: '#10B981',      // Success (positive)
    error: '#EF4444',        // Error (critical)
    warning: '#F59E0B',      // Warm Amber - warnings
    info: '#47D6FF',         // Teal/Cyan - audio state
  },
  neon: {
    pink: '#ff6b9d',
    purple: '#c44569',
    blue: '#4b7bec',
    cyan: '#26de81',
    orange: '#ffa502',
  },
  glass: {
    border: 'rgba(255, 255, 255, 0.1)',
    highlight: 'rgba(255, 255, 255, 0.05)',
  },
};

// ============================================================================
// LIGHT THEME COLORS (Clean, minimal, no Vista vibes)
// ============================================================================
export const lightColors = {
  background: {
    primary: '#f8f9fd',      // Soft light blue-gray (main background)
    secondary: '#ffffff',    // Pure white (surfaces)
    surface: '#fafbff',      // Very light blue (cards/panels)
    hover: '#f0f2f8',        // Subtle hover
    glass: 'rgba(255, 255, 255, 0.7)',  // Glassmorphism background
  },
  text: {
    primary: '#1a1f3a',      // Deep navy (reversed from dark)
    secondary: '#5a6280',    // Mid-tone gray
    disabled: '#9ca3b8',     // Light gray
  },
  accent: {
    success: '#00a388',      // Darker teal for contrast
    error: '#e63946',        // Darker red
    warning: '#e68a00',      // Darker orange
    info: '#3d68d4',         // Darker blue
  },
  neon: {
    pink: '#d9577e',         // Muted pink
    purple: '#a03d5a',       // Muted purple
    blue: '#3d68d4',         // Muted blue
    cyan: '#1fb874',         // Muted cyan
    orange: '#e68a00',       // Muted orange
  },
  glass: {
    border: 'rgba(102, 126, 234, 0.15)',     // Subtle purple tint
    highlight: 'rgba(102, 126, 234, 0.05)',  // Very subtle highlight
  },
};

// ============================================================================
// GLASSMORPHISM UTILITIES - Auralis Design Language v1.2.0
// Subtle glass borders catch light - depth via borders, spacing, and shadow (§4.1)
// ============================================================================
export const glassEffects = {
  // Subtle glass panel (cards, sidebars) - Enhanced for glossy aesthetic
  panel: (isDark: boolean) => ({
    background: isDark ? 'rgba(21, 29, 47, 0.30)' : lightColors.background.glass,
    backdropFilter: 'blur(20px) saturate(1.1)',     // Stronger blur + saturation boost
    WebkitBackdropFilter: 'blur(20px) saturate(1.1)',
    border: isDark
      ? '1px solid rgba(255, 255, 255, 0.10)'       // More visible glass border
      : '1px solid rgba(102, 126, 234, 0.12)',
    boxShadow: isDark
      ? '0 4px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.05)' // Deeper shadow + inner glow
      : '0 4px 16px rgba(102, 126, 234, 0.08), 0 0 0 1px rgba(255, 255, 255, 0.1)',
  }),

  // Strong glass (modals, popovers) - Maximum glossy effect
  strong: (isDark: boolean) => ({
    background: isDark
      ? 'rgba(21, 29, 47, 0.65)'                    // Increased opacity for solid presence
      : 'rgba(255, 255, 255, 0.85)',
    backdropFilter: 'blur(32px) saturate(1.2)',     // Maximum blur + saturation
    WebkitBackdropFilter: 'blur(32px) saturate(1.2)',
    border: isDark
      ? '1px solid rgba(255, 255, 255, 0.15)'       // Most visible border
      : '1px solid rgba(102, 126, 234, 0.18)',
    boxShadow: isDark
      ? '0 16px 48px rgba(0, 0, 0, 0.24), 0 0 0 1px rgba(255, 255, 255, 0.12)' // Deep shadow + strong inner glow
      : '0 16px 48px rgba(102, 126, 234, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.15)',
  }),

  // Minimal glass (hover states, tooltips) - Medium strength
  minimal: (isDark: boolean) => ({
    background: isDark
      ? 'rgba(21, 29, 47, 0.45)'                    // Increased opacity
      : 'rgba(255, 255, 255, 0.6)',
    backdropFilter: 'blur(28px) saturate(1.15)',    // Stronger blur + saturation
    WebkitBackdropFilter: 'blur(28px) saturate(1.15)',
    border: isDark
      ? '1px solid rgba(255, 255, 255, 0.12)'       // More visible border
      : '1px solid rgba(102, 126, 234, 0.12)',
  }),

  // Glow effect for active elements
  glow: (isDark: boolean, color: string = '#7366F0') => ({
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
        main: '#7366F0',        // Soft Violet/Indigo - primary brand accent (Design Language §2.1)
        light: '#8B7CF7',
        dark: '#5A5CC4',
      },
      secondary: {
        main: '#47D6FF',        // Teal/Cyan - audio state (Design Language §2.1)
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
      fontFamily: [
        'Inter',
        '-apple-system',
        'BlinkMacSystemFont',
        '"Segoe UI"',
        'Roboto',
        '"Helvetica Neue"',
        'Arial',
        'sans-serif',
      ].join(','),
      h1: {
        fontSize: '32px',
        fontWeight: 700,
        letterSpacing: '-0.5px',
      },
      h2: {
        fontSize: '24px',
        fontWeight: 600,
        letterSpacing: '-0.25px',
      },
      h3: {
        fontSize: '20px',
        fontWeight: 600,
      },
      h4: {
        fontSize: '18px',
        fontWeight: 600,
      },
      body1: {
        fontSize: '16px',
        lineHeight: 1.5,
      },
      body2: {
        fontSize: '14px',
        lineHeight: 1.5,
      },
      caption: {
        fontSize: '12px',
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
                : '0 4px 12px rgba(102, 126, 234, 0.2)',
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
            color: '#667eea',
            height: 6,
          },
          thumb: {
            width: 16,
            height: 16,
            backgroundColor: '#fff',
            border: isDark ? 'none' : '2px solid #667eea',
            '&:hover, &.Mui-focusVisible': {
              boxShadow: '0 0 0 8px rgba(102, 126, 234, 0.16)',
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
                ? 'rgba(255, 255, 255, 0.05)'
                : 'rgba(102, 126, 234, 0.05)',
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
