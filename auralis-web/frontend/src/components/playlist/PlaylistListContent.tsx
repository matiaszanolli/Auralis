import { MouseEvent } from 'react';
import { Box, Collapse } from '@mui/material';
import { Button, List } from '@/design-system';
import { ContextMenu, ContextMenuAction } from '@/components/shared/ContextMenu';
import { DroppablePlaylist } from './DroppablePlaylist';
import { EmptyState } from './PlaylistList.styles';
import * as playlistService from '@/services/playlistService';

interface PlaylistListContentProps {
  playlists: playlistService.Playlist[];
  loading: boolean;
  /** Set when the last (re)load failed; the existing list, if any, is kept. */
  error?: string | null;
  onRetry?: () => void;
  expanded: boolean;
  selectedPlaylistId?: number;
  contextMenuState: {
    isOpen: boolean;
    mousePosition?: { top: number; left: number };
  };
  contextActions: ContextMenuAction[];
  onPlaylistSelect?: (playlistId: number) => void;
  onContextMenuOpen: (e: MouseEvent, playlist: playlistService.Playlist) => void;
  onContextMenuClose: () => void;
}

/**
 * PlaylistListContent - Renders playlist list with context menu
 *
 * Displays:
 * - Loading state, load-error state with retry, or empty message
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
export const PlaylistListContent = ({
  playlists,
  loading,
  error,
  onRetry,
  expanded,
  selectedPlaylistId,
  contextMenuState,
  contextActions,
  onPlaylistSelect,
  onContextMenuOpen,
  onContextMenuClose,
}: PlaylistListContentProps) => {
  return (
    <>
      <Collapse in={expanded}>
        <List sx={{ py: 0 }}>
          {loading ? (
            <EmptyState>Loading playlists...</EmptyState>
          ) : playlists.length === 0 && error ? (
            // A failed load is not an empty library (#5645).
            <EmptyState role="alert">
              {error}
              {onRetry && (
                <>
                  <br />
                  <Button variant="ghost" size="sm" onClick={onRetry}>Retry</Button>
                </>
              )}
            </EmptyState>
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
