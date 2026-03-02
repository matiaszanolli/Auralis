import React from 'react';
import { tokens } from '../tokens';

export interface BoxProps {
  children?: React.ReactNode;
  as?: keyof JSX.IntrinsicElements;
  display?: 'flex' | 'block' | 'inline' | 'inline-flex' | 'grid' | 'none';
  flexDirection?: 'row' | 'column' | 'row-reverse' | 'column-reverse';
  alignItems?: 'flex-start' | 'center' | 'flex-end' | 'stretch' | 'baseline';
  justifyContent?: 'flex-start' | 'center' | 'flex-end' | 'space-between' | 'space-around' | 'space-evenly';
  gap?: keyof typeof tokens.spacing;
  padding?: keyof typeof tokens.spacing;
  paddingX?: keyof typeof tokens.spacing;
  paddingY?: keyof typeof tokens.spacing;
  margin?: keyof typeof tokens.spacing;
  marginX?: keyof typeof tokens.spacing;
  marginY?: keyof typeof tokens.spacing;
  width?: string | number;
  height?: string | number;
  maxWidth?: string | number;
  minWidth?: string | number;
  maxHeight?: string | number;
  minHeight?: string | number;
  flex?: number | string;
  flexShrink?: number;
  flexGrow?: number;
  overflow?: 'visible' | 'hidden' | 'scroll' | 'auto';
  overflowX?: 'visible' | 'hidden' | 'scroll' | 'auto';
  overflowY?: 'visible' | 'hidden' | 'scroll' | 'auto';
  position?: 'static' | 'relative' | 'absolute' | 'fixed' | 'sticky';
  top?: string | number;
  right?: string | number;
  bottom?: string | number;
  left?: string | number;
  bg?: string;
  color?: string;
  borderRadius?: keyof typeof tokens.borderRadius;
  border?: string;
  boxShadow?: string;
  opacity?: number;
  style?: React.CSSProperties;
  className?: string;
  onClick?: (e: React.MouseEvent) => void;
}

/**
 * Box - The most basic layout primitive
 *
 * A flexible container component that accepts all common CSS props
 * through a simple prop API using design tokens.
 *
 * @example
 * <Box display="flex" gap="md" padding="lg">
 *   <Box flex={1}>Content</Box>
 * </Box>
 */
export const Box = React.forwardRef<HTMLElement, BoxProps>(
  (
    {
      children,
      as: Component = 'div',
      display,
      flexDirection,
      alignItems,
      justifyContent,
      gap,
      padding,
      paddingX,
      paddingY,
      margin,
      marginX,
      marginY,
      width,
      height,
      maxWidth,
      minWidth,
      maxHeight,
      minHeight,
      flex,
      flexShrink,
      flexGrow,
      overflow,
      overflowX,
      overflowY,
      position,
      top,
      right,
      bottom,
      left,
      bg,
      color,
      borderRadius,
      border,
      boxShadow,
      opacity,
      style = {},
      className,
      onClick,
    },
    ref
  ) => {
    const styles: React.CSSProperties = {
      display,
      flexDirection,
      alignItems,
      justifyContent,
      gap: gap ? tokens.spacing[gap] : undefined,
      padding: padding ? tokens.spacing[padding] : undefined,
      paddingLeft: paddingX ? tokens.spacing[paddingX] : undefined,
      paddingRight: paddingX ? tokens.spacing[paddingX] : undefined,
      paddingTop: paddingY ? tokens.spacing[paddingY] : undefined,
      paddingBottom: paddingY ? tokens.spacing[paddingY] : undefined,
      margin: margin ? tokens.spacing[margin] : undefined,
      marginLeft: marginX ? tokens.spacing[marginX] : undefined,
      marginRight: marginX ? tokens.spacing[marginX] : undefined,
      marginTop: marginY ? tokens.spacing[marginY] : undefined,
      marginBottom: marginY ? tokens.spacing[marginY] : undefined,
      width,
      height,
      maxWidth,
      minWidth,
      maxHeight,
      minHeight,
      flex,
      flexShrink,
      flexGrow,
      overflow,
      overflowX,
      overflowY,
      position,
      top,
      right,
      bottom,
      left,
      backgroundColor: bg,
      color,
      borderRadius: borderRadius ? tokens.borderRadius[borderRadius] : undefined,
      border,
      boxShadow,
      opacity,
      ...style,
    };

    const Element = Component as React.ElementType;

    return (
      <Element
        ref={ref}
        style={styles}
        className={className}
        onClick={onClick}
      >
        {children}
      </Element>
    );
  }
);

Box.displayName = 'Box';

export default Box;
