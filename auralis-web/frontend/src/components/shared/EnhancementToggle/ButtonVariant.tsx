import { memo } from 'react';
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
export const ButtonVariant = memo<EnhancementToggleProps>(({
  isEnabled,
  onToggle,
  tooltipText,
}) => {
  // Action-describing label, also used as the button's accessible name so it
  // announces what activating it does (enable vs disable), not just "Audio
  // enhancement" (#4150 — fixes the a11y gap and the integration-test query).
  const actionLabel = isEnabled
    ? 'Disable audio enhancement'
    : 'Enable audio enhancement';

  return (
    <Tooltip
      title={tooltipText || actionLabel}
      arrow
      placement="top"
    >
      <EnhancementContainer>
        <ToggleButton
          onClick={() => onToggle(!isEnabled)}
          $isEnabled={isEnabled}
          aria-label={actionLabel}
          aria-pressed={isEnabled}
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
