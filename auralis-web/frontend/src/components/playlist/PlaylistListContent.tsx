import React from 'react';
import { Box, Collapse } from '@mui/material';
import { List } from '@/design-system';
import { ContextMenu, ContextMenuAction } from '../shared/ContextMenu';
import { DroppablePlaylist } from './DroppablePlaylist';
import { EmptyState } from './PlaylistList.styles';
import * as playlistService from '../../services/playlistService';

interface PlaylistListContentProps {
  playlists: playlistService.Playlist[];
  loading: boolean;
  expanded: boolean;
  selectedPlaylistId?: number;
  contextMenuState: {
    isOpen: boolean;
    mousePosition?: { top: number; left: number };
  };
  contextActions: ContextMenuAction[];
  onPlaylistSelect?: (playlistId: number) => void;
  onContextMenuOpen: (e: React.MouseEvent, playlist: playlistService.Playlist) => void;
  onContextMenuClose: () => void;
}

/**
 * PlaylistListContent - Renders playlist list with context menu
 *
 * Displays:
 * - Loading state or empty message
 * - List of droppable playlists
 * - Context menu for playlist actions
 *
 * @example
 * <PlaylistListContent
 *   playlists={playlists}
 *   loading={loading}
 *   expanded={expanded}
 *   {...otherProps}
 * />
 */
export const PlaylistListContent: React.FC<PlaylistListContentProps> = ({
  playlists,
  loading,
  expanded,
  selectedPlaylistId,
  contextMenuState,
  contextActions,
  onPlaylistSelect,
  onContextMenuOpen,
  onContextMenuClose,
}) => {
  return (
    <>
      <Collapse in={expanded}>
        <List sx={{ py: 0 }}>
          {loading ? (
            <EmptyState>Loading playlists...</EmptyState>
          ) : playlists.length === 0 ? (
            <EmptyState>
              No playlists yet
              <br />
              Click + to create one
            </EmptyState>
          ) : (
            playlists.map((playlist) => (
              <Box key={playlist.id} sx={{ px: 1 }}>
                <DroppablePlaylist
                  playlistId={playlist.id}
                  playlistName={playlist.name}
                  trackCount={playlist.track_count}
                  selected={selectedPlaylistId === playlist.id}
                  onClick={() => onPlaylistSelect && onPlaylistSelect(playlist.id)}
                  onContextMenu={(e) => onContextMenuOpen(e, playlist)}
                />
              </Box>
            ))
          )}
        </List>
      </Collapse>

      {/* Context menu */}
      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={onContextMenuClose}
        actions={contextActions}
      />
    </>
  );
};

export default PlaylistListContent;
