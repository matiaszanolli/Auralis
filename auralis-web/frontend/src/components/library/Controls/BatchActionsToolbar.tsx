/**
 * BatchActionsToolbar Component (Refactored)
 *
 * Floating toolbar that appears when tracks are selected.
 * Refactored from 240 lines using extracted components and helpers.
 *
 * Extracted modules:
 * - BatchActionsToolbarStyles - Styled components
 * - BatchActionButton - Reusable action button
 * - useBatchActionsMenu - More menu state
 */

import React from 'react';
import {
  Close,
  PlaylistAdd,
  QueueMusic,
  Delete,
  Favorite,
  MoreVert
} from '@mui/icons-material';
import {
  ToolbarContainer,
  SelectionCount,
  CloseButton,
} from './BatchActionsToolbarStyles';
import { BatchActionButton } from './BatchActionButton';
import { BatchActionsMoreMenu } from './BatchActionsMoreMenu';
import { useBatchActionsMenu } from './useBatchActionsMenu';

interface BatchActionsToolbarProps {
  selectedCount: number;
  onAddToPlaylist?: () => void;
  onAddToQueue?: () => void;
  onRemove?: () => void;
  onToggleFavorite?: () => void;
  onEditMetadata?: () => void;
  onClearSelection: () => void;
  context?: 'library' | 'playlist' | 'favorites' | 'queue';
}

/**
 * Get context-specific label for remove action
 */
const getRemoveLabel = (context: string): string => {
  switch (context) {
    case 'playlist':
      return 'Remove from Playlist';
    case 'favorites':
      return 'Remove from Favorites';
    case 'queue':
      return 'Remove from Queue';
    default:
      return 'Delete';
  }
};

/**
 * BatchActionsToolbar - Main orchestrator component
 *
 * Floating toolbar with conditional action buttons and menu
 */
const BatchActionsToolbar: React.FC<BatchActionsToolbarProps> = ({
  selectedCount,
  onAddToPlaylist,
  onAddToQueue,
  onRemove,
  onToggleFavorite,
  onEditMetadata,
  onClearSelection,
  context = 'library',
}) => {
  const {
    moreMenuAnchor,
    handleMoreMenuOpen,
    handleMoreMenuClose,
    handleAction,
  } = useBatchActionsMenu();

  return (
    <ToolbarContainer elevation={8}>
      <SelectionCount>
        {selectedCount} {selectedCount === 1 ? 'track' : 'tracks'} selected
      </SelectionCount>

      {/* Primary Actions */}
      {onAddToPlaylist && (
        <BatchActionButton
          icon={<PlaylistAdd />}
          title="Add to Playlist"
          onClick={onAddToPlaylist}
        />
      )}

      {onAddToQueue && (
        <BatchActionButton
          icon={<QueueMusic />}
          title="Add to Queue"
          onClick={onAddToQueue}
        />
      )}

      {onToggleFavorite && (
        <BatchActionButton
          icon={<Favorite />}
          title="Toggle Favorite"
          onClick={onToggleFavorite}
        />
      )}

      {onRemove && (
        <BatchActionButton
          icon={<Delete />}
          title={getRemoveLabel(context)}
          onClick={onRemove}
        />
      )}

      {/* More Actions Menu */}
      {onEditMetadata && (
        <>
          <BatchActionButton
            icon={<MoreVert />}
            title="More Actions"
            onClick={handleMoreMenuOpen}
          />
          <BatchActionsMoreMenu
            anchorEl={moreMenuAnchor}
            onClose={handleMoreMenuClose}
            onEditMetadata={onEditMetadata}
          />
        </>
      )}

      {/* Clear Selection Button */}
      <CloseButton onClick={onClearSelection} size="small">
        <Close />
      </CloseButton>
    </ToolbarContainer>
  );
};

export default BatchActionsToolbar;
