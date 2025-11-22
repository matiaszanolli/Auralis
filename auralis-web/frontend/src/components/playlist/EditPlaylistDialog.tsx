import React, { useState, useEffect } from 'react';
import {
  DialogContent,
  DialogActions,
  Box,
} from '@mui/material';
import { colors } from '../../theme/auralisTheme';
import { useToast } from '../shared/Toast';
import * as playlistService from '../../services/playlistService';
import { StyledDialog, StyledDialogTitle } from '../library/Dialog.styles';
import { StyledTextField } from '../library/FormFields.styles';
import { GradientButton, CancelButton } from '../library/Button.styles';
import { auroraOpacity } from '../library/Color.styles';

interface EditPlaylistDialogProps {
  open: boolean;
  onClose: () => void;
  playlist: playlistService.Playlist | null;
  onPlaylistUpdated?: () => void;
}

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
              background: auroraOpacity.veryLight,
              borderRadius: '8px',
              border: `1px solid ${auroraOpacity.standard}`,
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
        <GradientButton onClick={handleSave} disabled={!name.trim() || loading}>
          {loading ? 'Saving...' : 'Save Changes'}
        </GradientButton>
      </DialogActions>
    </StyledDialog>
  );
};

export default EditPlaylistDialog;
