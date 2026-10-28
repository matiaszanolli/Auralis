/**
 * SegmentedControl Primitive Component
 *
 * A group of mutually exclusive options displayed as connected segments.
 * Used for view mode toggles, sort selectors, and similar controls.
 *
 * Usage:
 *   <SegmentedControl
 *     value="az"
 *     onChange={(value) => setSortBy(value)}
 *     options={[
 *       { value: 'az', label: 'A-Z' },
 *       { value: 'year', label: 'Year' },
 *     ]}
 *   />
 *
 * @see docs/UI_DESIGN_GUIDELINES.md
 */

import { ReactNode } from 'react';
import { styled } from '@mui/material/styles';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

export interface SegmentedControlOption {
  value: string;
  label: string;
  icon?: ReactNode;
}

export interface SegmentedControlProps {
  /**
   * Currently selected value
   */
  value: string;

  /**
   * Callback when selection changes
   */
  onChange: (value: string) => void;

  /**
   * Available options
   */
  options: SegmentedControlOption[];

  /**
   * Size variant
   */
  size?: 'sm' | 'md';

  /**
   * Disabled state
   */
  disabled?: boolean;

  /**
   * Optional className for styling
   */
  className?: string;

  /**
   * Accessible name describing what the group of toggles controls.
   * Required for screen readers (#3609 / WCAG 1.3.1).
   */
  'aria-label'?: string;
}

const ControlContainer = styled('div')<{ size: 'sm' | 'md' }>(({ size: _size }) => ({
  display: 'inline-flex',
  alignItems: 'center',
  // Subtle glass container
  background: themeVars.panelFill,
  backdropFilter: 'blur(4px)',
  borderRadius: tokens.borderRadius.md,
  border: `1px solid ${themeVars.borderSubtle}`,
  padding: tokens.spacing.xxs,
  gap: tokens.spacing.xxs,
}));

const SegmentButton = styled('button')<{
  isSelected: boolean;
  size: 'sm' | 'md';
  disabled?: boolean;
}>(({ isSelected, size, disabled }) => ({
  // Reset
  border: 'none',
  outline: 'none',
  cursor: disabled ? 'not-allowed' : 'pointer',
  fontFamily: tokens.typography.fontFamily.primary,

  // Size
  height: size === 'sm' ? '28px' : '32px',
  padding: size === 'sm'
    ? `0 ${tokens.spacing.sm}`
    : `0 ${tokens.spacing.md}`,
  fontSize: size === 'sm'
    ? tokens.typography.fontSize.xs
    : tokens.typography.fontSize.sm,
  fontWeight: tokens.typography.fontWeight.medium,

  // Appearance
  borderRadius: `calc(${tokens.borderRadius.md} - 2px)`,
  color: isSelected
    ? themeVars.textPrimary
    : themeVars.textMuted,
  background: isSelected
    ? themeVars.selectedFill
    : 'transparent',
  boxShadow: isSelected
    ? `inset 0 0 8px ${tokens.colors.opacityScale.accent.veryLight}`
    : 'none',

  // Transitions
  transition: tokens.transitions.fast,
  opacity: disabled ? 0.5 : 1,

  // Icon + text layout
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.xs,

  // Hover (only when not selected and not disabled)
  '&:hover': !isSelected && !disabled ? {
    background: themeVars.hoverFill,
    color: themeVars.textSecondary,
  } : {},

  // Active (press)
  '&:active': !disabled ? {
    transform: 'scale(0.98)',
  } : {},

  // The reset above removes the outline, so the keyboard ring is restored here;
  // the global :focus-visible rule cannot win against a component class (#6030).
  '&:focus-visible': {
    outline: `2px solid ${themeVars.accent}`,
    outlineOffset: '2px',
  },
}));

export const SegmentedControl = ({
  value,
  onChange,
  options,
  size = 'sm',
  disabled = false,
  className,
  'aria-label': ariaLabel,
}: SegmentedControlProps) => {
  return (
    <ControlContainer size={size} className={className} role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <SegmentButton
          key={option.value}
          isSelected={value === option.value}
          size={size}
          disabled={disabled}
          onClick={() => !disabled && onChange(option.value)}
          type="button"
          aria-pressed={value === option.value}
        >
          {option.icon}
          {option.label}
        </SegmentButton>
      ))}
    </ControlContainer>
  );
};

export default SegmentedControl;
