import type { Components, Theme } from '@mui/material/styles';
import { tokens } from '@/design-system';
import type { SemanticTheme } from './semanticTheme';

/** MUI component style overrides. Split out of themeConfig.ts (#5841). */
export const createComponents = (
  semantic: SemanticTheme,
  isDark: boolean
): Components<Omit<Theme, 'components'>> => (
    {
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
    });
