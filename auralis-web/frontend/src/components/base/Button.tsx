import React from 'react';
import { tokens } from '@/design-system';

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  fullWidth?: boolean;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
}

const variantStyles = {
  primary: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primary,
    border: 'none',
    hover: { backgroundColor: tokens.colors.accent.secondary },
  },
  secondary: {
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    border: `1px solid ${tokens.colors.border.medium}`,
    hover: { backgroundColor: tokens.colors.bg.elevated },
  },
  ghost: {
    backgroundColor: 'transparent',
    color: tokens.colors.accent.primary,
    border: 'none',
    hover: { backgroundColor: tokens.colors.bg.secondary },
  },
  danger: {
    backgroundColor: tokens.colors.semantic.error,
    color: tokens.colors.text.primary,
    border: 'none',
    hover: { backgroundColor: '#dc2626' },
  },
};

const sizeStyles = {
  sm: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    fontSize: tokens.typography.fontSize.sm,
  },
  md: {
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    fontSize: tokens.typography.fontSize.base,
  },
  lg: {
    padding: `${tokens.spacing.md} ${tokens.spacing.lg}`,
    fontSize: tokens.typography.fontSize.md,
  },
};

/**
 * Button component with multiple variants and sizes.
 */
export const Button = React.forwardRef<
  HTMLButtonElement,
  ButtonProps
>(({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  startIcon,
  endIcon,
  children,
  disabled,
  className = '',
  ...props
}, ref) => {
  const variantStyle = variantStyles[variant];
  const sizeStyle = sizeStyles[size];

  const baseStyles: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: tokens.spacing.sm,
    borderRadius: tokens.borderRadius.md,
    fontWeight: tokens.typography.fontWeight.medium,
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    transition: tokens.transitions.all,
    width: fullWidth ? '100%' : 'auto',
    opacity: disabled || loading ? 0.6 : 1,
    ...variantStyle,
    ...sizeStyle,
  };

  return (
    <button
      ref={ref}
      style={baseStyles}
      disabled={disabled || loading}
      className={className}
      {...props}
      onMouseEnter={(e) => {
        if (!disabled && !loading) {
          Object.assign(e.currentTarget.style, variantStyle.hover);
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled && !loading) {
          Object.assign(e.currentTarget.style, variantStyle);
        }
      }}
    >
      {loading && <span>⏳</span>}
      {!loading && startIcon}
      {children}
      {!loading && endIcon}
    </button>
  );
});

Button.displayName = 'Button';
