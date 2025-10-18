import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  TextField,
  IconButton,
  styled,
} from '@mui/material';
import {
  Close,
  PlaylistAdd,
  Add,
  Check,
  FolderMusic,
} from '@mui/icons-material';
import { colors, gradients } from '../../theme/auralisTheme';
import GradientButton from '../shared/GradientButton';

interface Playlist {
  id: string;
  name: string;
  trackCount?: number;
}

interface AddToPlaylistModalProps {
  open: boolean;
  trackTitle?: string;
  onClose: () => void;
  onAddToPlaylist: (playlistId: string) => void;
  onCreatePlaylist?: (name: string) => void;
  playlists?: Playlist[];
}

const StyledDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    background: colors.background.secondary,
    backgroundImage: 'none',
    borderRadius: '16px',
    border: `1px solid rgba(102, 126, 234, 0.2)`,
    boxShadow: '0 12px 48px rgba(0, 0, 0, 0.6)',
    minWidth: '400px',
    maxWidth: '500px',
  },
}));

const StyledListItemButton = styled(ListItemButton)({
  borderRadius: '8px',
  marginBottom: '4px',
  transition: 'all 0.2s ease',
  border: '1px solid transparent',

  '&:hover': {
    background: 'rgba(102, 126, 234, 0.12)',
    border: '1px solid rgba(102, 126, 234, 0.3)',
    transform: 'translateX(4px)',
  },
});

const NewPlaylistInput = styled(TextField)({
  '& .MuiOutlinedInput-root': {
    borderRadius: '8px',
    background: colors.background.surface,

    '& fieldset': {
      borderColor: 'rgba(102, 126, 234, 0.2)',
    },

    '&:hover fieldset': {
      borderColor: 'rgba(102, 126, 234, 0.4)',
    },

    '&.Mui-focused fieldset': {
      borderColor: '#667eea',
    },
  },

  '& .MuiOutlinedInput-input': {
    color: colors.text.primary,
  },
});

export const AddToPlaylistModal: React.FC<AddToPlaylistModalProps> = ({
  open,
  trackTitle,
  onClose,
  onAddToPlaylist,
  onCreatePlaylist,
  playlists = [],
}) => {
  const [isCreating, setIsCreating] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState('');

  const handleCreatePlaylist = () => {
    if (newPlaylistName.trim() && onCreatePlaylist) {
      onCreatePlaylist(newPlaylistName.trim());
      setNewPlaylistName('');
      setIsCreating(false);
    }
  };

  const handleAddToPlaylist = (playlistId: string) => {
    onAddToPlaylist(playlistId);
    onClose();
  };

  return (
    <StyledDialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pr: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PlaylistAdd sx={{ color: '#667eea', fontSize: 24 }} />
            <Typography variant="h6" sx={{ fontWeight: 600, color: colors.text.primary }}>
              Add to Playlist
            </Typography>
          </Box>
          <IconButton
            onClick={onClose}
            size="small"
            sx={{
              color: colors.text.secondary,
              '&:hover': {
                color: colors.text.primary,
                background: 'rgba(102, 126, 234, 0.1)',
              },
            }}
          >
            <Close />
          </IconButton>
        </Box>
        {trackTitle && (
          <Typography variant="body2" sx={{ color: colors.text.secondary, mt: 1 }}>
            {trackTitle}
          </Typography>
        )}
      </DialogTitle>

      <DialogContent>
        {/* Create New Playlist Section */}
        <Box sx={{ mb: 3 }}>
          {isCreating ? (
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
              <NewPlaylistInput
                fullWidth
                size="small"
                placeholder="Playlist name"
                value={newPlaylistName}
                onChange={(e) => setNewPlaylistName(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleCreatePlaylist();
                  }
                }}
                autoFocus
              />
              <GradientButton
                onClick={handleCreatePlaylist}
                disabled={!newPlaylistName.trim()}
                sx={{ minWidth: '80px' }}
              >
                <Check />
              </GradientButton>
              <IconButton
                onClick={() => {
                  setIsCreating(false);
                  setNewPlaylistName('');
                }}
                sx={{ color: colors.text.secondary }}
              >
                <Close />
              </IconButton>
            </Box>
          ) : (
            <GradientButton
              fullWidth
              onClick={() => setIsCreating(true)}
              sx={{ justifyContent: 'flex-start', gap: 1 }}
            >
              <Add />
              Create New Playlist
            </GradientButton>
          )}
        </Box>

        {/* Existing Playlists */}
        {playlists.length > 0 ? (
          <>
            <Typography
              variant="caption"
              sx={{
                color: colors.text.secondary,
                textTransform: 'uppercase',
                letterSpacing: '1px',
                fontWeight: 600,
                mb: 1,
                display: 'block',
              }}
            >
              Your Playlists
            </Typography>
            <List sx={{ maxHeight: '300px', overflowY: 'auto' }}>
              {playlists.map((playlist) => (
                <StyledListItemButton
                  key={playlist.id}
                  onClick={() => handleAddToPlaylist(playlist.id)}
                >
                  <ListItemIcon sx={{ minWidth: 40 }}>
                    <FolderMusic sx={{ color: '#667eea', fontSize: 20 }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={playlist.name}
                    secondary={
                      playlist.trackCount !== undefined
                        ? `${playlist.trackCount} tracks`
                        : undefined
                    }
                    primaryTypographyProps={{
                      fontSize: 14,
                      fontWeight: 500,
                      color: colors.text.primary,
                    }}
                    secondaryTypographyProps={{
                      fontSize: 12,
                      color: colors.text.secondary,
                    }}
                  />
                </StyledListItemButton>
              ))}
            </List>
          </>
        ) : (
          <Box
            sx={{
              textAlign: 'center',
              py: 4,
              color: colors.text.secondary,
            }}
          >
            <FolderMusic sx={{ fontSize: 48, mb: 2, opacity: 0.5 }} />
            <Typography variant="body2">No playlists yet</Typography>
            <Typography variant="caption" sx={{ opacity: 0.7 }}>
              Create your first playlist above
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 3 }}>
        <GradientButton onClick={onClose} sx={{ minWidth: '100px' }}>
          Cancel
        </GradientButton>
      </DialogActions>
    </StyledDialog>
  );
};

export default AddToPlaylistModal;
