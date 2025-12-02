import React from 'react';
import { tokens } from '@/design-system';

interface ToggleProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  error?: string;
}

/**
 * Toggle switch component for boolean states.
 */
export const Toggle = React.forwardRef<
  HTMLInputElement,
  ToggleProps
>(({
  label,
  error,
  className = '',
  ...props
}, ref) => {
  const containerStyles: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
  };

  const switchContainerStyles: React.CSSProperties = {
    position: 'relative',
    display: 'inline-flex',
    width: '48px',
    height: '28px',
  };

  const inputStyles: React.CSSProperties = {
    appearance: 'none',
    width: '100%',
    height: '100%',
    margin: 0,
    padding: 0,
    cursor: 'pointer',
    backgroundColor: tokens.colors.bg.secondary,
    border: `2px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.full,
    transition: tokens.transitions.all,
    outline: 'none',
  };

  const labelStyles: React.CSSProperties = {
    fontSize: tokens.typography.fontSize.base,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    userSelect: 'none',
  };

  const errorStyles: React.CSSProperties = {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.semantic.error,
    marginTop: tokens.spacing.xs,
  };

  return (
    <div className={className}>
      <div style={containerStyles}>
        <div style={switchContainerStyles}>
          <input
            ref={ref}
            type="checkbox"
            style={inputStyles}
            {...props}
          />
        </div>
        {label && <label style={labelStyles}>{label}</label>}
      </div>
      {error && <div style={errorStyles}>{error}</div>}
    </div>
  );
});

Toggle.displayName = 'Toggle';
