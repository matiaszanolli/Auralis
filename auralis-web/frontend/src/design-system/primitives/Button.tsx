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
 * @see docs/UI_DESIGN_GUIDELINES.md
 */

import { ComponentType, ReactNode } from 'react';
import { styled } from '@mui/material/styles';
import MuiButton, { ButtonProps as MuiButtonProps } from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

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
  startIcon?: ReactNode;

  /**
   * Icon after text
   */
  endIcon?: ReactNode;
}

type StyledButtonProps = Omit<MuiButtonProps, 'variant' | 'size' | 'color'> & {
  variant?: ButtonProps['variant'];
  size?: ButtonProps['size'];
  loading?: boolean;
};

const StyledButton = styled(MuiButton as ComponentType<Omit<MuiButtonProps, 'variant' | 'size' | 'color'>>, {
  shouldForwardProp: (prop) =>
    !['variant', 'size', 'loading'].includes(prop as string),
})<StyledButtonProps>(({ variant = 'primary', size = 'md', disabled, loading }) => {
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
      color: themeVars.textPrimary,
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
      background: themeVars.surfaceSecondary,
      color: themeVars.textPrimary,
      border: `1px solid ${themeVars.borderStrong}`,

      '&:hover': {
        background: themeVars.surfaceRaised,
        borderColor: tokens.colors.border.heavy,
      },

      '&:active': {
        background: themeVars.surfaceSecondary,
      },
    },

    ghost: {
      background: 'transparent',
      color: themeVars.textSecondary,

      '&:hover': {
        background: themeVars.surfaceSecondary,
        color: themeVars.textPrimary,
      },

      '&:active': {
        background: themeVars.surfacePrimary,
      },
    },

    danger: {
      background: themeVars.error,
      color: themeVars.textPrimary,

      '&:hover': {
        background: themeVars.error,
        opacity: 0.9,
        boxShadow: tokens.shadows.md,
      },

      '&:active': {
        background: themeVars.error,
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
  color: themeVars.textPrimary,
});

export const Button = ({
  children,
  loading = false,
  disabled = false,
  variant = 'primary',
  size = 'md',
  startIcon,
  endIcon,
  ...props
}: ButtonProps) => {
  return (
    <StyledButton
      variant={variant}
      size={size}
      disabled={disabled || loading}
      loading={loading}
      startIcon={!loading ? startIcon : undefined}
      endIcon={!loading ? endIcon : undefined}
      {...props}
    >
      {loading && <LoadingSpinner size={20} />}
      <span style={{ visibility: loading ? 'hidden' : 'visible' }}>
        {children}
      </span>
    </StyledButton>
  );
};

export default Button;
