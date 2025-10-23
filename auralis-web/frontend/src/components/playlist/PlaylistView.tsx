import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tooltip,
  styled,
  CircularProgress,
} from '@mui/material';
import {
  PlayArrow,
  MoreVert,
  Delete,
  Edit,
  Clear,
} from '@mui/icons-material';
import { colors, gradients } from '../../theme/auralisTheme';
import { useToast } from '../shared/Toast';
import { useWebSocket } from '../../hooks/useWebSocket';
import * as playlistService from '../../services/playlistService';
import EditPlaylistDialog from './EditPlaylistDialog';

interface PlaylistViewProps {
  playlistId: number | null;
  onPlayTrack?: (trackId: number) => void;
  onBack?: () => void;
}

const ViewContainer = styled(Box)({
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
});

const Header = styled(Box)({
  padding: '32px',
  background: `linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%)`,
  borderBottom: `1px solid rgba(102, 126, 234, 0.2)`,
});

const PlaylistTitle = styled(Typography)({
  fontSize: '32px',
  fontWeight: 700,
  color: colors.text.primary,
  marginBottom: '8px',
  background: gradients.aurora,
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
});

const PlaylistMeta = styled(Typography)({
  fontSize: '14px',
  color: colors.text.secondary,
  marginBottom: '16px',
});

const ActionButtons = styled(Box)({
  display: 'flex',
  gap: '12px',
  marginTop: '16px',
});

const PlayButton = styled(IconButton)({
  background: gradients.aurora,
  color: '#ffffff',
  width: '48px',
  height: '48px',
  '&:hover': {
    background: 'linear-gradient(135deg, #7c8ef0 0%, #8b5bb5 100%)',
    transform: 'scale(1.05)',
  },
  transition: 'all 0.2s ease',
});

const SecondaryButton = styled(IconButton)({
  background: 'rgba(102, 126, 234, 0.15)',
  color: colors.text.secondary,
  width: '48px',
  height: '48px',
  '&:hover': {
    background: 'rgba(102, 126, 234, 0.25)',
    color: colors.text.primary,
  },
  transition: 'all 0.2s ease',
});

const StyledTableContainer = styled(TableContainer)({
  flex: 1,
  overflow: 'auto',
  background: 'transparent',
  '&::-webkit-scrollbar': {
    width: '8px',
  },
  '&::-webkit-scrollbar-track': {
    background: colors.background.primary,
  },
  '&::-webkit-scrollbar-thumb': {
    background: 'rgba(102, 126, 234, 0.3)',
    borderRadius: '4px',
    '&:hover': {
      background: 'rgba(102, 126, 234, 0.5)',
    },
  },
});

const StyledTable = styled(Table)({
  '& .MuiTableHead-root': {
    background: colors.background.secondary,
    position: 'sticky',
    top: 0,
    zIndex: 1,
  },
  '& .MuiTableCell-head': {
    color: colors.text.disabled,
    fontSize: '12px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    borderBottom: `1px solid rgba(102, 126, 234, 0.2)`,
  },
});

const StyledTableRow = styled(TableRow)({
  cursor: 'pointer',
  transition: 'all 0.2s ease',
  '&:hover': {
    background: 'rgba(102, 126, 234, 0.08)',
    transform: 'translateX(2px)',
    '& .row-actions': {
      opacity: 1,
    },
  },
  '& .MuiTableCell-root': {
    borderBottom: `1px solid rgba(102, 126, 234, 0.05)`,
    color: colors.text.secondary,
    fontSize: '14px',
  },
});

const RowActions = styled(Box)({
  display: 'flex',
  gap: '4px',
  opacity: 0,
  transition: 'opacity 0.2s ease',
});

const EmptyState = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100%',
  padding: '64px 32px',
  textAlign: 'center',
  color: colors.text.disabled,
});

export const PlaylistView: React.FC<PlaylistViewProps> = ({
  playlistId,
  onPlayTrack,
  onBack,
}) => {
  const [playlist, setPlaylist] = useState<playlistService.Playlist | null>(null);
  const [loading, setLoading] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const { success, showError } = useToast();

  // WebSocket connection for real-time updates
  const { lastMessage } = useWebSocket('ws://localhost:8765/ws');

  // Load playlist when ID changes
  useEffect(() => {
    if (playlistId) {
      fetchPlaylist();
    }
  }, [playlistId]);

  // Handle WebSocket messages for real-time updates
  useEffect(() => {
    if (!lastMessage || !playlistId) return;

    try {
      const message = JSON.parse(lastMessage);

      if (
        message.type === 'playlist_updated' ||
        message.type === 'playlist_tracks_added' ||
        message.type === 'playlist_track_removed' ||
        message.type === 'playlist_cleared'
      ) {
        if (message.data.playlist_id === playlistId) {
          fetchPlaylist();
        }
      }
    } catch (err) {
      console.error('Error parsing WebSocket message:', err);
    }
  }, [lastMessage, playlistId]);

  const fetchPlaylist = async () => {
    if (!playlistId) return;

    setLoading(true);
    try {
      const data = await playlistService.getPlaylist(playlistId);
      setPlaylist(data);
    } catch (error) {
      showError(`Failed to load playlist: ${error}`);
      onBack?.();
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveTrack = async (trackId: number, trackTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();

    if (!playlistId) return;

    try {
      await playlistService.removeTrackFromPlaylist(playlistId, trackId);
      success(`Removed "${trackTitle}" from playlist`);
    } catch (error) {
      showError(`Failed to remove track: ${error}`);
    }
  };

  const handleClearPlaylist = async () => {
    if (!playlistId || !playlist) return;

    if (!window.confirm(`Remove all tracks from "${playlist.name}"?`)) {
      return;
    }

    try {
      await playlistService.clearPlaylist(playlistId);
      success('Playlist cleared');
    } catch (error) {
      showError(`Failed to clear playlist: ${error}`);
    }
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatTotalDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }
    return `${mins} min`;
  };

  if (!playlistId) {
    return (
      <EmptyState>
        <Typography variant="h6" sx={{ mb: 1, color: colors.text.secondary }}>
          No Playlist Selected
        </Typography>
        <Typography variant="body2">
          Select a playlist from the sidebar to view its contents
        </Typography>
      </EmptyState>
    );
  }

  if (loading) {
    return (
      <EmptyState>
        <CircularProgress sx={{ color: '#667eea' }} />
      </EmptyState>
    );
  }

  if (!playlist) {
    return null;
  }

  const tracks = playlist.tracks || [];

  return (
    <ViewContainer>
      <Header>
        <PlaylistTitle>{playlist.name}</PlaylistTitle>
        {playlist.description && (
          <Typography sx={{ color: colors.text.secondary, mb: 2, fontSize: '14px' }}>
            {playlist.description}
          </Typography>
        )}
        <PlaylistMeta>
          {playlist.track_count} track{playlist.track_count !== 1 ? 's' : ''}
          {' • '}
          {formatTotalDuration(playlist.total_duration)}
        </PlaylistMeta>
        <ActionButtons>
          {tracks.length > 0 && (
            <Tooltip title="Play all">
              <PlayButton onClick={() => tracks[0] && onPlayTrack?.(tracks[0].id)}>
                <PlayArrow />
              </PlayButton>
            </Tooltip>
          )}
          <Tooltip title="Edit playlist">
            <SecondaryButton onClick={() => setEditDialogOpen(true)}>
              <Edit />
            </SecondaryButton>
          </Tooltip>
          {tracks.length > 0 && (
            <Tooltip title="Clear playlist">
              <SecondaryButton onClick={handleClearPlaylist}>
                <Clear />
              </SecondaryButton>
            </Tooltip>
          )}
        </ActionButtons>
      </Header>

      {tracks.length === 0 ? (
        <EmptyState>
          <Typography variant="h6" sx={{ mb: 1, color: colors.text.secondary }}>
            No Tracks
          </Typography>
          <Typography variant="body2">
            Right-click on tracks to add them to this playlist
          </Typography>
        </EmptyState>
      ) : (
        <StyledTableContainer>
          <StyledTable>
            <TableHead>
              <TableRow>
                <TableCell width="40">#</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Artist</TableCell>
                <TableCell>Album</TableCell>
                <TableCell width="100" align="right">Duration</TableCell>
                <TableCell width="80" align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {tracks.map((track, index) => (
                <StyledTableRow
                  key={track.id}
                  onClick={() => onPlayTrack?.(track.id)}
                >
                  <TableCell>{index + 1}</TableCell>
                  <TableCell sx={{ color: colors.text.primary, fontWeight: 500 }}>
                    {track.title}
                  </TableCell>
                  <TableCell>{track.artist || 'Unknown Artist'}</TableCell>
                  <TableCell>{track.album || 'Unknown Album'}</TableCell>
                  <TableCell align="right">{formatDuration(track.duration)}</TableCell>
                  <TableCell align="right">
                    <RowActions className="row-actions">
                      <Tooltip title="Remove from playlist">
                        <IconButton
                          size="small"
                          onClick={(e) => handleRemoveTrack(track.id, track.title, e)}
                          sx={{
                            color: colors.text.disabled,
                            '&:hover': { color: '#ff4444' },
                          }}
                        >
                          <Delete fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </RowActions>
                  </TableCell>
                </StyledTableRow>
              ))}
            </TableBody>
          </StyledTable>
        </StyledTableContainer>
      )}

      <EditPlaylistDialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        playlist={playlist}
        onPlaylistUpdated={fetchPlaylist}
      />
    </ViewContainer>
  );
};

export default PlaylistView;
