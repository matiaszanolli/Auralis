import React from 'react';
import { tokens } from '@/design-system';

interface CardProps {
  children: React.ReactNode;
  header?: React.ReactNode;
  footer?: React.ReactNode;
  hoverable?: boolean;
  className?: string;
}

/**
 * Card component for grouping related content.
 */
export const Card = React.forwardRef<
  HTMLDivElement,
  CardProps
>(({
  children,
  header,
  footer,
  hoverable = false,
  className = '',
}, ref) => {
  const containerStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: tokens.colors.bg.tertiary,
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.lg,
    overflow: 'hidden',
    transition: tokens.transitions.all,
    cursor: hoverable ? 'pointer' : 'default',
  };

  const headerStyles: React.CSSProperties = {
    padding: tokens.spacing.lg,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    fontWeight: tokens.typography.fontWeight.semibold,
    color: tokens.colors.text.primary,
  };

  const contentStyles: React.CSSProperties = {
    padding: tokens.spacing.lg,
    flex: 1,
  };

  const footerStyles: React.CSSProperties = {
    padding: tokens.spacing.lg,
    borderTop: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
  };

  return (
    <div
      ref={ref}
      style={containerStyles}
      className={className}
      onMouseEnter={(e) => {
        if (hoverable) {
          e.currentTarget.style.boxShadow = tokens.shadows.md;
          e.currentTarget.style.transform = 'translateY(-4px)';
        }
      }}
      onMouseLeave={(e) => {
        if (hoverable) {
          e.currentTarget.style.boxShadow = 'none';
          e.currentTarget.style.transform = 'translateY(0)';
        }
      }}
    >
      {header && <div style={headerStyles}>{header}</div>}
      <div style={contentStyles}>{children}</div>
      {footer && <div style={footerStyles}>{footer}</div>}
    </div>
  );
});

Card.displayName = 'Card';
