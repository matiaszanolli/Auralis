import React from 'react';
import { tokens } from '@/design-system';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  color?: string;
  label?: string;
  className?: string;
}

const sizeMap = {
  sm: '24px',
  md: '40px',
  lg: '64px',
};

/**
 * Loading spinner component for indicating loading states.
 */
export const LoadingSpinner = React.forwardRef<
  HTMLDivElement,
  LoadingSpinnerProps
>(({
  size = 'md',
  color = tokens.colors.accent.primary,
  label,
  className = '',
}, ref) => {
  const spinnerSize = sizeMap[size];

  const containerStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: tokens.spacing.md,
  };

  const spinnerStyles: React.CSSProperties = {
    width: spinnerSize,
    height: spinnerSize,
    border: `3px solid ${tokens.colors.bg.secondary}`,
    borderTop: `3px solid ${color}`,
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  };

  return (
    <div ref={ref} style={containerStyles} className={className}>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
      <div style={spinnerStyles} />
      {label && (
        <span style={{
          color: tokens.colors.text.secondary,
          fontSize: tokens.typography.fontSize.sm,
        }}>
          {label}
        </span>
      )}
    </div>
  );
});

LoadingSpinner.displayName = 'LoadingSpinner';
