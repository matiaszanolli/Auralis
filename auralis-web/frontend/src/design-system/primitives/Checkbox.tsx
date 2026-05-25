import { CSSProperties, InputHTMLAttributes, forwardRef } from 'react';
import { tokens } from '@/design-system';

interface CheckboxProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  error?: string;
}

/**
 * Checkbox component following design system standards.
 */
export const Checkbox = forwardRef<
  HTMLInputElement,
  CheckboxProps
>(({
  label,
  error,
  className = '',
  ...props
}, ref) => {
  const containerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
  };

  const inputStyles: CSSProperties = {
    width: '18px',
    height: '18px',
    cursor: 'pointer',
    accentColor: tokens.colors.accent.primary,
  };

  const labelStyles: CSSProperties = {
    fontSize: tokens.typography.fontSize.base,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    userSelect: 'none',
  };

  const errorStyles: CSSProperties = {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.semantic.error,
    marginTop: tokens.spacing.xs,
  };

  return (
    <div className={className}>
      <div style={containerStyles}>
        <input
          ref={ref}
          type="checkbox"
          style={inputStyles}
          {...props}
        />
        {label && <label style={labelStyles}>{label}</label>}
      </div>
      {error && <div style={errorStyles}>{error}</div>}
    </div>
  );
});

Checkbox.displayName = 'Checkbox';
