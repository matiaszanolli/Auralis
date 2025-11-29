import React from 'react';
import { tokens } from '@/design-system';

interface TooltipProps {
  content: string;
  children: React.ReactNode;
  position?: 'top' | 'right' | 'bottom' | 'left';
  className?: string;
}

const positionStyles = {
  top: {
    bottom: '100%',
    left: '50%',
    transform: 'translateX(-50%) translateY(-8px)',
  },
  right: {
    left: '100%',
    top: '50%',
    transform: 'translateY(-50%) translateX(8px)',
  },
  bottom: {
    top: '100%',
    left: '50%',
    transform: 'translateX(-50%) translateY(8px)',
  },
  left: {
    right: '100%',
    top: '50%',
    transform: 'translateY(-50%) translateX(-8px)',
  },
};

/**
 * Tooltip component for displaying helpful information on hover.
 */
export const Tooltip = React.forwardRef<
  HTMLDivElement,
  TooltipProps
>(({
  content,
  children,
  position = 'top',
  className = '',
}, ref) => {
  const [isVisible, setIsVisible] = React.useState(false);

  const containerStyles: React.CSSProperties = {
    position: 'relative',
    display: 'inline-block',
  };

  const tooltipStyles: React.CSSProperties = {
    position: 'absolute',
    ...positionStyles[position],
    backgroundColor: tokens.colors.bg.primary,
    color: tokens.colors.text.primary,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.sm,
    fontSize: tokens.typography.fontSize.xs,
    whiteSpace: 'nowrap',
    zIndex: tokens.zIndex.tooltip,
    border: `1px solid ${tokens.colors.border.light}`,
    opacity: isVisible ? 1 : 0,
    visibility: isVisible ? 'visible' : 'hidden',
    transition: tokens.transitions.all,
    pointerEvents: 'none',
  };

  return (
    <div
      ref={ref}
      style={containerStyles}
      className={className}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children}
      <div style={tooltipStyles}>{content}</div>
    </div>
  );
});

Tooltip.displayName = 'Tooltip';
