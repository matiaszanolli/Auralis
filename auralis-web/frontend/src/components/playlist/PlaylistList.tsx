/**
 * PlaylistList Component
 *
 * Main orchestration component for playlist management in sidebar.
 * Handles playlist selection, creation, editing, and deletion with
 * real-time WebSocket updates.
 *
 * Features:
 * - Collapsible playlist section
 * - Create/edit/delete playlists
 * - Context menu with playlist actions
 * - WebSocket real-time updates
 * - Drag-and-drop playlist selection
 *
 * Uses:
 * - usePlaylistData hook for the list, loading flag and real-time updates
 * - usePlaylistOperations hook for deletion
 * - usePlaylistContextActions hook for context menu
 * - PlaylistListHeader for header section
 * - PlaylistListContent for list rendering
 *
 * Usage:
 * ```tsx
 * <PlaylistList
 *   onPlaylistSelect={handleSelect}
 *   selectedPlaylistId={selectedId}
 * />
 * ```
 */

import { MouseEvent, useCallback, useState } from 'react';
import { Box } from '@mui/material';
import Add from '@mui/icons-material/Add';
import * as playlistService from '@/services/playlistService';
import { useContextMenu } from '@/components/shared/ContextMenu';
import CreatePlaylistDialog from './CreatePlaylistDialog';
import EditPlaylistDialog from './EditPlaylistDialog';
import { PlaylistSection } from './PlaylistList.styles';
import { PlaylistListHeader } from './PlaylistListHeader';
import { PlaylistListContent } from './PlaylistListContent';
import { usePlaylistData } from './usePlaylistData';
import { usePlaylistOperations } from './usePlaylistOperations';
import { usePlaylistContextActions } from './usePlaylistContextActions';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

// At most one of the create dialog, edit dialog and context menu is active;
// one union makes that an invariant instead of three independent flags (#5480).
type PlaylistOverlay =
  | { kind: 'none' }
  | { kind: 'create' }
  | { kind: 'edit'; playlist: playlistService.Playlist }
  | { kind: 'contextMenu'; playlist: playlistService.Playlist };

const NO_OVERLAY: PlaylistOverlay = { kind: 'none' };

interface PlaylistListProps {
  onPlaylistSelect?: (playlistId: number) => void;
  selectedPlaylistId?: number;
  hideHeader?: boolean;
}

export const PlaylistList = ({
  onPlaylistSelect,
  selectedPlaylistId,
  hideHeader = false,
}: PlaylistListProps) => {
  const [expanded, setExpanded] = useState(true);
  const [overlay, setOverlay] = useState<PlaylistOverlay>(NO_OVERLAY);
  const { playlists, loading, refresh, addPlaylist, removePlaylist } = usePlaylistData();

  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();
  const { handleDelete } = usePlaylistOperations({ selectedPlaylistId, onPlaylistSelect });

  const openCreateDialog = () => setOverlay({ kind: 'create' });
  // Closing one overlay must not dismiss another that replaced it, so only
  // reset when `kind` is still the one being closed.
  const closeOverlay = useCallback((kind: PlaylistOverlay['kind']) => {
    setOverlay((current) => (current.kind === kind ? NO_OVERLAY : current));
  }, []);

  const handlePlaylistCreated = (playlist: playlistService.Playlist) => {
    addPlaylist(playlist);
    if (onPlaylistSelect) {
      onPlaylistSelect(playlist.id);
    }
  };

  const handleDeleteClick = async (playlistId: number, playlistName: string) => {
    const deleted = await handleDelete(playlistId, playlistName);
    if (deleted) {
      removePlaylist(playlistId);
    }
  };

  const handleContextMenuOpen = (e: MouseEvent, playlist: playlistService.Playlist) => {
    e.preventDefault();
    e.stopPropagation();
    setOverlay({ kind: 'contextMenu', playlist });
    handleContextMenu(e);
  };

  // ContextMenu runs an action's onClick and THEN onClose, so the Edit
  // action's switch to { kind: 'edit' } must survive this close.
  const handleContextMenuClose = () => {
    closeOverlay('contextMenu');
    handleCloseContextMenu();
  };

  const contextActions = usePlaylistContextActions({
    playlist: overlay.kind === 'contextMenu' ? overlay.playlist : null,
    onPlaylistSelect,
    onDelete: handleDeleteClick,
    onEdit: (playlist) => setOverlay({ kind: 'edit', playlist }),
  });

  return (
    <PlaylistSection>
      {!hideHeader && (
        <PlaylistListHeader
          playlistCount={playlists.length}
          expanded={expanded}
          onExpandToggle={() => setExpanded(!expanded)}
          onCreateClick={openCreateDialog}
        />
      )}

      <PlaylistListContent
        playlists={playlists}
        loading={loading}
        expanded={hideHeader ? true : expanded}
        selectedPlaylistId={selectedPlaylistId}
        contextMenuState={contextMenuState}
        contextActions={contextActions}
        onPlaylistSelect={onPlaylistSelect}
        onContextMenuOpen={handleContextMenuOpen}
        onContextMenuClose={handleContextMenuClose}
      />

      {hideHeader && (
        // The click target itself is a native <button> so it is keyboard
        // focusable/activatable, with an explicit accessible name — previously
        // this was a non-semantic Box onClick wrapping an unlabeled icon-only
        // IconButton, which Tab landed on as a bare "button" (#4450).
        <Box
          component="button"
          type="button"
          onClick={openCreateDialog}
          aria-label="Create new playlist"
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing.sm,
            padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
            cursor: 'pointer',
            color: themeVars.textSecondary,
            transition: tokens.transitions.fast,
            // Reset native button chrome so it matches the surrounding rows.
            width: '100%',
            background: 'transparent',
            border: 'none',
            font: 'inherit',
            textAlign: 'left',
            '&:hover': {
              color: themeVars.textPrimary,
              backgroundColor: themeVars.surfaceSecondary,
            },
          }}
        >
          <Add fontSize="small" />
          <span>New Playlist</span>
        </Box>
      )}

      <CreatePlaylistDialog
        open={overlay.kind === 'create'}
        onClose={() => closeOverlay('create')}
        onPlaylistCreated={handlePlaylistCreated}
      />

      <EditPlaylistDialog
        open={overlay.kind === 'edit'}
        onClose={() => closeOverlay('edit')}
        playlist={overlay.kind === 'edit' ? overlay.playlist : null}
        onPlaylistUpdated={refresh}
      />
    </PlaylistSection>
  );
};

export default PlaylistList;
