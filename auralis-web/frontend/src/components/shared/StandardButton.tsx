/**
 * StandardButton Component
 * ========================
 *
 * Consistent button styling across the Auralis application.
 * Implements the design system button patterns with proper hover states,
 * ripple effects, and accessibility support.
 *
 * **Variants:**
 * - primary: Aurora gradient button (main CTAs)
 * - secondary: Outlined button with hover fill
 * - ghost: Transparent button with subtle hover
 * - danger: Error/destructive actions
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import React from 'react';
import { Button, ButtonProps, styled, alpha } from '@mui/material';
import { gradients, colors, shadows, borderRadius, transitions, spacing } from '../../theme/auralisTheme';

export interface StandardButtonProps extends Omit<ButtonProps, 'variant'> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  glow?: boolean;
}

// Primary button with aurora gradient
const PrimaryButton = styled(Button)<{ glow?: boolean }>(({ glow }) => ({
  background: gradients.aurora,
  color: colors.text.primary,
  padding: `${spacing.sm}px ${spacing.lg}px`,
  borderRadius: `${borderRadius.sm}px`,
  fontWeight: 600,
  textTransform: 'none',
  transition: `all ${transitions.hover}`,
  border: 'none',
  boxShadow: glow ? shadows.glowPurple : shadows.sm,

  '&:hover': {
    background: gradients.auroraReverse,
    transform: 'translateY(-2px)',
    boxShadow: glow ? `${shadows.glowPurple}, ${shadows.md}` : shadows.md,
  },

  '&:active': {
    transform: 'translateY(0)',
    transition: `all ${transitions.fast}`,
  },

  '&:disabled': {
    background: colors.background.surface,
    color: colors.text.disabled,
    boxShadow: 'none',
  },

  '&:focus-visible': {
    outline: 'none',
    boxShadow: `0 0 0 3px ${alpha('#667eea', 0.5)}`,
  },
}));

// Secondary button with outline
const SecondaryButton = styled(Button)({
  background: 'transparent',
  color: '#667eea',
  padding: `${spacing.sm}px ${spacing.lg}px`,
  borderRadius: `${borderRadius.sm}px`,
  fontWeight: 600,
  textTransform: 'none',
  transition: `all ${transitions.hover}`,
  border: `2px solid ${alpha('#667eea', 0.5)}`,

  '&:hover': {
    background: alpha('#667eea', 0.1),
    borderColor: '#667eea',
    transform: 'translateY(-2px)',
    boxShadow: shadows.sm,
  },

  '&:active': {
    transform: 'translateY(0)',
    background: alpha('#667eea', 0.2),
  },

  '&:disabled': {
    borderColor: colors.text.disabled,
    color: colors.text.disabled,
  },

  '&:focus-visible': {
    outline: 'none',
    boxShadow: `0 0 0 3px ${alpha('#667eea', 0.3)}`,
  },
});

// Ghost button (transparent background)
const GhostButton = styled(Button)({
  background: 'transparent',
  color: colors.text.primary,
  padding: `${spacing.sm}px ${spacing.lg}px`,
  borderRadius: `${borderRadius.sm}px`,
  fontWeight: 600,
  textTransform: 'none',
  transition: `all ${transitions.hover}`,
  border: 'none',

  '&:hover': {
    background: colors.background.hover,
    transform: 'translateY(-2px)',
  },

  '&:active': {
    transform: 'translateY(0)',
    background: colors.background.surface,
  },

  '&:disabled': {
    color: colors.text.disabled,
  },

  '&:focus-visible': {
    outline: 'none',
    boxShadow: `0 0 0 2px ${alpha(colors.text.primary, 0.3)}`,
  },
});

// Danger button (destructive actions)
const DangerButton = styled(Button)({
  background: colors.semantic.error,
  color: colors.text.primary,
  padding: `${spacing.sm}px ${spacing.lg}px`,
  borderRadius: `${borderRadius.sm}px`,
  fontWeight: 600,
  textTransform: 'none',
  transition: `all ${transitions.hover}`,
  border: 'none',
  boxShadow: shadows.sm,

  '&:hover': {
    background: colors.semantic.errorDark,
    transform: 'translateY(-2px)',
    boxShadow: `0 8px 24px ${alpha(colors.semantic.error, 0.3)}`,
  },

  '&:active': {
    transform: 'translateY(0)',
  },

  '&:disabled': {
    background: colors.background.surface,
    color: colors.text.disabled,
    boxShadow: 'none',
  },

  '&:focus-visible': {
    outline: 'none',
    boxShadow: `0 0 0 3px ${alpha(colors.semantic.error, 0.5)}`,
  },
});

/**
 * StandardButton component with consistent styling
 */
export const StandardButton: React.FC<StandardButtonProps> = ({
  variant = 'primary',
  glow = false,
  children,
  ...props
}) => {
  switch (variant) {
    case 'primary':
      return (
        <PrimaryButton glow={glow} {...props}>
          {children}
        </PrimaryButton>
      );
    case 'secondary':
      return <SecondaryButton {...props}>{children}</SecondaryButton>;
    case 'ghost':
      return <GhostButton {...props}>{children}</GhostButton>;
    case 'danger':
      return <DangerButton {...props}>{children}</DangerButton>;
    default:
      return (
        <PrimaryButton glow={glow} {...props}>
          {children}
        </PrimaryButton>
      );
  }
};

export default StandardButton;
