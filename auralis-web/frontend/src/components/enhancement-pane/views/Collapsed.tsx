import React from 'react';

import { ChevronLeft, AutoAwesome } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { IconButton, Tooltip } from '@/design-system';
import {
  CollapsedPaneContainer,
  CollapsedIconContainer,
} from '@/components/enhancement-pane/EnhancementPane.styles';

interface CollapsedProps {
  onToggleCollapse?: () => void;
}

/**
 * Collapsed - Collapsed view of enhancement pane
 *
 * Shows only icon and collapse button when collapsed.
 */
export const Collapsed = ({
  onToggleCollapse,
}: CollapsedProps) => {
  return (
    <CollapsedPaneContainer>
      <IconButton onClick={onToggleCollapse} aria-label="Expand enhancement pane" aria-expanded={false} sx={{ color: tokens.colors.text.primary }}>
        <ChevronLeft />
      </IconButton>
      <CollapsedIconContainer>
        <Tooltip title="Auto-Mastering" placement="left">
          <AutoAwesome sx={{ color: tokens.colors.accent.primary }} />
        </Tooltip>
      </CollapsedIconContainer>
    </CollapsedPaneContainer>
  );
};

export default Collapsed;
