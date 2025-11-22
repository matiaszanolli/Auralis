import React, { useState, useEffect } from 'react';
import {
  Box,
  List,
  ListItemText,
  Collapse,
  Tooltip,
} from '@mui/material';
import {
  QueueMusic,
  Add,
  ExpandMore,
  ExpandLess,
  Delete,
  Edit,
} from '@mui/icons-material';
import { useToast } from '../shared/Toast';
import { useWebSocketContext } from '../../contexts/WebSocketContext';
import { useContextMenu, ContextMenu, getPlaylistContextActions } from '../shared/ContextMenu';
import * as playlistService from '../../services/playlistService';
import CreatePlaylistDialog from './CreatePlaylistDialog';
import EditPlaylistDialog from './EditPlaylistDialog';
import { DroppablePlaylist } from './DroppablePlaylist';
import {
  PlaylistSection,
  SectionHeader,
  SectionTitle,
  AddButton,
  EmptyState,
} from './PlaylistList.styles';

interface PlaylistListProps {
  onPlaylistSelect?: (playlistId: number) => void;
  selectedPlaylistId?: number;
}

export const PlaylistList: React.FC<PlaylistListProps> = ({
  onPlaylistSelect,
  selectedPlaylistId,
}) => {
  const [playlists, setPlaylists] = useState<playlistService.Playlist[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingPlaylist, setEditingPlaylist] = useState<playlistService.Playlist | null>(null);
  const [contextMenuPlaylist, setContextMenuPlaylist] = useState<playlistService.Playlist | null>(null);
  const [loading, setLoading] = useState(false);
  const { success, error, info } = useToast();

  // WebSocket connection for real-time updates (using shared WebSocketContext)
  const { subscribe } = useWebSocketContext();

  // Context menu state
  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();

  // Load playlists on mount
  useEffect(() => {
    fetchPlaylists();
  }, []);

  // Handle WebSocket messages for real-time playlist updates
  useEffect(() => {
    console.log('📝 PlaylistList: Setting up WebSocket subscriptions');

    // Subscribe to playlist_created
    const unsubscribeCreated = subscribe('playlist_created', () => {
      fetchPlaylists();
    });

    // Subscribe to playlist_updated
    const unsubscribeUpdated = subscribe('playlist_updated', (message: any) => {
      try {
        setPlaylists((prev) =>
          prev.map((p) =>
            p.id === message.data.playlist_id
              ? { ...p, ...message.data.updates }
              : p
          )
        );
      } catch (err) {
        console.error('Error handling playlist_updated:', err);
      }
    });

    // Subscribe to playlist_deleted
    const unsubscribeDeleted = subscribe('playlist_deleted', (message: any) => {
      try {
        setPlaylists((prev) =>
          prev.filter((p) => p.id !== message.data.playlist_id)
        );
      } catch (err) {
        console.error('Error handling playlist_deleted:', err);
      }
    });

    // Subscribe to playlist_tracks_added
    const unsubscribeTracksAdded = subscribe('playlist_tracks_added', () => {
      fetchPlaylists();
    });

    // Subscribe to playlist_track_removed
    const unsubscribeTrackRemoved = subscribe('playlist_track_removed', () => {
      fetchPlaylists();
    });

    // Subscribe to playlist_cleared
    const unsubscribeCleared = subscribe('playlist_cleared', () => {
      fetchPlaylists();
    });

    // Cleanup: unsubscribe from all message types
    return () => {
      console.log('📝 PlaylistList: Cleaning up WebSocket subscriptions');
      unsubscribeCreated();
      unsubscribeUpdated();
      unsubscribeDeleted();
      unsubscribeTracksAdded();
      unsubscribeTrackRemoved();
      unsubscribeCleared();
    };
  }, [subscribe]);

  const fetchPlaylists = async () => {
    setLoading(true);
    try {
      const response = await playlistService.getPlaylists();
      setPlaylists(response.playlists);
    } catch (error) {
      console.error('Failed to load playlists:', error);
      // Don't show error toast on initial load, just log it
    } finally {
      setLoading(false);
    }
  };

  const handlePlaylistCreated = (playlist: playlistService.Playlist) => {
    setPlaylists((prev) => [...prev, playlist]);
    if (onPlaylistSelect) {
      onPlaylistSelect(playlist.id);
    }
  };

  const handleDelete = async (playlistId: number, playlistName: string, e: React.MouseEvent) => {
    e.stopPropagation();

    if (!window.confirm(`Delete playlist "${playlistName}"?`)) {
      return;
    }

    try {
      await playlistService.deletePlaylist(playlistId);
      setPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
      success(`Playlist "${playlistName}" deleted`);

      // Clear selection if deleted playlist was selected
      if (selectedPlaylistId === playlistId && onPlaylistSelect) {
        onPlaylistSelect(-1);
      }
    } catch (err) {
      error(`Failed to delete playlist: ${err}`);
    }
  };

  const handleEdit = (playlistId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const playlist = playlists.find((p) => p.id === playlistId);
    if (playlist) {
      setEditingPlaylist(playlist);
      setEditDialogOpen(true);
    }
  };

  const handlePlaylistUpdated = () => {
    // Refresh playlists to get latest data
    fetchPlaylists();
  };

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
  const contextActions = contextMenuPlaylist
    ? getPlaylistContextActions(contextMenuPlaylist.id.toString(), {
        onPlay: () => {
          info(`Playing playlist: ${contextMenuPlaylist.name}`);
          if (onPlaylistSelect) {
            onPlaylistSelect(contextMenuPlaylist.id);
          }
          // TODO: Implement play playlist
        },
        onEdit: () => {
          setEditingPlaylist(contextMenuPlaylist);
          setEditDialogOpen(true);
        },
        onDelete: () => {
          handleDelete(contextMenuPlaylist.id, contextMenuPlaylist.name, new MouseEvent('click') as any);
        },
      })
    : [];

  return (
    <PlaylistSection>
      <SectionHeader
        onClick={() => setExpanded(!expanded)}
        role="button"
        aria-label={expanded ? 'Collapse playlists' : 'Expand playlists'}
        aria-expanded={expanded}
      >
        <SectionTitle>
          <QueueMusic sx={{ fontSize: '18px' }} />
          Playlists ({playlists.length})
        </SectionTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Tooltip title="Create playlist">
            <AddButton
              onClick={(e) => {
                e.stopPropagation();
                setCreateDialogOpen(true);
              }}
            >
              <Add />
            </AddButton>
          </Tooltip>
          {expanded ? <ExpandLess /> : <ExpandMore />}
        </Box>
      </SectionHeader>

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
                  onContextMenu={(e) => handleContextMenuOpen(e, playlist)}
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
        onClose={handleContextMenuClose}
        actions={contextActions}
      />

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
