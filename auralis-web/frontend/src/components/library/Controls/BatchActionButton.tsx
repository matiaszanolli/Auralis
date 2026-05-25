/**
 * BatchActionButton Component
 *
 * Reusable action button for batch operations toolbar
 */

import { MouseEvent, ReactNode } from 'react';
import { Tooltip } from '@/design-system';
import { ActionButton } from './BatchActionsToolbarStyles';

interface BatchActionButtonProps {
  icon: ReactNode;
  title: string;
  onClick: (event: MouseEvent<HTMLElement>) => void;
}

export const BatchActionButton = ({
  icon,
  title,
  onClick,
}: BatchActionButtonProps) => {
  const handleClick = (event: MouseEvent<HTMLElement>) => {
    onClick(event);
  };

  return (
    <Tooltip title={title}>
      <ActionButton onClick={handleClick} size="medium" aria-label={title}>
        {icon}
      </ActionButton>
    </Tooltip>
  );
};
