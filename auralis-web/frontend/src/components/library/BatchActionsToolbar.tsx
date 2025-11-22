/**
 * BatchActionsToolbar Component
 *
 * Floating toolbar that appears when tracks are selected.
 * Provides bulk action buttons (add to playlist, add to queue, delete, etc.)
 *
 * Usage:
 * ```tsx
 * <BatchActionsToolbar
 *   selectedCount={5}
 *   onAddToPlaylist={() => handleBulkAddToPlaylist(selectedTracks)}
 *   onAddToQueue={() => handleBulkAddToQueue(selectedTracks)}
 *   onRemove={() => handleBulkRemove(selectedTracks)}
 *   onClearSelection={() => clearSelection()}
 * />
 * ```
 */

import React, { useState } from 'react';
import {
  Box,
  Paper,
  IconButton,
  Typography,
  Button,
  Menu,
  MenuItem,
  Tooltip,
  styled,
  alpha
} from '@mui/material';
import {
  Close,
  PlaylistAdd,
  QueueMusic,
  Delete,
  Favorite,
  FavoriteBorder,
  Edit,
  MoreVert
} from '@mui/icons-material';
import { cardShadows } from './Shadow.styles';

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

const ToolbarContainer = styled(Paper)(({ theme }) => ({
  position: 'fixed',
  top: '80px',
  left: '50%',
  transform: 'translateX(-50%)',
  zIndex: 1200,
  background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.95) 0%, rgba(118, 75, 162, 0.95) 100%)',
  backdropFilter: 'blur(20px)',
  border: '1px solid rgba(255, 255, 255, 0.2)',
  borderRadius: '16px',
  padding: '12px 24px',
  display: 'flex',
  alignItems: 'center',
  gap: '16px',
  boxShadow: cardShadows.dropdownDark,
  animation: 'slideDown 0.3s ease-out',
  '@keyframes slideDown': {
    from: {
      opacity: 0,
      transform: 'translate(-50%, -20px)',
    },
    to: {
      opacity: 1,
      transform: 'translate(-50%, 0)',
    },
  },
}));

const SelectionCount = styled(Typography)(({ theme }) => ({
  color: '#ffffff',
  fontWeight: 'bold',
  fontSize: '16px',
  minWidth: '140px',
}));

const ActionButton = styled(IconButton)(({ theme }) => ({
  color: '#ffffff',
  backgroundColor: 'rgba(255, 255, 255, 0.15)',
  '&:hover': {
    backgroundColor: 'rgba(255, 255, 255, 0.25)',
  },
  transition: 'all 0.2s ease',
}));

const CloseButton = styled(IconButton)(({ theme }) => ({
  color: '#ffffff',
  marginLeft: 'auto',
  '&:hover': {
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
  },
}));

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
  const [moreMenuAnchor, setMoreMenuAnchor] = useState<null | HTMLElement>(null);

  const handleMoreMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setMoreMenuAnchor(event.currentTarget);
  };

  const handleMoreMenuClose = () => {
    setMoreMenuAnchor(null);
  };

  const handleAction = (action: () => void) => {
    action();
    handleMoreMenuClose();
  };

  // Context-specific labels
  const getRemoveLabel = () => {
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

  return (
    <ToolbarContainer elevation={8}>
      <SelectionCount>
        {selectedCount} {selectedCount === 1 ? 'track' : 'tracks'} selected
      </SelectionCount>

      {/* Primary Actions */}
      {onAddToPlaylist && (
        <Tooltip title="Add to Playlist">
          <ActionButton onClick={onAddToPlaylist} size="medium">
            <PlaylistAdd />
          </ActionButton>
        </Tooltip>
      )}

      {onAddToQueue && (
        <Tooltip title="Add to Queue">
          <ActionButton onClick={onAddToQueue} size="medium">
            <QueueMusic />
          </ActionButton>
        </Tooltip>
      )}

      {onToggleFavorite && (
        <Tooltip title="Toggle Favorite">
          <ActionButton onClick={onToggleFavorite} size="medium">
            <Favorite />
          </ActionButton>
        </Tooltip>
      )}

      {onRemove && (
        <Tooltip title={getRemoveLabel()}>
          <ActionButton onClick={onRemove} size="medium">
            <Delete />
          </ActionButton>
        </Tooltip>
      )}

      {/* More Actions Menu */}
      {(onEditMetadata) && (
        <>
          <Tooltip title="More Actions">
            <ActionButton onClick={handleMoreMenuOpen} size="medium">
              <MoreVert />
            </ActionButton>
          </Tooltip>
          <Menu
            anchorEl={moreMenuAnchor}
            open={Boolean(moreMenuAnchor)}
            onClose={handleMoreMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'right',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
            PaperProps={{
              sx: {
                background: 'linear-gradient(135deg, #1a1f3a 0%, #0A0E27 100%)',
                border: '1px solid rgba(102, 126, 234, 0.2)',
                borderRadius: '12px',
                mt: 1,
              },
            }}
          >
            {onEditMetadata && (
              <MenuItem
                onClick={() => handleAction(onEditMetadata)}
                sx={{ color: 'white', gap: 1 }}
              >
                <Edit fontSize="small" />
                Edit Metadata
              </MenuItem>
            )}
          </Menu>
        </>
      )}

      {/* Clear Selection Button */}
      <Tooltip title="Clear Selection">
        <CloseButton onClick={onClearSelection} size="small">
          <Close />
        </CloseButton>
      </Tooltip>
    </ToolbarContainer>
  );
};

export default BatchActionsToolbar;
