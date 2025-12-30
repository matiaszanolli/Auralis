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
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import { tokens } from '../tokens';

export interface SegmentedControlOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
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
}

const ControlContainer = styled('div')<{ size: 'sm' | 'md' }>(({ size }) => ({
  display: 'inline-flex',
  alignItems: 'center',
  // Subtle glass container
  background: 'rgba(255, 255, 255, 0.03)',
  backdropFilter: 'blur(4px)',
  borderRadius: tokens.borderRadius.md,
  border: '1px solid rgba(255, 255, 255, 0.06)',
  padding: '2px',
  gap: '2px',
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
    ? tokens.colors.text.primary
    : tokens.colors.text.tertiary,
  background: isSelected
    ? 'rgba(255, 255, 255, 0.08)'
    : 'transparent',
  boxShadow: isSelected
    ? 'inset 0 0 8px rgba(115, 102, 240, 0.1)'
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
    background: 'rgba(255, 255, 255, 0.04)',
    color: tokens.colors.text.secondary,
  } : {},

  // Active (press)
  '&:active': !disabled ? {
    transform: 'scale(0.98)',
  } : {},
}));

export const SegmentedControl: React.FC<SegmentedControlProps> = ({
  value,
  onChange,
  options,
  size = 'sm',
  disabled = false,
  className,
}) => {
  return (
    <ControlContainer size={size} className={className}>
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
