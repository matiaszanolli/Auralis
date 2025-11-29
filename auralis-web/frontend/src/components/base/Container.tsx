import React from 'react';
import { tokens } from '@/design-system';

interface ContainerProps {
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  padding?: keyof typeof tokens.spacing;
  className?: string;
}

const maxWidths = {
  sm: '480px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  full: '100%',
};

/**
 * Container component for constraining content width.
 * Provides horizontal centering and consistent padding.
 */
export const Container = React.forwardRef<
  HTMLDivElement,
  ContainerProps
>(({
  children,
  maxWidth = 'lg',
  padding = 'lg',
  className = '',
}, ref) => {
  const styles: React.CSSProperties = {
    maxWidth: maxWidths[maxWidth],
    margin: '0 auto',
    padding: tokens.spacing[padding],
    width: '100%',
    boxSizing: 'border-box',
  };

  return (
    <div ref={ref} style={styles} className={className}>
      {children}
    </div>
  );
});

Container.displayName = 'Container';
