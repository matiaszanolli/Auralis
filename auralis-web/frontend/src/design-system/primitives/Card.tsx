/**
 * Card Primitive Component
 *
 * Container component for album cards, track cards, and content sections.
 *
 * Usage:
 *   <Card>Content</Card>
 *   <Card variant="elevated" hoverable>Elevated card</Card>
 *   <Card padding="lg">Large padding</Card>
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import MuiCard, { CardProps as MuiCardProps } from '@mui/material/Card';
import { tokens } from '../tokens';

export interface CardProps extends Omit<MuiCardProps, 'variant'> {
  /**
   * Visual variant
   */
  variant?: 'default' | 'elevated' | 'outlined';

  /**
   * Padding size
   */
  padding?: 'none' | 'sm' | 'md' | 'lg';

  /**
   * Enable hover effect
   */
  hoverable?: boolean;

  /**
   * Selected/active state
   */
  selected?: boolean;
}

const StyledCard = styled(MuiCard, {
  shouldForwardProp: (prop) =>
    !['variant', 'padding', 'hoverable', 'selected'].includes(prop as string),
})<{ variant?: 'default' | 'elevated' | 'outlined'; padding?: 'none' | 'sm' | 'md' | 'lg'; hoverable?: boolean; selected?: boolean }>(({ variant = 'default', padding = 'md', hoverable, selected }) => {
  // Padding styles
  const paddingStyles = {
    none: { padding: 0 },
    sm: { padding: tokens.spacing.sm },
    md: { padding: tokens.spacing.md },
    lg: { padding: tokens.spacing.lg },
  };

  // Variant styles
  const variantStyles = {
    default: {
      background: tokens.colors.bg.tertiary,
      border: 'none',
      boxShadow: tokens.shadows.none,
    },

    elevated: {
      background: tokens.colors.bg.tertiary,
      border: 'none',
      boxShadow: tokens.shadows.md,
    },

    outlined: {
      background: tokens.colors.bg.secondary,
      border: `1px solid ${tokens.colors.border.light}`,
      boxShadow: tokens.shadows.none,
    },
  };

  // Hover styles
  const hoverStyles = hoverable
    ? {
        cursor: 'pointer',
        transition: tokens.transitions.all,

        '&:hover': {
          transform: 'scale(1.02)',
          boxShadow: tokens.shadows.lg,
        },

        '&:active': {
          transform: 'scale(1)',
        },
      }
    : {};

  // Selected styles
  const selectedStyles = selected
    ? {
        borderColor: tokens.colors.accent.primary,
        boxShadow: `0 0 0 2px ${tokens.colors.accent.primary}`,
      }
    : {};

  return {
    ...variantStyles[variant as keyof typeof variantStyles],
    ...paddingStyles[padding as keyof typeof paddingStyles],
    ...hoverStyles,
    ...selectedStyles,
    borderRadius: tokens.borderRadius.lg,
    overflow: 'hidden',
  };
});

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  padding = 'md',
  hoverable = false,
  selected = false,
  ...props
}) => {
  return (
    <StyledCard
      variant={variant}
      padding={padding}
      hoverable={hoverable}
      selected={selected}
      {...(props as any)}
    >
      {children}
    </StyledCard>
  );
};

export default Card;
