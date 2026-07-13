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
  /** Disable the button while a batch operation is in flight (#4443). */
  disabled?: boolean;
}

export const BatchActionButton = ({
  icon,
  title,
  onClick,
  disabled = false,
}: BatchActionButtonProps) => {
  const handleClick = (event: MouseEvent<HTMLElement>) => {
    onClick(event);
  };

  return (
    <Tooltip title={title}>
      {/* A disabled button doesn't emit pointer events, so wrap it so the
          Tooltip still has a live event target (and MUI doesn't warn). */}
      <span>
        <ActionButton onClick={handleClick} size="medium" aria-label={title} disabled={disabled}>
          {icon}
        </ActionButton>
      </span>
    </Tooltip>
  );
};
