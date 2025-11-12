/**
 * EnhancementToggle - Re-export from shared component
 *
 * This file provides backward compatibility for the enhancement-pane variant.
 * The actual implementation is now unified in the shared component.
 *
 * Usage:
 * <EnhancementToggle
 *   enabled={isEnhanced}
 *   isProcessing={processing}
 *   onToggle={(enabled) => setIsEnhanced(enabled)}
 * />
 *
 * @see ../shared/EnhancementToggle.tsx for the unified implementation
 */

import React from 'react';
import {
  EnhancementToggle as SharedEnhancementToggle,
} from '../shared/EnhancementToggle';

interface EnhancementToggleProps {
  enabled: boolean;
  isProcessing: boolean;
  onToggle: (enabled: boolean) => void;
}

/**
 * Switch variant wrapper - adapts the shared component for enhancement-pane usage
 * Maps the local prop names (enabled) to the shared component's prop names (isEnabled).
 */
const EnhancementToggle: React.FC<EnhancementToggleProps> = React.memo(({
  enabled,
  isProcessing,
  onToggle,
}) => {
  return (
    <SharedEnhancementToggle
      variant="switch"
      isEnabled={enabled}
      isProcessing={isProcessing}
      onToggle={onToggle}
      label="Enable Auto-Mastering"
      showDescription
    />
  );
});

EnhancementToggle.displayName = 'EnhancementToggle';

export default EnhancementToggle;
