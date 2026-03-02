import React from 'react';
import { tokens } from '../tokens';

export interface TextProps {
  children: React.ReactNode;
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'p' | 'span' | 'label';
  variant?: 'display' | 'title' | 'heading' | 'body' | 'caption' | 'label';
  size?: keyof typeof tokens.typography.fontSize;
  weight?: keyof typeof tokens.typography.fontWeight;
  color?: string;
  opacity?: number;
  align?: 'left' | 'center' | 'right';
  truncate?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const variantStyles = {
  display: {
    fontSize: tokens.typography.fontSize['2xl'],
    fontWeight: tokens.typography.fontWeight.bold,
    lineHeight: 1.2,
  },
  title: {
    fontSize: tokens.typography.fontSize.xl,
    fontWeight: tokens.typography.fontWeight.bold,
    lineHeight: 1.3,
  },
  heading: {
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.semibold,
    lineHeight: 1.4,
  },
  body: {
    fontSize: tokens.typography.fontSize.base,
    fontWeight: tokens.typography.fontWeight.normal,
    lineHeight: 1.5,
  },
  caption: {
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.normal,
    lineHeight: 1.4,
  },
  label: {
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.medium,
    lineHeight: 1.4,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
};

/**
 * Text - Typography primitive
 *
 * Provides consistent text styling using design tokens.
 * Supports semantic HTML elements and predefined variants.
 *
 * @example
 * <Text variant="title">Page Title</Text>
 * <Text as="p" variant="body" color={tokens.colors.text.secondary}>
 *   Body text
 * </Text>
 */
export const Text = React.forwardRef<HTMLElement, TextProps>(
  (
    {
      children,
      as: Component = 'span',
      variant = 'body',
      size,
      weight,
      color,
      opacity,
      align,
      truncate,
      className,
      style = {},
    },
    ref
  ) => {
    const variantStyle = variantStyles[variant];

    const styles: React.CSSProperties = {
      fontFamily: tokens.typography.fontFamily.primary,
      margin: 0,
      ...variantStyle,
      ...(size && { fontSize: tokens.typography.fontSize[size] }),
      ...(weight && { fontWeight: tokens.typography.fontWeight[weight] }),
      ...(color && { color }),
      ...(opacity !== undefined && { opacity }),
      ...(align && { textAlign: align }),
      ...(truncate && {
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }),
      ...style,
    };

    return (
      <Component ref={ref as any} style={styles} className={className}>
        {children}
      </Component>
    );
  }
);

Text.displayName = 'Text';

export default Text;
