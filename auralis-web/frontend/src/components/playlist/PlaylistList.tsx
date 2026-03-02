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
 * - usePlaylistWebSocket hook for real-time updates
 * - usePlaylistOperations hook for CRUD operations
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

import React, { useState, useEffect } from 'react';
import { Box, IconButton } from '@mui/material';
import { Add } from '@mui/icons-material';
import * as playlistService from '../../services/playlistService';
import { useContextMenu } from '../shared/ContextMenu';
import CreatePlaylistDialog from './CreatePlaylistDialog';
import EditPlaylistDialog from './EditPlaylistDialog';
import { PlaylistSection } from './PlaylistList.styles';
import { PlaylistListHeader } from './PlaylistListHeader';
import { PlaylistListContent } from './PlaylistListContent';
import { usePlaylistWebSocket } from './usePlaylistWebSocket';
import { usePlaylistOperations } from './usePlaylistOperations';
import { usePlaylistContextActions } from './usePlaylistContextActions';
import { tokens } from '@/design-system';

interface PlaylistListProps {
  onPlaylistSelect?: (playlistId: number) => void;
  selectedPlaylistId?: number;
  hideHeader?: boolean;
}

export const PlaylistList: React.FC<PlaylistListProps> = ({
  onPlaylistSelect,
  selectedPlaylistId,
  hideHeader = false,
}) => {
  // State management
  const [playlists, setPlaylists] = useState<playlistService.Playlist[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingPlaylist, setEditingPlaylist] = useState<playlistService.Playlist | null>(null);
  const [contextMenuPlaylist, setContextMenuPlaylist] = useState<playlistService.Playlist | null>(null);
  const [loading, setLoading] = useState(false);

  // Context menu and utilities
  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();

  // Custom hooks for operations
  const { fetchPlaylists: fetchPlaylistsAsync, handleDelete } = usePlaylistOperations({
    selectedPlaylistId,
    onPlaylistSelect,
  });

  // Load playlists on mount
  useEffect(() => {
    const loadPlaylists = async () => {
      setLoading(true);
      const loaded = await fetchPlaylistsAsync();
      setPlaylists(loaded);
      setLoading(false);
    };
    loadPlaylists();
  }, [fetchPlaylistsAsync]);

  // WebSocket subscriptions for real-time updates
  usePlaylistWebSocket({
    onPlaylistCreated: async () => {
      const loaded = await fetchPlaylistsAsync();
      setPlaylists(loaded);
    },
    onPlaylistUpdated: (playlistId, updates) => {
      setPlaylists((prev) =>
        prev.map((p) =>
          p.id === playlistId ? { ...p, ...updates } : p
        )
      );
    },
    onPlaylistDeleted: (playlistId) => {
      setPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
    },
    onPlaylistsRefresh: async () => {
      const loaded = await fetchPlaylistsAsync();
      setPlaylists(loaded);
    },
  });

  // Playlist creation handler
  const handlePlaylistCreated = (playlist: playlistService.Playlist) => {
    setPlaylists((prev) => [...prev, playlist]);
    if (onPlaylistSelect) {
      onPlaylistSelect(playlist.id);
    }
  };

  // Playlist deletion handler
  const handleDeleteClick = async (playlistId: number, playlistName: string) => {
    const deleted = await handleDelete(playlistId, playlistName);
    if (deleted) {
      setPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
    }
  };

  // Playlist updated handler
  const handlePlaylistUpdated = async () => {
    const loaded = await fetchPlaylistsAsync();
    setPlaylists(loaded);
  };

  // Context menu handlers
  const handleContextMenuOpen = (e: React.MouseEvent, playlist: playlistService.Playlist) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenuPlaylist(playlist);
    handleContextMenu(e);
  };

  const handleContextMenuClose = () => {
    setContextMenuPlaylist(null);
    handleCloseContextMenu();
  };

  // Context menu actions
  const contextActions = usePlaylistContextActions({
    playlist: contextMenuPlaylist,
    onPlaylistSelect,
    onDelete: handleDeleteClick,
    onEdit: (playlist) => {
      setEditingPlaylist(playlist);
      setEditDialogOpen(true);
    },
  });

  return (
    <PlaylistSection>
      {!hideHeader && (
        <PlaylistListHeader
          playlistCount={playlists.length}
          expanded={expanded}
          onExpandToggle={() => setExpanded(!expanded)}
          onCreateClick={() => setCreateDialogOpen(true)}
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
        <Box
          onClick={() => setCreateDialogOpen(true)}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing.sm,
            padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
            cursor: 'pointer',
            color: tokens.colors.text.secondary,
            transition: tokens.transitions.fast,
            '&:hover': {
              color: tokens.colors.text.primary,
              backgroundColor: tokens.colors.bg.level2,
            },
          }}
        >
          <IconButton
            size="small"
            sx={{
              color: 'inherit',
              padding: 0,
            }}
          >
            <Add fontSize="small" />
          </IconButton>
          <span>New Playlist</span>
        </Box>
      )}

      <CreatePlaylistDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onPlaylistCreated={handlePlaylistCreated}
      />

      <EditPlaylistDialog
        open={editDialogOpen}
        onClose={() => {
          setEditDialogOpen(false);
          setEditingPlaylist(null);
        }}
        playlist={editingPlaylist}
        onPlaylistUpdated={handlePlaylistUpdated}
      />
    </PlaylistSection>
  );
};

export default PlaylistList;
