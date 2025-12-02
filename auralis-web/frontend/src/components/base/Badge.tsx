import React from 'react';
import { tokens } from '@/design-system';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'primary' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
  className?: string;
}

const variantColors = {
  primary: {
    bg: tokens.colors.accent.primary,
    text: tokens.colors.text.primary,
  },
  success: {
    bg: tokens.colors.semantic.success,
    text: tokens.colors.text.primary,
  },
  warning: {
    bg: tokens.colors.semantic.warning,
    text: tokens.colors.text.primary,
  },
  error: {
    bg: tokens.colors.semantic.error,
    text: tokens.colors.text.primary,
  },
  info: {
    bg: tokens.colors.semantic.info,
    text: tokens.colors.text.primary,
  },
};

const sizeStyles = {
  sm: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    fontSize: tokens.typography.fontSize.xs,
  },
  md: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
    fontSize: tokens.typography.fontSize.sm,
  },
};

/**
 * Badge component for labeling and categorization.
 */
export const Badge = React.forwardRef<
  HTMLSpanElement,
  BadgeProps
>(({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
}, ref) => {
  const colors = variantColors[variant];
  const sizing = sizeStyles[size];

  const styles: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bg,
    color: colors.text,
    borderRadius: tokens.borderRadius.full,
    fontWeight: tokens.typography.fontWeight.semibold,
    whiteSpace: 'nowrap',
    ...sizing,
  };

  return (
    <span ref={ref} style={styles} className={className}>
      {children}
    </span>
  );
});

Badge.displayName = 'Badge';
