/**
 * ButtonGroup Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Container component for grouping multiple buttons together.
 * Provides consistent spacing, alignment, and layout options.
 *
 * Features:
 * - Horizontal and vertical layouts
 * - Customizable spacing and alignment
 * - Support for wrapped layout on mobile
 * - Automatic button connection (optional)
 *
 * @example
 * ```tsx
 * // Basic horizontal group
 * <ButtonGroup direction="row" gap="sm">
 *   <Button>Cancel</Button>
 *   <Button>Save</Button>
 * </ButtonGroup>
 *
 * // Vertical group
 * <ButtonGroup direction="column" gap="md">
 *   <Button fullWidth>Option 1</Button>
 *   <Button fullWidth>Option 2</Button>
 * </ButtonGroup>
 *
 * // Right-aligned buttons
 * <ButtonGroup direction="row" justify="flex-end" gap="md">
 *   <Button variant="text">Cancel</Button>
 *   <Button>Save</Button>
 * </ButtonGroup>
 *
 * // Centered buttons
 * <ButtonGroup direction="row" justify="center" gap="sm">
 *   <ButtonIcon icon={<LeftIcon />} />
 *   <ButtonIcon icon={<RightIcon />} />
 * </ButtonGroup>
 * ```
 */

import React from 'react';
import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

export type ButtonGroupDirection = 'row' | 'column';
export type ButtonGroupSpacing = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type ButtonGroupAlignment = 'flex-start' | 'center' | 'flex-end' | 'space-between' | 'space-around';

export interface ButtonGroupProps extends React.ComponentProps<typeof Box> {
  /**
   * Layout direction
   * @default 'row'
   */
  direction?: ButtonGroupDirection;

  /**
   * Horizontal alignment of buttons
   * @default 'flex-start'
   */
  justify?: ButtonGroupAlignment;

  /**
   * Vertical alignment of buttons
   * @default 'center'
   */
  align?: 'flex-start' | 'center' | 'flex-end' | 'stretch';

  /**
   * Gap between buttons
   * @default 'md'
   */
  gap?: ButtonGroupSpacing;

  /**
   * Whether buttons should wrap on smaller screens
   * @default true
   */
  wrap?: boolean;

  /**
   * Whether to remove default MUI button margin
   * @default true
   */
  disableButtonMargin?: boolean;

  /**
   * Custom background color
   */
  backgroundColor?: string;

  /**
   * Custom padding
   */
  padding?: string;

  children: React.ReactNode;
}

// Spacing presets
const spacingPresets = {
  xs: tokens.spacing.xs,
  sm: tokens.spacing.sm,
  md: tokens.spacing.md,
  lg: tokens.spacing.lg,
  xl: tokens.spacing.xl,
};

/**
 * Styled button group container
 */
export const StyledButtonGroup = styled(Box, {
  shouldForwardProp: (prop) =>
    ![
      'direction',
      'justify',
      'align',
      'gap',
      'wrap',
      'disableButtonMargin',
      'backgroundColor',
    ].includes(prop as string),
})<{
  $direction?: ButtonGroupDirection;
  $justify?: ButtonGroupAlignment;
  $align?: string;
  $gap?: ButtonGroupSpacing;
  $wrap?: boolean;
  $disableButtonMargin?: boolean;
  $backgroundColor?: string;
}>(
  ({
    $direction = 'row',
    $justify = 'flex-start',
    $align = 'center',
    $gap = 'md',
    $wrap = true,
    $disableButtonMargin = true,
    $backgroundColor,
  }) => ({
    display: 'flex',
    flexDirection: $direction,
    justifyContent: $justify,
    alignItems: $align,
    gap: spacingPresets[$gap],
    flexWrap: $wrap ? 'wrap' : 'nowrap',
    backgroundColor: $backgroundColor || 'transparent',
    transition: `all ${tokens.transitions.base}`,

    // Remove default MUI button margins if requested
    ..($disableButtonMargin && {
      '& button': {
        margin: '0',
      },
    }),
  })
);

/**
 * ButtonGroup Component
 *
 * Container for grouping buttons with consistent spacing and alignment.
 */
export const ButtonGroup = React.forwardRef<HTMLDivElement, ButtonGroupProps>(
  (
    {
      direction = 'row',
      justify = 'flex-start',
      align = 'center',
      gap = 'md',
      wrap = true,
      disableButtonMargin = true,
      sx = {},
      padding,
      backgroundColor,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <StyledButtonGroup
        ref={ref}
        $direction={direction}
        $justify={justify}
        $align={align}
        $gap={gap}
        $wrap={wrap}
        $disableButtonMargin={disableButtonMargin}
        $backgroundColor={backgroundColor}
        sx={{
          ...(padding && { padding }),
          ...sx,
        }}
        {...props}
      >
        {children}
      </StyledButtonGroup>
    );
  }
);

ButtonGroup.displayName = 'ButtonGroup';

export default ButtonGroup;
