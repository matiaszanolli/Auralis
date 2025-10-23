import React, { useState, useEffect } from 'react';
import {
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  styled,
  Box,
} from '@mui/material';
import {
  PlaylistAdd,
  Favorite,
  FavoriteBorder,
  Info,
  QueueMusic,
  Add,
} from '@mui/icons-material';
import { colors } from '../../theme/auralisTheme';
import { useToast } from './Toast';
import * as playlistService from '../../services/playlistService';
import CreatePlaylistDialog from '../playlist/CreatePlaylistDialog';

interface TrackContextMenuProps {
  trackId: number | null;
  trackTitle: string;
  isFavorite: boolean;
  anchorPosition: { top: number; left: number } | null;
  onClose: () => void;
  onToggleFavorite?: () => void;
  onShowInfo?: () => void;
  onAddToQueue?: () => void;
}

const StyledMenu = styled(Menu)({
  '& .MuiPaper-root': {
    background: colors.background.secondary,
    border: `1px solid rgba(102, 126, 234, 0.2)`,
    borderRadius: '8px',
    minWidth: '220px',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
  },
});

const StyledMenuItem = styled(MenuItem)({
  fontSize: '14px',
  color: colors.text.primary,
  padding: '10px 16px',
  transition: 'all 0.2s ease',
  '&:hover': {
    background: 'rgba(102, 126, 234, 0.15)',
    transform: 'translateX(2px)',
  },
  '& .MuiListItemIcon-root': {
    color: colors.text.secondary,
    minWidth: 36,
  },
});

const PlaylistMenuItem = styled(MenuItem)({
  fontSize: '13px',
  color: colors.text.secondary,
  padding: '8px 16px 8px 48px',
  transition: 'all 0.2s ease',
  '&:hover': {
    background: 'rgba(102, 126, 234, 0.1)',
    color: colors.text.primary,
    transform: 'translateX(2px)',
  },
});

const CreateNewMenuItem = styled(MenuItem)({
  fontSize: '13px',
  color: '#667eea',
  padding: '8px 16px 8px 48px',
  fontWeight: 600,
  transition: 'all 0.2s ease',
  '&:hover': {
    background: 'rgba(102, 126, 234, 0.15)',
    transform: 'translateX(2px)',
  },
});

const SectionLabel = styled(Box)({
  fontSize: '11px',
  fontWeight: 600,
  color: colors.text.disabled,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  padding: '8px 16px 4px 16px',
});

export const TrackContextMenu: React.FC<TrackContextMenuProps> = ({
  trackId,
  trackTitle,
  isFavorite,
  anchorPosition,
  onClose,
  onToggleFavorite,
  onShowInfo,
  onAddToQueue,
}) => {
  const [playlists, setPlaylists] = useState<playlistService.Playlist[]>([]);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const { success, showError } = useToast();

  // Load playlists when menu opens
  useEffect(() => {
    if (anchorPosition) {
      fetchPlaylists();
    }
  }, [anchorPosition]);

  const fetchPlaylists = async () => {
    try {
      const response = await playlistService.getPlaylists();
      setPlaylists(response.playlists);
    } catch (error) {
      console.error('Failed to load playlists:', error);
    }
  };

  const handleAddToPlaylist = async (playlistId: number, playlistName: string) => {
    if (!trackId) return;

    try {
      await playlistService.addTracksToPlaylist(playlistId, [trackId]);
      success(`Added to "${playlistName}"`);
      onClose();
    } catch (error) {
      showError(`Failed to add to playlist: ${error}`);
    }
  };

  const handleCreateNewPlaylist = () => {
    onClose();
    setCreateDialogOpen(true);
  };

  const handlePlaylistCreated = async (playlist: playlistService.Playlist) => {
    if (!trackId) return;

    // Add the track to the newly created playlist
    try {
      await playlistService.addTracksToPlaylist(playlist.id, [trackId]);
      success(`Added to "${playlist.name}"`);
    } catch (error) {
      showError(`Failed to add to playlist: ${error}`);
    }
  };

  return (
    <>
      <StyledMenu
        open={Boolean(anchorPosition)}
        onClose={onClose}
        anchorReference="anchorPosition"
        anchorPosition={anchorPosition || undefined}
      >
        {onAddToQueue && (
          <>
            <StyledMenuItem onClick={() => { onAddToQueue(); onClose(); }}>
              <ListItemIcon>
                <QueueMusic />
              </ListItemIcon>
              <ListItemText>Add to Queue</ListItemText>
            </StyledMenuItem>
            <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)' }} />
          </>
        )}

        <StyledMenuItem>
          <ListItemIcon>
            <PlaylistAdd />
          </ListItemIcon>
          <ListItemText>Add to Playlist</ListItemText>
        </StyledMenuItem>

        {playlists.length > 0 && (
          <>
            <SectionLabel>Your Playlists</SectionLabel>
            {playlists.map((playlist) => (
              <PlaylistMenuItem
                key={playlist.id}
                onClick={() => handleAddToPlaylist(playlist.id, playlist.name)}
              >
                {playlist.name} ({playlist.track_count})
              </PlaylistMenuItem>
            ))}
          </>
        )}

        <CreateNewMenuItem onClick={handleCreateNewPlaylist}>
          <Add sx={{ fontSize: '16px', mr: 1 }} />
          Create New Playlist
        </CreateNewMenuItem>

        <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)', my: 1 }} />

        {onToggleFavorite && (
          <StyledMenuItem onClick={() => { onToggleFavorite(); onClose(); }}>
            <ListItemIcon>
              {isFavorite ? <Favorite /> : <FavoriteBorder />}
            </ListItemIcon>
            <ListItemText>
              {isFavorite ? 'Remove from Favourites' : 'Add to Favourites'}
            </ListItemText>
          </StyledMenuItem>
        )}

        {onShowInfo && (
          <StyledMenuItem onClick={() => { onShowInfo(); onClose(); }}>
            <ListItemIcon>
              <Info />
            </ListItemIcon>
            <ListItemText>Track Info</ListItemText>
          </StyledMenuItem>
        )}
      </StyledMenu>

      <CreatePlaylistDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onPlaylistCreated={handlePlaylistCreated}
        initialTrackIds={trackId ? [trackId] : undefined}
      />
    </>
  );
};

export default TrackContextMenu;
