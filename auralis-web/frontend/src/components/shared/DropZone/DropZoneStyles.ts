import { Paper, styled, alpha } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

/**
 * Styled components for DropZone
 */

export const DropZonePaper = styled(Paper, {
  shouldForwardProp: (prop) => prop !== '$isDragging' && prop !== '$disabled' && prop !== '$scanning',
})<{ $isDragging: boolean; $disabled: boolean; $scanning: boolean }>(
  ({ $isDragging, $disabled, $scanning }) => ({
    position: 'relative',
    padding: tokens.spacing.xxl,
    borderRadius: tokens.borderRadius.lg,
    // MUI's alpha() parses the color string, so it cannot take a
    // `var(--app-*)` — it throws on one. color-mix() applies the same fraction
    // to whichever color the theme resolves the variable to, at paint time
    // (#4877), matching AppMainContent.tsx / TrackTableHeader.tsx.
    border: `2px dashed ${
      $isDragging
        ? tokens.colors.accent.primary
        : $scanning
        ? `color-mix(in srgb, ${themeVars.textSecondary} 30%, transparent)`
        : `color-mix(in srgb, ${themeVars.textDisabled} 20%, transparent)`
    }`,
    background: $isDragging
      ? alpha(tokens.colors.accent.primary, 0.05)
      : $scanning
      ? `color-mix(in srgb, ${themeVars.surfaceRaised} 50%, transparent)`
      : 'transparent',
    cursor: $disabled || $scanning ? 'not-allowed' : 'pointer',
    transition: tokens.transitions.state_inOut,
    textAlign: 'center',
    overflow: 'hidden',
    opacity: $disabled ? 0.5 : 1,

    // WCAG 2.4.7: keyboard focus indicator (#2771)
    '&:focus-visible': {
      outline: `2px solid ${tokens.colors.accent.primary}`,
      outlineOffset: '2px',
    },

    ...((!$disabled && !$scanning) && {
      '&:hover': {
        borderColor: tokens.colors.accent.primary,
        background: alpha(tokens.colors.accent.primary, 0.02),
        transform: 'scale(1.01)',
      },
    }),

    ...($isDragging && {
      '&::before': {
        content: '""',
        position: 'absolute',
        inset: 0,
        background: tokens.gradients.aurora,
        opacity: 0.05,
        animation: 'pulse 2s ease-in-out infinite',
      },
    }),

    // Style Guide §6.1: Slow, weighted motion (300-600ms state changes)
    '@keyframes pulse': {
      '0%, 100%': { opacity: 0.05 },
      '50%': { opacity: 0.1 },
    },

    // Style Guide §6.1: Slow breathing animation instead of bounce
    '@keyframes breathe': {
      '0%, 100%': {
        transform: 'scale(1)',
        opacity: 1,
      },
      '50%': {
        transform: 'scale(1.02)',
        opacity: 0.92,
      },
    },

    '@keyframes fadeIn': {
      from: {
        opacity: 0,
        transform: 'scale(0.95)',
      },
      to: {
        opacity: 1,
        transform: 'scale(1)',
      },
    },
  })
);
