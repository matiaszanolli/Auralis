import React from 'react';
import { tokens } from '@/design-system';

interface TextInputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
  fullWidth?: boolean;
}

/**
 * Text input component with optional label, error state, and icons.
 * Follows design system colors and spacing.
 */
export const TextInput = React.forwardRef<
  HTMLInputElement,
  TextInputProps
>(({
  label,
  error,
  helperText,
  startIcon,
  endIcon,
  fullWidth = false,
  className = '',
  ...props
}, ref) => {
  const containerStyles: React.CSSProperties = {
    width: fullWidth ? '100%' : 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.xs,
  };

  const inputContainerStyles: React.CSSProperties = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
  };

  const inputStyles: React.CSSProperties = {
    flex: 1,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    paddingLeft: startIcon ? `calc(${tokens.spacing.md} + 24px + ${tokens.spacing.sm})` : tokens.spacing.md,
    paddingRight: endIcon ? `calc(${tokens.spacing.md} + 24px + ${tokens.spacing.sm})` : tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primary,
    fontFamily: tokens.typography.fontFamily.primary,
    fontSize: tokens.typography.fontSize.base,
    transition: tokens.transitions.all,
    boxSizing: 'border-box' as const,
  };

  const inputStylesWithError: React.CSSProperties = {
    ...inputStyles,
    borderColor: error ? tokens.colors.semantic.error : tokens.colors.border.light,
  };

  const labelStyles: React.CSSProperties = {
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.primary,
  };

  const errorStyles: React.CSSProperties = {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.semantic.error,
  };

  const helperStyles: React.CSSProperties = {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
  };

  const iconStyles: React.CSSProperties = {
    position: 'absolute',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '24px',
    height: '24px',
    color: tokens.colors.text.secondary,
  };

  return (
    <div style={containerStyles} className={className}>
      {label && <label style={labelStyles}>{label}</label>}
      <div style={inputContainerStyles}>
        {startIcon && (
          <div style={{ ...iconStyles, left: tokens.spacing.sm }}>
            {startIcon}
          </div>
        )}
        <input
          ref={ref}
          style={inputStylesWithError}
          {...props}
        />
        {endIcon && (
          <div style={{ ...iconStyles, right: tokens.spacing.sm }}>
            {endIcon}
          </div>
        )}
      </div>
      {error && <div style={errorStyles}>{error}</div>}
      {helperText && !error && <div style={helperStyles}>{helperText}</div>}
    </div>
  );
});

TextInput.displayName = 'TextInput';
