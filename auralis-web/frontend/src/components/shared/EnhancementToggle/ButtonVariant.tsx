import React from 'react';
import { Tooltip } from '@/design-system';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { ToggleButton, EnhancementLabel, EnhancementContainer } from './EnhancementToggleStyles';
import { EnhancementToggleProps } from './EnhancementToggle';

/**
 * Button variant of EnhancementToggle
 * Compact icon button with label, suitable for player bars
 *
 * Features:
 * - Minimal footprint
 * - Aurora glow effect when enabled
 * - Smooth scale animations
 * - Icon rotation effect
 */
export const ButtonVariant: React.FC<EnhancementToggleProps> = React.memo(({
  isEnabled,
  onToggle,
  tooltipText,
}) => {
  const defaultTooltip = isEnabled
    ? 'Disable audio enhancement'
    : 'Enable audio enhancement';

  return (
    <Tooltip
      title={tooltipText || defaultTooltip}
      arrow
      placement="top"
    >
      <EnhancementContainer>
        <ToggleButton
          onClick={() => onToggle(!isEnabled)}
          $isEnabled={isEnabled}
          aria-label={isEnabled ? 'Disable enhancement' : 'Enable enhancement'}
        >
          <AutoAwesomeIcon />
        </ToggleButton>
        <EnhancementLabel $isEnabled={isEnabled}>
          {isEnabled ? 'Enhanced' : 'Original'}
        </EnhancementLabel>
      </EnhancementContainer>
    </Tooltip>
  );
});

ButtonVariant.displayName = 'EnhancementToggle.ButtonVariant';

export default ButtonVariant;
