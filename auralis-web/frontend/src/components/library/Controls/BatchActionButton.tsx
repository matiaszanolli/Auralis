/**
 * BatchActionButton Component
 *
 * Reusable action button for batch operations toolbar
 */

import React from 'react';
import { Tooltip } from '@/design-system';
import { ActionButton } from './BatchActionsToolbarStyles';

interface BatchActionButtonProps {
  icon: React.ReactNode;
  title: string;
  onClick: (event: React.MouseEvent<HTMLElement>) => void;
}

export const BatchActionButton = ({
  icon,
  title,
  onClick,
}: BatchActionButtonProps) => {
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    onClick(event);
  };

  return (
    <Tooltip title={title}>
      <ActionButton onClick={handleClick} size="medium">
        {icon}
      </ActionButton>
    </Tooltip>
  );
};
