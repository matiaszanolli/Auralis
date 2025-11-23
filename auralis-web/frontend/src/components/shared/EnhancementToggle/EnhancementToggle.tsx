/**
 * EnhancementToggle - Parametrized Enhancement Toggle Component
 *
 * Unified component that supports multiple UI variants for toggling audio enhancement.
 * Consolidates button-style and switch-style toggle patterns.
 *
 * Features:
 * - Multiple variants: "button" (compact icon), "switch" (form control)
 * - Design token styling with aurora glow
 * - Processing state support
 * - Smooth animations and transitions
 * - Accessible with proper ARIA labels and tooltips
 */

import React from 'react';
import { ButtonVariant } from './ButtonVariant';
import { SwitchVariant } from './SwitchVariant';

export type EnhancementToggleVariant = 'button' | 'switch';

export interface EnhancementToggleProps {
  /**
   * Whether enhancement is enabled
   */
  isEnabled: boolean;

  /**
   * Callback when toggle state changes
   */
  onToggle: (enabled: boolean) => void;

  /**
   * UI variant to display
   * @default 'button'
   */
  variant?: EnhancementToggleVariant;

  /**
   * Optional: Show processing/loading state
   */
  isProcessing?: boolean;

  /**
   * Optional: Custom label text (switch variant only)
   */
  label?: string;

  /**
   * Optional: Custom description text (switch variant only)
   */
  description?: string;

  /**
   * Optional: Show description based on enabled state
   */
  showDescription?: boolean;

  /**
   * Optional: Custom tooltip text
   */
  tooltipText?: string;
}

/**
 * EnhancementToggle - Unified enhancement toggle supporting multiple UI variants
 *
 * @example
 * // Button variant (compact, for player bar)
 * <EnhancementToggle
 *   variant="button"
 *   isEnabled={isEnhanced}
 *   onToggle={() => setIsEnhanced(!isEnhanced)}
 * />
 *
 * @example
 * // Switch variant (form control, for enhancement pane)
 * <EnhancementToggle
 *   variant="switch"
 *   isEnabled={isEnhanced}
 *   onToggle={setIsEnhanced}
 *   isProcessing={isProcessing}
 *   label="Enable Auto-Mastering"
 * />
 */
export const EnhancementToggle: React.FC<EnhancementToggleProps> = React.memo(({
  variant = 'button',
  ...props
}) => {
  if (variant === 'switch') {
    return <SwitchVariant {...props} />;
  }

  return <ButtonVariant {...props} />;
});

EnhancementToggle.displayName = 'EnhancementToggle';

export default EnhancementToggle;
