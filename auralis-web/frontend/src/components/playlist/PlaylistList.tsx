import React, { useState, useEffect } from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  IconButton,
  Typography,
  Collapse,
  styled,
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
import { colors } from '../../theme/auralisTheme';
import { useToast } from '../shared/Toast';
import { useWebSocket } from '../../hooks/useWebSocket';
import * as playlistService from '../../services/playlistService';
import CreatePlaylistDialog from './CreatePlaylistDialog';
import EditPlaylistDialog from './EditPlaylistDialog';

interface PlaylistListProps {
  onPlaylistSelect?: (playlistId: number) => void;
  selectedPlaylistId?: number;
}

const PlaylistSection = styled(Box)({
  marginTop: '16px',
});

const SectionHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '8px 16px',
  cursor: 'pointer',
  '&:hover': {
    background: 'rgba(102, 126, 234, 0.05)',
  },
  transition: 'background 0.2s ease',
});

const SectionTitle = styled(Typography)({
  fontSize: '14px',
  fontWeight: 600,
  color: colors.text.secondary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
});

const StyledListItem = styled(ListItem)({
  padding: 0,
});

const StyledListItemButton = styled(ListItemButton)<{ selected?: boolean }>(
  ({ selected }) => ({
    paddingLeft: '32px',
    paddingRight: '8px',
    height: '40px',
    borderRadius: '6px',
    margin: '2px 8px',
    transition: 'all 0.2s ease',
    background: selected ? 'rgba(102, 126, 234, 0.15)' : 'transparent',
    borderLeft: selected ? '3px solid #667eea' : '3px solid transparent',

    '&:hover': {
      background: selected
        ? 'rgba(102, 126, 234, 0.2)'
        : 'rgba(102, 126, 234, 0.08)',
      transform: 'translateX(2px)',

      '& .playlist-actions': {
        opacity: 1,
      },
    },

    '& .MuiListItemText-primary': {
      fontSize: '14px',
      color: selected ? colors.text.primary : colors.text.secondary,
      fontWeight: selected ? 600 : 400,
    },
  })
);

const PlaylistActions = styled(Box)({
  display: 'flex',
  gap: '4px',
  opacity: 0,
  transition: 'opacity 0.2s ease',
});

const ActionButton = styled(IconButton)({
  width: '28px',
  height: '28px',
  color: colors.text.secondary,
  '&:hover': {
    color: '#667eea',
    background: 'rgba(102, 126, 234, 0.1)',
  },
  '& .MuiSvgIcon-root': {
    fontSize: '18px',
  },
});

const AddButton = styled(IconButton)({
  width: '28px',
  height: '28px',
  color: colors.text.secondary,
  '&:hover': {
    color: '#667eea',
    background: 'rgba(102, 126, 234, 0.1)',
  },
  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
});

const EmptyState = styled(Box)({
  padding: '16px 32px',
  textAlign: 'center',
  color: colors.text.disabled,
  fontSize: '13px',
});

export const PlaylistList: React.FC<PlaylistListProps> = ({
  onPlaylistSelect,
  selectedPlaylistId,
}) => {
  const [playlists, setPlaylists] = useState<playlistService.Playlist[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingPlaylist, setEditingPlaylist] = useState<playlistService.Playlist | null>(null);
  const [loading, setLoading] = useState(false);
  const { success, error, info } = useToast();

  // WebSocket connection for real-time updates
  const { connected, lastMessage } = useWebSocket('ws://localhost:8765/ws');

  // Load playlists on mount
  useEffect(() => {
    fetchPlaylists();
  }, []);

  // Handle WebSocket messages for real-time playlist updates
  useEffect(() => {
    if (!lastMessage) return;

    try {
      const message = JSON.parse(lastMessage);

      switch (message.type) {
        case 'playlist_created':
          // Refresh playlists when a new one is created
          fetchPlaylists();
          break;

        case 'playlist_updated':
          // Update the specific playlist
          setPlaylists((prev) =>
            prev.map((p) =>
              p.id === message.data.playlist_id
                ? { ...p, ...message.data.updates }
                : p
            )
          );
          break;

        case 'playlist_deleted':
          // Remove deleted playlist
          setPlaylists((prev) =>
            prev.filter((p) => p.id !== message.data.playlist_id)
          );
          break;

        case 'playlist_tracks_added':
        case 'playlist_track_removed':
        case 'playlist_cleared':
          // Refresh playlists to get updated track counts
          fetchPlaylists();
          break;
      }
    } catch (err) {
      console.error('Error parsing WebSocket message:', err);
    }
  }, [lastMessage]);

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
              <StyledListItem key={playlist.id}>
                <StyledListItemButton
                  selected={selectedPlaylistId === playlist.id}
                  onClick={() => onPlaylistSelect && onPlaylistSelect(playlist.id)}
                >
                  <ListItemText
                    primary={playlist.name}
                    secondary={`${playlist.track_count} tracks`}
                    secondaryTypographyProps={{
                      sx: {
                        fontSize: '12px',
                        color: colors.text.disabled,
                      },
                    }}
                  />
                  <PlaylistActions className="playlist-actions">
                    <Tooltip title="Edit playlist">
                      <ActionButton
                        data-testid="edit-playlist-button"
                        aria-label="Edit playlist"
                        onClick={(e) => handleEdit(playlist.id, e)}
                      >
                        <Edit />
                      </ActionButton>
                    </Tooltip>
                    <Tooltip title="Delete playlist">
                      <ActionButton
                        data-testid="delete-playlist-button"
                        aria-label="Delete playlist"
                        onClick={(e) => handleDelete(playlist.id, playlist.name, e)}
                      >
                        <Delete />
                      </ActionButton>
                    </Tooltip>
                  </PlaylistActions>
                </StyledListItemButton>
              </StyledListItem>
            ))
          )}
        </List>
      </Collapse>

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
