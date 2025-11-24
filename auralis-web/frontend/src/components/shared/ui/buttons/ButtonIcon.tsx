/**
 * ButtonIcon Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Specialized button component for icon-only actions.
 * Provides consistent sizing, spacing, and hover effects for icon buttons.
 *
 * Features:
 * - Multiple sizes: small (32px), medium (40px), large (56px)
 * - Aurora gradient hover effects
 * - Smooth transitions and transform animations
 * - Accessibility: Built-in tooltip support, ARIA labels
 * - Circular or square shapes
 *
 * @example
 * ```tsx
 * // Basic icon button
 * <ButtonIcon icon={<PlayIcon />} onClick={handlePlay} />
 *
 * // With tooltip
 * <ButtonIcon
 *   icon={<DeleteIcon />}
 *   tooltip="Delete item"
 *   onClick={handleDelete}
 * />
 *
 * // Medium size with custom color
 * <ButtonIcon
 *   size="medium"
 *   icon={<EditIcon />}
 *   ariaLabel="Edit"
 * />
 *
 * // Large disabled button
 * <ButtonIcon
 *   size="large"
 *   icon={<MoreIcon />}
 *   disabled
 * />
 * ```
 */

import React from 'react';
import { IconButton as MuiIconButton, Tooltip, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { auroraOpacity } from '@/components/library/Styles/Color.styles';

export type ButtonIconSize = 'small' | 'medium' | 'large';
export type ButtonIconShape = 'circular' | 'square';

export interface ButtonIconProps extends React.ComponentProps<typeof MuiIconButton> {
  /**
   * Icon element to display
   */
  icon: React.ReactNode;

  /**
   * Button size
   * @default 'medium'
   */
  size?: ButtonIconSize;

  /**
   * Button shape
   * @default 'circular'
   */
  shape?: ButtonIconShape;

  /**
   * Tooltip text to show on hover
   */
  tooltip?: string;

  /**
   * Tooltip placement
   * @default 'bottom'
   */
  tooltipPlacement?: 'top' | 'bottom' | 'left' | 'right';

  /**
   * Whether button has aurora glow effect on hover
   * @default true
   */
  glowEffect?: boolean;

  /**
   * Custom color for icon
   * @default 'inherit'
   */
  iconColor?: 'inherit' | 'primary' | 'secondary' | 'error' | 'success' | 'warning' | 'info';
}

// Size configurations
const sizeConfig = {
  small: {
    width: '32px',
    height: '32px',
    iconSize: '18px',
  },
  medium: {
    width: '40px',
    height: '40px',
    iconSize: '24px',
  },
  large: {
    width: '56px',
    height: '56px',
    iconSize: '32px',
  },
};

/**
 * Styled circular icon button
 */
export const StyledCircularIconButton = styled(MuiIconButton, {
  shouldForwardProp: (prop) => prop !== '$glowEffect',
})<{ $glowEffect?: boolean }>(({ $glowEffect = true }) => ({
  borderRadius: '50%',
  backgroundColor: auroraOpacity.minimal,
  color: tokens.colors.text.primary,
  transition: `all ${tokens.transitions.base}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',

  '&:hover': $glowEffect
    ? {
        backgroundColor: auroraOpacity.lighter,
        boxShadow: `0 4px 12px ${auroraOpacity.strong}, 0 0 16px ${auroraOpacity.standard}`,
        transform: 'scale(1.1)',
      }
    : {
        backgroundColor: auroraOpacity.lighter,
        transform: 'scale(1.1)',
      },

  '&:active': {
    backgroundColor: auroraOpacity.standard,
    transform: 'scale(0.95)',
  },

  '&:disabled': {
    backgroundColor: auroraOpacity.veryLight,
    color: tokens.colors.text.disabled,
    cursor: 'not-allowed',
  },
}));

/**
 * Styled square icon button
 */
export const StyledSquareIconButton = styled(MuiIconButton, {
  shouldForwardProp: (prop) => prop !== '$glowEffect',
})<{ $glowEffect?: boolean }>(({ $glowEffect = true }) => ({
  borderRadius: tokens.borderRadius.medium,
  backgroundColor: auroraOpacity.minimal,
  color: tokens.colors.text.primary,
  transition: `all ${tokens.transitions.base}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',

  '&:hover': $glowEffect
    ? {
        backgroundColor: auroraOpacity.lighter,
        boxShadow: `0 4px 12px ${auroraOpacity.strong}, 0 0 16px ${auroraOpacity.standard}`,
        transform: 'translateY(-2px)',
      }
    : {
        backgroundColor: auroraOpacity.lighter,
        transform: 'translateY(-2px)',
      },

  '&:active': {
    backgroundColor: auroraOpacity.standard,
    transform: 'scale(0.95)',
  },

  '&:disabled': {
    backgroundColor: auroraOpacity.veryLight,
    color: tokens.colors.text.disabled,
    cursor: 'not-allowed',
  },
}));

/**
 * ButtonIcon Component
 *
 * Icon-only button with support for tooltips, sizing, and glow effects.
 */
export const ButtonIcon = React.forwardRef<HTMLButtonElement, ButtonIconProps>(
  (
    {
      icon,
      size = 'medium',
      shape = 'circular',
      tooltip,
      tooltipPlacement = 'bottom',
      glowEffect = true,
      sx = {},
      ...props
    },
    ref
  ) => {
    const sizeStyles = sizeConfig[size];
    const StyledButton = shape === 'circular' ? StyledCircularIconButton : StyledSquareIconButton;

    const buttonElement = (
      <StyledButton
        ref={ref}
        $glowEffect={glowEffect}
        sx={{
          width: sizeStyles.width,
          height: sizeStyles.height,
          padding: '0',
          ...sx,
        }}
        {...props}
      >
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '100%',
            fontSize: sizeStyles.iconSize,
            lineHeight: '1',
          }}
        >
          {icon}
        </span>
      </StyledButton>
    );

    if (tooltip) {
      return (
        <Tooltip title={tooltip} placement={tooltipPlacement} arrow>
          {buttonElement}
        </Tooltip>
      );
    }

    return buttonElement;
  }
);

ButtonIcon.displayName = 'ButtonIcon';

export default ButtonIcon;
