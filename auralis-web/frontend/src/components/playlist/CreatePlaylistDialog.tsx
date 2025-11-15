import React, { useState } from 'react';
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

interface CreatePlaylistDialogProps {
  open: boolean;
  onClose: () => void;
  onPlaylistCreated?: (playlist: playlistService.Playlist) => void;
  initialTrackIds?: number[];
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

const CreateButton = styled(Button)({
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

export const CreatePlaylistDialog: React.FC<CreatePlaylistDialogProps> = ({
  open,
  onClose,
  onPlaylistCreated,
  initialTrackIds,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const { success, error } = useToast();

  const handleCreate = async () => {
    if (!name.trim()) {
      error('Please enter a playlist name');
      return;
    }

    setLoading(true);
    try {
      const playlist = await playlistService.createPlaylist({
        name: name.trim(),
        description: description.trim(),
        track_ids: initialTrackIds,
      });

      success(`Playlist "${name}" created successfully`);

      if (onPlaylistCreated) {
        onPlaylistCreated(playlist);
      }

      // Reset form
      setName('');
      setDescription('');
      onClose();
    } catch (err) {
      error(`Failed to create playlist: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setName('');
      setDescription('');
      onClose();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && name.trim() && !loading) {
      handleCreate();
    }
  };

  return (
    <StyledDialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <StyledDialogTitle>Create New Playlist</StyledDialogTitle>
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
          {initialTrackIds && initialTrackIds.length > 0 && (
            <Box
              sx={{
                p: 2,
                background: 'rgba(102, 126, 234, 0.1)',
                borderRadius: '8px',
                border: `1px solid rgba(102, 126, 234, 0.2)`,
              }}
            >
              <Box sx={{ color: colors.text.secondary, fontSize: '14px' }}>
                {initialTrackIds.length} track{initialTrackIds.length !== 1 ? 's' : ''} will be added to this playlist
              </Box>
            </Box>
          )}
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2, pt: 1 }}>
        <CancelButton onClick={handleClose} disabled={loading}>
          Cancel
        </CancelButton>
        <CreateButton onClick={handleCreate} disabled={!name.trim() || loading}>
          {loading ? 'Creating...' : 'Create Playlist'}
        </CreateButton>
      </DialogActions>
    </StyledDialog>
  );
};

export default CreatePlaylistDialog;
