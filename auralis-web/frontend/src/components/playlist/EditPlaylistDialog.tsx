import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  styled,
} from '@mui/material';
import { colors } from '../../theme/auralisTheme';
import { useToast } from '../shared/Toast';
import * as playlistService from '../../services/playlistService';

interface EditPlaylistDialogProps {
  open: boolean;
  onClose: () => void;
  playlist: playlistService.Playlist | null;
  onPlaylistUpdated?: () => void;
}

const StyledDialog = styled(Dialog)({
  '& .MuiDialog-paper': {
    background: colors.background.secondary,
    border: `1px solid rgba(102, 126, 234, 0.2)`,
    borderRadius: '12px',
    minWidth: '400px',
  },
});

const StyledDialogTitle = styled(DialogTitle)({
  color: colors.text.primary,
  fontSize: '20px',
  fontWeight: 600,
  borderBottom: `1px solid rgba(102, 126, 234, 0.1)`,
});

const StyledTextField = styled(TextField)({
  '& .MuiInputBase-root': {
    color: colors.text.primary,
    background: colors.background.primary,
    borderRadius: '8px',
  },
  '& .MuiInputLabel-root': {
    color: colors.text.secondary,
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: 'rgba(102, 126, 234, 0.3)',
  },
  '& .MuiInputBase-root:hover .MuiOutlinedInput-notchedOutline': {
    borderColor: 'rgba(102, 126, 234, 0.5)',
  },
  '& .MuiInputBase-root.Mui-focused .MuiOutlinedInput-notchedOutline': {
    borderColor: '#667eea',
  },
});

const SaveButton = styled(Button)({
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  color: '#ffffff',
  textTransform: 'none',
  fontWeight: 600,
  padding: '10px 24px',
  borderRadius: '8px',
  '&:hover': {
    background: 'linear-gradient(135deg, #7c8ef0 0%, #8b5bb5 100%)',
    transform: 'translateY(-1px)',
    boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)',
  },
  '&:disabled': {
    background: 'rgba(102, 126, 234, 0.3)',
    color: 'rgba(255, 255, 255, 0.5)',
  },
  transition: 'all 0.2s ease',
});

const CancelButton = styled(Button)({
  color: colors.text.secondary,
  textTransform: 'none',
  '&:hover': {
    background: 'rgba(102, 126, 234, 0.1)',
  },
});

export const EditPlaylistDialog: React.FC<EditPlaylistDialogProps> = ({
  open,
  onClose,
  playlist,
  onPlaylistUpdated,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const { success, error } = useToast();

  // Update form when playlist changes
  useEffect(() => {
    if (playlist) {
      setName(playlist.name);
      setDescription(playlist.description || '');
    }
  }, [playlist]);

  const handleSave = async () => {
    if (!playlist) return;

    if (!name.trim()) {
      error('Please enter a playlist name');
      return;
    }

    setLoading(true);
    try {
      await playlistService.updatePlaylist(playlist.id, {
        name: name.trim(),
        description: description.trim(),
      });

      success(`Playlist "${name}" updated successfully`);

      if (onPlaylistUpdated) {
        onPlaylistUpdated();
      }

      onClose();
    } catch (err) {
      error(`Failed to update playlist: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && name.trim() && !loading) {
      handleSave();
    }
  };

  if (!playlist) return null;

  return (
    <StyledDialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <StyledDialogTitle>Edit Playlist</StyledDialogTitle>
      <DialogContent>
        <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <StyledTextField
            autoFocus
            label="Playlist Name"
            fullWidth
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={loading}
            placeholder="Enter playlist name"
          />
          <StyledTextField
            label="Description (Optional)"
            fullWidth
            multiline
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={loading}
            placeholder="Add a description for your playlist"
          />
          <Box
            sx={{
              p: 2,
              background: 'rgba(102, 126, 234, 0.1)',
              borderRadius: '8px',
              border: `1px solid rgba(102, 126, 234, 0.2)`,
            }}
          >
            <Box sx={{ color: colors.text.secondary, fontSize: '14px' }}>
              {playlist.track_count} track{playlist.track_count !== 1 ? 's' : ''} in this playlist
            </Box>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2, pt: 1 }}>
        <CancelButton onClick={handleClose} disabled={loading}>
          Cancel
        </CancelButton>
        <SaveButton onClick={handleSave} disabled={!name.trim() || loading}>
          {loading ? 'Saving...' : 'Save Changes'}
        </SaveButton>
      </DialogActions>
    </StyledDialog>
  );
};

export default EditPlaylistDialog;
