import { CSSProperties, forwardRef, useId } from 'react';
import { tokens } from '@/design-system';

interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  showValue?: boolean;
  color?: 'primary' | 'success' | 'warning' | 'error';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  /** Accessible name for the bar when no visible label is provided. */
  'aria-label'?: string;
}

const colorMap = {
  primary: tokens.colors.accent.primary,
  success: tokens.colors.semantic.success,
  warning: tokens.colors.semantic.warning,
  error: tokens.colors.semantic.error,
};

const sizeMap = {
  sm: '4px',
  md: '8px',
  lg: '12px',
};

/**
 * Progress bar component for showing progress of a task.
 */
export const ProgressBar = forwardRef<
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
  'aria-label': ariaLabel,
}, ref) => {
  const labelId = useId();
  const percentage = Math.min((value / max) * 100, 100);
  const barHeight = sizeMap[size];
  const barColor = colorMap[color];

  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.sm,
  };

  const headerStyles: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
  };

  const barContainerStyles: CSSProperties = {
    width: '100%',
    height: barHeight,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.full,
    overflow: 'hidden',
  };

  const barFillStyles: CSSProperties = {
    height: '100%',
    width: `${percentage}%`,
    backgroundColor: barColor,
    transition: tokens.transitions.base,
    borderRadius: tokens.borderRadius.full,
  };

  const rounded = Math.round(percentage);
  const accessibleName = ariaLabel ?? (typeof label === 'string' ? undefined : 'Progress');

  return (
    <div ref={ref} style={containerStyles} className={className}>
      {(label || showValue) && (
        <div style={headerStyles}>
          {label && <span id={labelId}>{label}</span>}
          {showValue && <span>{rounded}%</span>}
        </div>
      )}
      <div
        style={barContainerStyles}
        role="progressbar"
        aria-valuenow={rounded}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={`${rounded}%`}
        aria-labelledby={label ? labelId : undefined}
        aria-label={label ? undefined : accessibleName}
      >
        <div style={barFillStyles} />
      </div>
    </div>
  );
});

ProgressBar.displayName = 'ProgressBar';
