import React from 'react';
import { tokens } from '@/design-system';

interface AlertProps {
  children: React.ReactNode;
  variant?: 'info' | 'success' | 'warning' | 'error';
  icon?: React.ReactNode;
  onClose?: () => void;
  className?: string;
}

const hexToRgba = (hex: string, alpha: number): string => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const variantStyles = {
  info: {
    bg: hexToRgba(tokens.colors.semantic.info, 0.15),
    border: tokens.colors.semantic.info,
    text: tokens.colors.semantic.info,
  },
  success: {
    bg: hexToRgba(tokens.colors.semantic.success, 0.15),
    border: tokens.colors.semantic.success,
    text: tokens.colors.semantic.success,
  },
  warning: {
    bg: hexToRgba(tokens.colors.semantic.warning, 0.15),
    border: tokens.colors.semantic.warning,
    text: tokens.colors.semantic.warning,
  },
  error: {
    bg: hexToRgba(tokens.colors.semantic.error, 0.15),
    border: tokens.colors.semantic.error,
    text: tokens.colors.semantic.error,
  },
};

/**
 * Alert component for displaying important messages.
 */
export const Alert = React.forwardRef<
  HTMLDivElement,
  AlertProps
>(({
  children,
  variant = 'info',
  icon,
  onClose,
  className = '',
}, ref) => {
  const variantStyle = variantStyles[variant] || variantStyles.info;

  const containerStyles: React.CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: variantStyle.bg,
    border: `1px solid ${variantStyle.border}`,
    borderRadius: tokens.borderRadius.md,
    color: variantStyle.text,
  };

  const contentStyles: React.CSSProperties = {
    flex: 1,
    fontSize: tokens.typography.fontSize.sm,
    lineHeight: tokens.typography.lineHeight.normal,
  };

  const closeButtonStyles: React.CSSProperties = {
    background: 'none',
    border: 'none',
    color: variantStyle.text,
    cursor: 'pointer',
    padding: 0,
    fontSize: tokens.typography.fontSize.lg,
    lineHeight: 1,
  };

  return (
    <div ref={ref} role="alert" style={containerStyles} className={className}>
      {icon && <div>{icon}</div>}
      <div style={contentStyles}>{children}</div>
      {onClose && (
        <button style={closeButtonStyles} onClick={onClose} aria-label="Close alert">
          ✕
        </button>
      )}
    </div>
  );
});

Alert.displayName = 'Alert';
