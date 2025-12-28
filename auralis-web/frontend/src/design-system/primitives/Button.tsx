/**
 * Button Primitive Component
 *
 * The definitive button component for Auralis.
 * Supports multiple variants, sizes, and states.
 *
 * Usage:
 *   <Button variant="primary">Click me</Button>
 *   <Button variant="secondary" size="sm">Small</Button>
 *   <Button variant="ghost" disabled>Disabled</Button>
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import MuiButton, { ButtonProps as MuiButtonProps } from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import { tokens } from '../tokens';

export interface ButtonProps extends Omit<MuiButtonProps, 'variant' | 'size' | 'color'> {
  /**
   * Visual variant
   */
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';

  /**
   * Size - supports both design system and MUI formats
   */
  size?: 'sm' | 'md' | 'lg' | 'small' | 'medium' | 'large';

  /**
   * Loading state
   */
  loading?: boolean;

  /**
   * Full width
   */
  fullWidth?: boolean;

  /**
   * Icon before text
   */
  startIcon?: React.ReactNode;

  /**
   * Icon after text
   */
  endIcon?: React.ReactNode;
}

const StyledButton = styled(MuiButton, {
  shouldForwardProp: (prop) =>
    !['variant', 'size', 'loading'].includes(prop as string),
})<{ variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md' | 'lg' | 'small' | 'medium' | 'large'; loading?: boolean }>(({ variant = 'primary', size = 'md', disabled, loading }) => {
  // Base styles
  const baseStyles = {
    fontFamily: tokens.typography.fontFamily.primary,
    fontWeight: tokens.typography.fontWeight.semibold,
    borderRadius: tokens.borderRadius.md,
    textTransform: 'none' as const,
    transition: tokens.transitions.all,
    border: 'none',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled || loading ? 0.5 : 1,
    position: 'relative' as const,

    // Disable MUI's default uppercase transform
    '& .MuiButton-label': {
      textTransform: 'none',
    },
  };

  // Map Material-UI sizes to design system sizes
  const normalizedSize = (() => {
    switch (size) {
      case 'small': return 'sm';
      case 'medium': return 'md';
      case 'large': return 'lg';
      default: return size as 'sm' | 'md' | 'lg';
    }
  })();

  // Size styles
  const sizeStyles = {
    sm: {
      height: '32px',
      padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
      fontSize: tokens.typography.fontSize.sm,
      gap: tokens.spacing.xs,
    },
    md: {
      height: '40px',
      padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
      fontSize: tokens.typography.fontSize.base,
      gap: tokens.spacing.sm,
    },
    lg: {
      height: '48px',
      padding: `${tokens.spacing.md} ${tokens.spacing.xl}`,
      fontSize: tokens.typography.fontSize.md,
      gap: tokens.spacing.sm,
    },
  };

  // Variant styles
  const variantStyles = {
    primary: {
      background: tokens.gradients.aurora,
      color: tokens.colors.text.primary,
      boxShadow: tokens.shadows.md,

      '&:hover': {
        boxShadow: tokens.shadows.lg,
        transform: 'scale(1.02)',              // Scale-based hover (Design Language §5)
      },

      '&:active': {
        transform: 'scale(0.98)',              // Press inward for tactile feedback
      },
    },

    secondary: {
      background: tokens.colors.bg.tertiary,
      color: tokens.colors.text.primary,
      border: `1px solid ${tokens.colors.border.medium}`,

      '&:hover': {
        background: tokens.colors.bg.elevated,
        borderColor: tokens.colors.border.heavy,
      },

      '&:active': {
        background: tokens.colors.bg.tertiary,
      },
    },

    ghost: {
      background: 'transparent',
      color: tokens.colors.text.secondary,

      '&:hover': {
        background: tokens.colors.bg.tertiary,
        color: tokens.colors.text.primary,
      },

      '&:active': {
        background: tokens.colors.bg.secondary,
      },
    },

    danger: {
      background: tokens.colors.semantic.error,
      color: tokens.colors.text.primary,

      '&:hover': {
        background: tokens.colors.semantic.error,
        opacity: 0.9,
        boxShadow: tokens.shadows.md,
      },

      '&:active': {
        background: tokens.colors.semantic.error,
        opacity: 0.8,
      },
    },
  };

  return {
    ...baseStyles,
    ...sizeStyles[normalizedSize as keyof typeof sizeStyles],
    ...variantStyles[variant as keyof typeof variantStyles],
  };
});

const LoadingSpinner = styled(CircularProgress)({
  position: 'absolute',
  left: '50%',
  top: '50%',
  marginLeft: '-10px',
  marginTop: '-10px',
  color: tokens.colors.text.primary,
});

export const Button: React.FC<ButtonProps> = ({
  children,
  loading = false,
  disabled = false,
  variant = 'primary',
  size = 'md',
  startIcon,
  endIcon,
  ...props
}) => {
  return (
    <StyledButton
      variant={variant}
      size={size}
      disabled={disabled || loading}
      loading={loading}
      startIcon={!loading ? startIcon : undefined}
      endIcon={!loading ? endIcon : undefined}
      {...(props as any)}
    >
      {loading && <LoadingSpinner size={20} />}
      <span style={{ visibility: loading ? 'hidden' : 'visible' }}>
        {children}
      </span>
    </StyledButton>
  );
};

export default Button;
