/**
 * EnhancementToggle - Re-export from shared component
 *
 * This file provides backward compatibility for the player-bar variant.
 * The actual implementation is now unified in the shared component.
 *
 * Usage:
 * <EnhancementToggle
 *   isEnabled={isEnhanced}
 *   onToggle={(enabled) => setIsEnhanced(enabled)}
 * />
 *
 * @see ../shared/EnhancementToggle.tsx for the unified implementation
 */

import React from 'react';
import {
  EnhancementToggle as SharedEnhancementToggle,
  EnhancementToggleProps,
} from '../shared/EnhancementToggle';

/**
 * Button variant wrapper - adapts the shared component for player-bar usage
 * The shared component expects onToggle(enabled: boolean) callback,
 * but this variant just calls onToggle() without arguments for backward compatibility.
 */
export const EnhancementToggle: React.FC<Omit<EnhancementToggleProps, 'onToggle'> & { onToggle: () => void }> = (
  { isEnabled, onToggle, ...props }
) => {
  return (
    <SharedEnhancementToggle
      variant="button"
      isEnabled={isEnabled}
      onToggle={(enabled) => onToggle()}
      {...props}
    />
  );
};

EnhancementToggle.displayName = 'EnhancementToggle';
