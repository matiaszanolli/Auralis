/**
 * Button Component
 * ~~~~~~~~~~~~~~~
 *
 * Unified button component with multiple variants, sizes, and states.
 * Supports text, outlined, and contained variants with Aurora gradient theming.
 *
 * Features:
 * - Multiple variants: text, outlined, contained, gradient
 * - Sizes: small (32px), medium (40px), large (56px)
 * - States: default, hover, active, disabled, loading
 * - Aurora gradient styling with smooth transitions
 * - Accessibility: ARIA labels, keyboard navigation, focus states
 * - Responsive: Scales appropriately for different screen sizes
 *
 * @example
 * ```tsx
 * // Text button
 * <Button variant="text">Cancel</Button>
 *
 * // Contained button with gradient
 * <Button variant="contained">Save</Button>
 *
 * // Large primary button
 * <Button size="large" fullWidth>Play</Button>
 *
 * // Outlined button
 * <Button variant="outlined">Edit</Button>
 *
 * // Disabled state
 * <Button disabled>Disabled</Button>
 *
 * // Loading state
 * <Button loading>Processing...</Button>
 * ```
 */

import React from 'react';
import { Button as MuiButton, CircularProgress, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { auroraOpacity, gradients } from '../../library/Styles/Color.styles';

export type ButtonVariant = 'text' | 'outlined' | 'contained' | 'gradient';
export type ButtonSize = 'small' | 'medium' | 'large';

export interface ButtonProps extends React.ComponentProps<typeof MuiButton> {
  /**
   * Button variant style
   * @default 'contained'
   */
  variant?: ButtonVariant;

  /**
   * Button size
   * @default 'medium'
   */
  size?: ButtonSize;

  /**
   * Whether the button is in a loading state
   * Shows a spinner and disables interaction
   */
  loading?: boolean;

  /**
   * Loading indicator color
   * @default 'inherit'
   */
  loadingColor?: 'inherit' | 'primary' | 'secondary';

  /**
   * Custom color for the button
   * @default 'primary'
   */
  color?: 'primary' | 'secondary' | 'error' | 'success' | 'warning' | 'info' | 'inherit';

  /**
   * Whether button should take full width of container
   */
  fullWidth?: boolean;
}

// Size configurations
const sizeConfig = {
  small: {
    padding: tokens.spacing.xs + ' ' + tokens.spacing.md,
    fontSize: tokens.typography.fontSize.sm,
    minHeight: '32px',
    minWidth: '32px',
  },
  medium: {
    padding: tokens.spacing.sm + ' ' + tokens.spacing.lg,
    fontSize: tokens.typography.fontSize.md,
    minHeight: '40px',
    minWidth: '40px',
  },
  large: {
    padding: tokens.spacing.md + ' ' + tokens.spacing.xl,
    fontSize: tokens.typography.fontSize.lg,
    minHeight: '56px',
    minWidth: '56px',
  },
};

/**
 * Styled text button
 */
export const StyledTextButton = styled(MuiButton)(({ theme }) => ({
  textTransform: 'none',
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.primary,
  backgroundColor: 'transparent',
  transition: `all ${tokens.transitions.base}`,

  '&:hover': {
    backgroundColor: auroraOpacity.lighter,
  },

  '&:active': {
    backgroundColor: auroraOpacity.standard,
    transform: 'scale(0.98)',
  },

  '&:disabled': {
    color: tokens.colors.text.disabled,
    backgroundColor: 'transparent',
  },
}));

/**
 * Styled outlined button
 */
export const StyledOutlinedButton = styled(MuiButton)(({ theme }) => ({
  textTransform: 'none',
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.primary,
  backgroundColor: 'transparent',
  border: `2px solid ${auroraOpacity.veryLight}`,
  transition: `all ${tokens.transitions.base}`,

  '&:hover': {
    backgroundColor: auroraOpacity.lighter,
    borderColor: tokens.colors.accent.purple,
    boxShadow: `0 4px 12px ${auroraOpacity.strong}`,
    transform: 'translateY(-2px)',
  },

  '&:active': {
    backgroundColor: auroraOpacity.standard,
    borderColor: tokens.colors.accent.purple,
    transform: 'scale(0.98)',
  },

  '&:disabled': {
    color: tokens.colors.text.disabled,
    borderColor: auroraOpacity.veryLight,
    backgroundColor: 'transparent',
  },
}));

/**
 * Styled contained button with Aurora gradient
 */
export const StyledContainedButton = styled(MuiButton)(({ theme }) => ({
  textTransform: 'none',
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.primary,
  background: gradients.aurora,
  border: 'none',
  transition: `all ${tokens.transitions.base}`,
  boxShadow: `0 4px 12px ${auroraOpacity.standard}`,

  '&:hover': {
    background: gradients.aurora,
    boxShadow: `0 8px 24px ${auroraOpacity.strong}`,
    transform: 'translateY(-2px)',
  },

  '&:active': {
    boxShadow: `0 2px 8px ${auroraOpacity.strong}`,
    transform: 'scale(0.98)',
  },

  '&:disabled': {
    color: tokens.colors.text.disabled,
    background: auroraOpacity.strong,
    boxShadow: 'none',
  },
}));

/**
 * Styled gradient button (full-width variant)
 */
export const StyledGradientButton = styled(MuiButton)(({ theme }) => ({
  textTransform: 'none',
  fontWeight: tokens.typography.fontWeight.bold,
  color: tokens.colors.text.primary,
  background: gradients.aurora,
  border: 'none',
  borderRadius: tokens.borderRadius.full,
  transition: `all ${tokens.transitions.base}`,
  boxShadow: `0 4px 16px ${auroraOpacity.strong}, 0 0 24px ${auroraOpacity.lighter}`,

  '&:hover': {
    background: gradients.aurora,
    boxShadow: `0 8px 24px ${auroraOpacity.stronger}, 0 0 32px ${auroraOpacity.standard}`,
    transform: 'scale(1.05) translateY(-2px)',
  },

  '&:active': {
    boxShadow: `0 2px 8px ${auroraOpacity.strong}`,
    transform: 'scale(0.95)',
  },

  '&:disabled': {
    color: tokens.colors.text.disabled,
    background: auroraOpacity.strong,
    boxShadow: 'none',
  },
}));

/**
 * Button Component
 *
 * Main button component that handles variant and size configurations.
 * Automatically applies appropriate styling based on props.
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'contained',
      size = 'medium',
      loading = false,
      loadingColor = 'inherit',
      disabled = false,
      fullWidth = false,
      children,
      sx = {},
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;
    const sizeStyles = sizeConfig[size];

    // Select the appropriate styled component based on variant
    let StyledButtonComponent;
    switch (variant) {
      case 'text':
        StyledButtonComponent = StyledTextButton;
        break;
      case 'outlined':
        StyledButtonComponent = StyledOutlinedButton;
        break;
      case 'gradient':
        StyledButtonComponent = StyledGradientButton;
        break;
      case 'contained':
      default:
        StyledButtonComponent = StyledContainedButton;
        break;
    }

    return (
      <StyledButtonComponent
        ref={ref}
        disabled={isDisabled}
        fullWidth={fullWidth}
        sx={{
          ...sizeStyles,
          position: 'relative',
          ...sx,
        }}
        {...props}
      >
        {loading && (
          <CircularProgress
            size={size === 'small' ? 16 : size === 'medium' ? 20 : 24}
            color={loadingColor}
            sx={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              marginLeft: `-${size === 'small' ? 8 : size === 'medium' ? 10 : 12}px`,
              marginTop: `-${size === 'small' ? 8 : size === 'medium' ? 10 : 12}px`,
            }}
          />
        )}
        <span style={{ visibility: loading ? 'hidden' : 'visible' }}>{children}</span>
      </StyledButtonComponent>
    );
  }
);

Button.displayName = 'Button';

export default Button;
