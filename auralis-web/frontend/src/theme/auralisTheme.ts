import { createTheme } from '@mui/material/styles';

// Design System - Spacing Scale
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
  xxxl: 64,
};

// Design System - Shadows
export const shadows = {
  none: 'none',
  xs: '0 1px 2px rgba(0, 0, 0, 0.08)',
  sm: '0 2px 4px rgba(0, 0, 0, 0.1)',
  md: '0 4px 12px rgba(0, 0, 0, 0.15)',
  lg: '0 8px 24px rgba(0, 0, 0, 0.2)',
  xl: '0 16px 48px rgba(0, 0, 0, 0.3)',
  // Glow effects for aurora theme
  glowPurple: '0 8px 24px rgba(102, 126, 234, 0.3)',
  glowPink: '0 8px 24px rgba(255, 107, 157, 0.3)',
  glowBlue: '0 8px 24px rgba(75, 123, 236, 0.3)',
};

// Design System - Border Radius
export const borderRadius = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  full: 9999,
};

// Design System - Animation Timings
export const transitions = {
  fast: '150ms ease',
  normal: '250ms ease',
  slow: '350ms ease',
  bounce: '350ms cubic-bezier(0.68, -0.55, 0.265, 1.55)',
};

// Aurora gradient definitions
export const gradients = {
  aurora: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  auroraReverse: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
  neonSunset: 'linear-gradient(135deg, #ff6b9d 0%, #ffa502 100%)',
  deepOcean: 'linear-gradient(135deg, #4b7bec 0%, #26de81 100%)',
  electricPurple: 'linear-gradient(135deg, #c44569 0%, #667eea 100%)',
  cosmicBlue: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',
};

// Color palette
export const colors = {
  background: {
    primary: '#0A0E27',
    secondary: '#1a1f3a',
    surface: '#252b45',
    elevated: '#2a3150',
    hover: '#313858',
  },
  text: {
    primary: '#ffffff',
    secondary: '#8b92b0',
    disabled: '#5a5f7a',
    hint: '#6b7299',
  },
  accent: {
    success: '#00d4aa',
    error: '#ff4757',
    warning: '#ffa502',
    info: '#4b7bec',
    purple: '#667eea',
    pink: '#ff6b9d',
  },
  neon: {
    pink: '#ff6b9d',
    purple: '#c44569',
    blue: '#4b7bec',
    cyan: '#26de81',
    orange: '#ffa502',
  },
};

// Create MUI theme
export const auralisTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#667eea',
      light: '#8b9cf7',
      dark: '#5166d6',
    },
    secondary: {
      main: '#764ba2',
      light: '#9668c4',
      dark: '#5d3c82',
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
      'Montserrat',
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
      lineHeight: 1.2,
      letterSpacing: '-0.5px',
    },
    h2: {
      fontSize: '28px',
      fontWeight: 700,
      lineHeight: 1.3,
      letterSpacing: '-0.25px',
    },
    h3: {
      fontSize: '24px',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h4: {
      fontSize: '20px',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h5: {
      fontSize: '18px',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h6: {
      fontSize: '16px',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    body1: {
      fontSize: '16px',
      lineHeight: 1.6,
      fontWeight: 400,
    },
    body2: {
      fontSize: '14px',
      lineHeight: 1.6,
      fontWeight: 400,
    },
    caption: {
      fontSize: '12px',
      lineHeight: 1.4,
      color: colors.text.secondary,
      letterSpacing: '0.4px',
    },
    subtitle1: {
      fontSize: '16px',
      fontWeight: 500,
      lineHeight: 1.5,
    },
    subtitle2: {
      fontSize: '14px',
      fontWeight: 500,
      lineHeight: 1.5,
    },
    button: {
      textTransform: 'none',
      fontWeight: 600,
      letterSpacing: '0.2px',
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
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: colors.background.secondary,
          backgroundImage: 'none',
          transition: `all ${transitions.normal}`,
          '&:hover': {
            backgroundColor: colors.background.elevated,
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
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
          },
        },
      },
    },
  },
});

export default auralisTheme;
