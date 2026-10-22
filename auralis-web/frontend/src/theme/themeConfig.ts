import { createTheme, Theme } from '@mui/material/styles';
import { tokens } from '@/design-system';
import { getSemanticTheme, type ThemeMode } from './semanticTheme';

// ============================================================================
// CREATE THEME FUNCTION
// ============================================================================
/** MUI spacing unit in px, taken from `tokens.spacing.cluster` (#5384). */
export const MUI_SPACING_UNIT_PX = Number.parseFloat(tokens.spacing.cluster);

export const createAuralisTheme = (mode: ThemeMode): Theme => {
  const isDark = mode === 'dark';
  const semantic = getSemanticTheme(mode);

  // #3597/#3949: MUI light/dark variants derived from the brand accents. MUI
  // uses these for auto-generated hover/focus shades; we pre-compute them to
  // keep the palette stable across MUI updates instead of relying on its
  // internal colorManipulator heuristics. Now token-backed (no magic hex).
  const PRIMARY_LIGHT = tokens.colors.accent.primaryLight;
  const PRIMARY_DARK = tokens.colors.accent.primaryDark;
  const SECONDARY_LIGHT = tokens.colors.accent.secondaryLight;
  const SECONDARY_DARK = tokens.colors.accent.secondaryDark;

  return createTheme({
    // Auralis owns one semantic CSS-variable namespace. Keeping MUI's generated
    // variables disabled avoids two competing runtime theme contracts.
    cssVariables: false,
    palette: {
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
    },
    // #5384: MUI's numeric sx spacing (`p: 2`, `mb: 3`) and its components'
    // internal padding resolve through theme.spacing(n) = n x unit. The unit
    // is the 8px `cluster` token rather than MUI's own default, so the two
    // scales are one: spacing(1) = cluster, (2) = group, (4) = section,
    // (0.5) = xs, (1.5) = md. The value is unchanged, so rendering is too.
    spacing: MUI_SPACING_UNIT_PX,
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
        color: semantic.textSecondary,
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
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: semantic.canvas,
            color: semantic.textPrimary,
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: tokens.borderRadius.sm,
            padding: `${tokens.spacing.cluster} ${tokens.spacing.group}`,
            fontWeight: tokens.typography.fontWeight.semibold,
            transition: tokens.transitions.hover_out,
          },
          contained: {
            boxShadow: 'none',
            '&:hover': {
              boxShadow: tokens.shadows.sm,
            },
          },
          outlined: {
            borderColor: semantic.borderDefault,
            '&:hover': {
              borderColor: semantic.borderStrong,
              backgroundColor: semantic.accentSoft,
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundColor: semantic.surfaceSecondary,
            backgroundImage: 'none',
            border: `1px solid ${semantic.borderSubtle}`,
            boxShadow: 'none',
            transition: tokens.transitions.hover_out,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundColor: semantic.surfacePrimary,
            backgroundImage: 'none',
            color: semantic.textPrimary,
          },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            backgroundColor: semantic.surfaceRaised,
            border: `1px solid ${semantic.borderDefault}`,
            borderRadius: tokens.borderRadius.lg,
            boxShadow: semantic.shadowOverlay,
          },
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: {
            padding: `${tokens.spacing.lg} ${tokens.spacing.xl}`,
            borderBottom: `1px solid ${semantic.borderSubtle}`,
          },
        },
      },
      MuiDialogActions: {
        styleOverrides: {
          root: {
            padding: `${tokens.spacing.md} ${tokens.spacing.lg}`,
            borderTop: `1px solid ${semantic.borderSubtle}`,
          },
        },
      },
      MuiBackdrop: {
        styleOverrides: {
          root: {
            backgroundColor: semantic.backdrop,
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: semantic.surfacePrimary,
            backgroundImage: 'none',
            borderColor: semantic.borderSubtle,
            boxShadow: semantic.shadowRaised,
          },
        },
      },
      MuiDivider: {
        styleOverrides: {
          root: {
            borderColor: semantic.borderSubtle,
          },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: tokens.borderRadius.sm,
            transition: tokens.transitions.hover_out,
            '&:hover': {
              backgroundColor: semantic.accentSoft,
            },
            '&.Mui-selected': {
              backgroundColor: semantic.accentSoft,
              '&:hover': {
                backgroundColor: semantic.accentSoft,
              },
            },
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            backgroundColor: semantic.surfaceSecondary,
            borderRadius: tokens.borderRadius.sm,
            transition: tokens.transitions.hover_out,
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: semantic.borderDefault,
            },
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: semantic.borderStrong,
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: semantic.accent,
              boxShadow: `0 0 0 3px ${semantic.focusRing}`,
            },
          },
          input: {
            color: semantic.textPrimary,
            '&::placeholder': {
              color: semantic.textMuted,
              opacity: 1,
            },
          },
        },
      },
      MuiTabs: {
        styleOverrides: {
          root: {
            borderBottom: `1px solid ${semantic.borderSubtle}`,
          },
          indicator: {
            height: 2,
            borderRadius: tokens.borderRadius.full,
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            minHeight: 44,
            color: semantic.textSecondary,
            textTransform: 'none',
            '&.Mui-selected': {
              color: semantic.textPrimary,
            },
          },
        },
      },
      MuiToggleButton: {
        styleOverrides: {
          root: {
            color: semantic.textSecondary,
            borderColor: semantic.borderDefault,
            '&:hover': {
              backgroundColor: semantic.accentSoft,
              color: semantic.textPrimary,
            },
            '&.Mui-selected': {
              backgroundColor: semantic.accentSoft,
              color: semantic.accent,
              '&:hover': {
                backgroundColor: semantic.accentSoft,
              },
            },
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
            backgroundColor: semantic.surfaceRaised,
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
                background: tokens.gradients.aurora,
                opacity: 1,
              },
            },
          },
          thumb: {
            width: 24,
            height: 24,
            boxShadow: isDark
              ? '0 2px 4px ' + tokens.colors.opacityScale.dark.standard
              : '0 2px 4px ' + tokens.colors.opacityScale.dark.light,
          },
          track: {
            borderRadius: 16,
            backgroundColor: semantic.surfaceRaised,
            opacity: 1,
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            color: semantic.textSecondary,
            transition: tokens.transitions.hover_out,
            '&:hover': {
              color: semantic.textPrimary,
              backgroundColor: semantic.accentSoft,
            },
          },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: semantic.surfaceOverlay,
            color: semantic.textPrimary,
            border: `1px solid ${semantic.borderDefault}`,
            boxShadow: semantic.shadowRaised,
            fontSize: tokens.typography.fontSize.xs,
          },
        },
      },
    },
  });
};

// Use `themeVars` for theme-aware colours; the MUI success/error/warning/info
// palette is built from `getSemanticTheme(mode)`.
