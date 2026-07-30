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

import { styled } from '@mui/material/styles';
import MuiBadge, { BadgeProps as MuiBadgeProps } from '@mui/material/Badge';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

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

type StyledBadgeProps = Omit<MuiBadgeProps, 'variant' | 'color'> & {
  variant?: BadgeProps['variant'];
};

const StyledBadge = styled(MuiBadge as React.ComponentType<Omit<MuiBadgeProps, 'variant' | 'color'>>, {
  shouldForwardProp: (prop) => prop !== 'variant',
})<StyledBadgeProps>(({ variant = 'default' }) => {
  const variantStyles = {
    default: {
      '& .MuiBadge-badge': {
        background: themeVars.textSecondary,
        color: themeVars.textPrimary,
      },
    },
    primary: {
      '& .MuiBadge-badge': {
        background: tokens.gradients.aurora,
        color: themeVars.textPrimary,
      },
    },
    success: {
      '& .MuiBadge-badge': {
        background: themeVars.success,
        color: themeVars.textPrimary,
      },
    },
    warning: {
      '& .MuiBadge-badge': {
        background: themeVars.warning,
        color: themeVars.textPrimary,
      },
    },
    error: {
      '& .MuiBadge-badge': {
        background: themeVars.error,
        color: themeVars.textPrimary,
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

export const Badge = ({
  children,
  variant = 'default',
  value,
  dot = false,
  ...props
}: BadgeProps) => {
  return (
    <StyledBadge
      variant={variant}
      badgeContent={dot ? undefined : value}
      invisible={!value && !dot}
      {...props}
    >
      {children}
    </StyledBadge>
  );
};

export default Badge;
