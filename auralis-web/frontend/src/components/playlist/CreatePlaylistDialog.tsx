import React, { useState } from 'react';
import {
  DialogContent,
  DialogActions,
  Box,
} from '@mui/material';
import { useToast } from '../shared/Toast';
import * as playlistService from '../../services/playlistService';
import { StyledDialog, StyledDialogTitle } from '../library/Dialog.styles';
import { StyledTextField } from '../library/FormFields.styles';
import { GradientButton, CancelButton } from '../library/Button.styles';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

interface CreatePlaylistDialogProps {
  open: boolean;
  onClose: () => void;
  onPlaylistCreated?: (playlist: playlistService.Playlist) => void;
  initialTrackIds?: number[];
}

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
                background: auroraOpacity.veryLight,
                borderRadius: '8px',
                border: `1px solid ${auroraOpacity.standard}`,
              }}
            >
              <Box sx={{ color: tokens.colors.text.secondary, fontSize: '14px' }}>
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
        <GradientButton onClick={handleCreate} disabled={!name.trim() || loading}>
          {loading ? 'Creating...' : 'Create Playlist'}
        </GradientButton>
      </DialogActions>
    </StyledDialog>
  );
};

export default CreatePlaylistDialog;
