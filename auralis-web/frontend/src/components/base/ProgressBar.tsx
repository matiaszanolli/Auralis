import React from 'react';
import { tokens } from '@/design-system';

interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  showValue?: boolean;
  color?: 'primary' | 'success' | 'warning' | 'error';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const colorMap = {
  primary: tokens.colors.accent.primary,
  success: tokens.colors.accent.success,
  warning: tokens.colors.accent.warning,
  error: tokens.colors.accent.error,
};

const sizeMap = {
  sm: '4px',
  md: '8px',
  lg: '12px',
};

/**
 * Progress bar component for showing progress of a task.
 */
export const ProgressBar = React.forwardRef<
  HTMLDivElement,
  ProgressBarProps
>(({
  value,
  max = 100,
  label,
  showValue = false,
  color = 'primary',
  size = 'md',
  className = '',
}, ref) => {
  const percentage = Math.min((value / max) * 100, 100);
  const barHeight = sizeMap[size];
  const barColor = colorMap[color];

  const containerStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.sm,
  };

  const headerStyles: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
  };

  const barContainerStyles: React.CSSProperties = {
    width: '100%',
    height: barHeight,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.full,
    overflow: 'hidden',
  };

  const barFillStyles: React.CSSProperties = {
    height: '100%',
    width: `${percentage}%`,
    backgroundColor: barColor,
    transition: tokens.transitions.base,
    borderRadius: tokens.borderRadius.full,
  };

  return (
    <div ref={ref} style={containerStyles} className={className}>
      {(label || showValue) && (
        <div style={headerStyles}>
          {label && <span>{label}</span>}
          {showValue && <span>{Math.round(percentage)}%</span>}
        </div>
      )}
      <div style={barContainerStyles}>
        <div style={barFillStyles} />
      </div>
    </div>
  );
});

ProgressBar.displayName = 'ProgressBar';
