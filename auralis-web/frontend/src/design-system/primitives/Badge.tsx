/**
 * Badge Primitive Component
 *
 * Small badge for counts, status, and labels.
 *
 * Usage:
 *   <Badge value={5} />
 *   <Badge value="New" variant="success" />
 *   <Badge dot variant="error" />
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import MuiBadge, { BadgeProps as MuiBadgeProps } from '@mui/material/Badge';
import { tokens } from '../tokens';

export interface BadgeProps extends Omit<MuiBadgeProps, 'variant' | 'color'> {
  /**
   * Visual variant
   */
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'error';

  /**
   * Badge content (number or string)
   */
  value?: number | string;

  /**
   * Show as dot instead of value
   */
  dot?: boolean;
}

const StyledBadge = styled(MuiBadge, {
  shouldForwardProp: (prop) => prop !== 'variant',
})<{ variant?: 'default' | 'primary' | 'success' | 'warning' | 'error' }>(({ variant = 'default' }) => {
  const variantStyles = {
    default: {
      '& .MuiBadge-badge': {
        background: tokens.colors.text.secondary,
        color: tokens.colors.text.primary,
      },
    },
    primary: {
      '& .MuiBadge-badge': {
        background: tokens.gradients.aurora,
        color: tokens.colors.text.primary,
      },
    },
    success: {
      '& .MuiBadge-badge': {
        background: tokens.colors.accent.success,
        color: tokens.colors.text.primary,
      },
    },
    warning: {
      '& .MuiBadge-badge': {
        background: tokens.colors.accent.warning,
        color: tokens.colors.text.primary,
      },
    },
    error: {
      '& .MuiBadge-badge': {
        background: tokens.colors.accent.error,
        color: tokens.colors.text.primary,
      },
    },
  };

  return {
    ...variantStyles[variant as keyof typeof variantStyles],
    '& .MuiBadge-badge': {
      fontSize: tokens.typography.fontSize.xs,
      fontWeight: tokens.typography.fontWeight.semibold,
      height: '20px',
      minWidth: '20px',
      borderRadius: tokens.borderRadius.full,
      padding: `0 ${tokens.spacing.xs}`,
    },
  };
});

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  value,
  dot = false,
  ...props
}) => {
  return (
    <StyledBadge
      variant={variant}
      badgeContent={dot ? undefined : value}
      invisible={!value && !dot}
      {...(props as any)}
    >
      {children}
    </StyledBadge>
  );
};

export default Badge;
