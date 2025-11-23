import React from 'react';
import { ListItemIcon, ListItemText, Divider } from '@mui/material';
import { StyledMenuItem } from './ContextMenu.styles';
import { ContextMenuAction } from './contextMenuActions';
import { auroraOpacity } from '../../library/Color.styles';

interface ContextMenuActionsProps {
  actions: ContextMenuAction[];
  onActionClick: (action: ContextMenuAction) => void;
}

/**
 * ContextMenuActions - Renders main context menu actions
 *
 * Displays list of actions with optional dividers and destructive styling.
 * Handles icon rendering and menu dismissal on action click.
 *
 * @example
 * <ContextMenuActions
 *   actions={actions}
 *   onActionClick={handleAction}
 * />
 */
export const ContextMenuActions: React.FC<ContextMenuActionsProps> = ({
  actions,
  onActionClick,
}) => {
  return (
    <>
      {actions.map((action, index) => (
        <React.Fragment key={action.id}>
          {action.divider && index > 0 && (
            <Divider sx={{ borderColor: auroraOpacity.minimal, my: 1 }} />
          )}
          <StyledMenuItem
            onClick={() => onActionClick(action)}
            disabled={action.disabled}
            destructive={action.destructive}
          >
            {action.icon && <ListItemIcon>{action.icon}</ListItemIcon>}
            <ListItemText>{action.label}</ListItemText>
          </StyledMenuItem>
        </React.Fragment>
      ))}
    </>
  );
};

export default ContextMenuActions;
