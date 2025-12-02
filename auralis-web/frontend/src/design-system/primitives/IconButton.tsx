/**
 * IconButton Primitive Component
 *
 * Icon-only button for actions and controls.
 * Used in player controls, toolbars, and action menus.
 *
 * Usage:
 *   <IconButton><PlayArrowIcon /></IconButton>
 *   <IconButton variant="primary" size="lg"><FavoriteIcon /></IconButton>
 *   <IconButton tooltip="Add to playlist"><AddIcon /></IconButton>
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import MuiIconButton, { IconButtonProps as MuiIconButtonProps } from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import { tokens } from '../tokens';

export interface IconButtonProps extends Omit<MuiIconButtonProps, 'size' | 'color'> {
  /**
   * Visual variant
   */
  variant?: 'default' | 'primary' | 'secondary' | 'ghost';

  /**
   * Size
   */
  size?: 'sm' | 'md' | 'lg';

  /**
   * Tooltip text (optional)
   */
  tooltip?: string;

  /**
   * Active/selected state
   */
  active?: boolean;
}

const StyledIconButton = styled(MuiIconButton, {
  shouldForwardProp: (prop) =>
    !['variant', 'size', 'active'].includes(prop as string),
})<IconButtonProps>(({ variant = 'default', size = 'md', active, disabled }) => {
  // Size styles
  const sizeStyles = {
    sm: {
      width: '32px',
      height: '32px',
      fontSize: '18px',
    },
    md: {
      width: '40px',
      height: '40px',
      fontSize: '20px',
    },
    lg: {
      width: '48px',
      height: '48px',
      fontSize: '24px',
    },
  };

  // Variant styles
  const variantStyles = {
    default: {
      color: tokens.colors.text.secondary,
      background: 'transparent',

      '&:hover': {
        background: tokens.colors.bg.tertiary,
        color: tokens.colors.text.primary,
      },

      '&:active': {
        background: tokens.colors.bg.elevated,
      },

      ...(active && {
        color: tokens.colors.accent.primary,
        background: tokens.colors.bg.tertiary,
      }),
    },

    primary: {
      color: tokens.colors.text.primary,
      background: tokens.gradients.aurora,
      boxShadow: tokens.shadows.md,

      '&:hover': {
        boxShadow: tokens.shadows.lg,
        transform: 'scale(1.05)',
      },

      '&:active': {
        transform: 'scale(1)',
      },
    },

    secondary: {
      color: tokens.colors.text.primary,
      background: tokens.colors.bg.tertiary,
      border: `1px solid ${tokens.colors.border.medium}`,

      '&:hover': {
        background: tokens.colors.bg.elevated,
        borderColor: tokens.colors.border.heavy,
      },

      '&:active': {
        background: tokens.colors.bg.tertiary,
      },

      ...(active && {
        borderColor: tokens.colors.accent.primary,
        background: tokens.colors.bg.elevated,
      }),
    },

    ghost: {
      color: tokens.colors.text.secondary,
      background: 'transparent',

      '&:hover': {
        color: tokens.colors.text.primary,
        background: tokens.colors.bg.tertiary,
      },

      ...(active && {
        color: tokens.colors.accent.primary,
      }),
    },
  };

  return {
    ...sizeStyles[size as keyof typeof sizeStyles],
    ...variantStyles[variant as keyof typeof variantStyles],
    borderRadius: tokens.borderRadius.md,
    transition: tokens.transitions.all,
    opacity: disabled ? 0.5 : 1,
    cursor: disabled ? 'not-allowed' : 'pointer',

    '& svg': {
      fontSize: 'inherit',
    },
  };
});

export const IconButton: React.FC<IconButtonProps> = ({
  children,
  tooltip,
  variant = 'default',
  size = 'md',
  active = false,
  disabled = false,
  ...props
}) => {
  const button = (
    <StyledIconButton
      variant={variant}
      size={size}
      active={active}
      disabled={disabled}
      {...(props as any)}
    >
      {children}
    </StyledIconButton>
  );

  // Wrap with tooltip if provided
  if (tooltip && !disabled) {
    return (
      <Tooltip title={tooltip} arrow>
        {button}
      </Tooltip>
    );
  }

  return button;
};

export default IconButton;
