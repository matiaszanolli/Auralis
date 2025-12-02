import React from 'react';
import { tokens } from '@/design-system';

interface AlertProps {
  children: React.ReactNode;
  variant?: 'info' | 'success' | 'warning' | 'error';
  icon?: React.ReactNode;
  onClose?: () => void;
  className?: string;
}

const variantStyles = {
  info: {
    bg: `rgba(${parseInt(tokens.colors.semantic.info.slice(1, 3), 16)}, ${parseInt(tokens.colors.semantic.info.slice(3, 5), 16)}, ${parseInt(tokens.colors.semantic.info.slice(5, 7), 16)}, 0.15)`,
    border: tokens.colors.semantic.info,
    text: tokens.colors.semantic.info,
  },
  success: {
    bg: `rgba(0, 212, 170, 0.15)`,
    border: tokens.colors.semantic.success,
    text: tokens.colors.semantic.success,
  },
  warning: {
    bg: `rgba(245, 158, 11, 0.15)`,
    border: tokens.colors.semantic.warning,
    text: tokens.colors.semantic.warning,
  },
  error: {
    bg: `rgba(239, 68, 68, 0.15)`,
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
  const variantStyle = variantStyles[variant];

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
    <div ref={ref} style={containerStyles} className={className}>
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
