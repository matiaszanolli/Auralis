import { CSSProperties, ReactNode, forwardRef } from 'react';
import { tokens } from '@/design-system';

interface GridProps {
  children: ReactNode;
  columns?: number;
  spacing?: keyof typeof tokens.spacing;
  minColWidth?: string;
  className?: string;
}

/**
 * Grid layout component for arranging items in a responsive grid.
 * Uses CSS Grid with automatic column sizing or fixed column count.
 */
export const Grid = forwardRef<
  HTMLDivElement,
  GridProps
>(({
  children,
  columns,
  spacing = 'md',
  minColWidth = '200px',
  className = '',
}, ref) => {
  const gap = tokens.spacing[spacing];

  const styles: CSSProperties = {
    display: 'grid',
    gap,
    gridTemplateColumns: columns
      ? `repeat(${columns}, 1fr)`
      : `repeat(auto-fit, minmax(${minColWidth}, 1fr))`,
  };

  return (
    <div ref={ref} style={styles} className={className}>
      {children}
    </div>
  );
});

Grid.displayName = 'Grid';
