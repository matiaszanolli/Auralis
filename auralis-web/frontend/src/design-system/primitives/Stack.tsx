import React from 'react';
import { tokens } from '@/design-system';

interface StackProps {
  children: React.ReactNode;
  direction?: 'row' | 'column';
  spacing?: keyof typeof tokens.spacing;
  align?: 'flex-start' | 'center' | 'flex-end' | 'stretch';
  justify?: 'flex-start' | 'center' | 'flex-end' | 'space-between' | 'space-around';
  className?: string;
}

/**
 * Flexible box component for stacking children with consistent spacing.
 * Supports both horizontal and vertical layouts.
 */
export const Stack = React.forwardRef<
  HTMLDivElement,
  StackProps
>(({
  children,
  direction = 'column',
  spacing = 'md',
  align = 'flex-start',
  justify = 'flex-start',
  className = '',
}, ref) => {
  const gap = tokens.spacing[spacing];

  const styles: React.CSSProperties = {
    display: 'flex',
    flexDirection: direction as any,
    gap,
    alignItems: align,
    justifyContent: justify,
  };

  return (
    <div ref={ref} style={styles} className={className}>
      {children}
    </div>
  );
});

Stack.displayName = 'Stack';
