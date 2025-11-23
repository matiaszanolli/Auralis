/**
 * BatchActionButton Component
 *
 * Reusable action button for batch operations toolbar
 */

import React from 'react';
import { Tooltip } from '@mui/material';
import { ActionButton } from './BatchActionsToolbarStyles';

interface BatchActionButtonProps {
  icon: React.ReactNode;
  title: string;
  onClick: () => void;
}

export const BatchActionButton: React.FC<BatchActionButtonProps> = ({
  icon,
  title,
  onClick,
}) => {
  return (
    <Tooltip title={title}>
      <ActionButton onClick={onClick} size="medium">
        {icon}
      </ActionButton>
    </Tooltip>
  );
};
