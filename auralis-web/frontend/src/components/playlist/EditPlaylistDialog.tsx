import React from 'react';
import { DialogContent } from '@mui/material';
import * as playlistService from '../../services/playlistService';
import { StyledDialog, StyledDialogTitle } from '../library/Styles/Dialog.styles';
import { useEditPlaylistForm } from './useEditPlaylistForm';
import { PlaylistFormFields } from './PlaylistFormFields';
import { PlaylistTrackCount } from './PlaylistTrackCount';
import { EditPlaylistDialogActions } from './EditPlaylistDialogActions';

interface EditPlaylistDialogProps {
  open: boolean;
  onClose: () => void;
  playlist: playlistService.Playlist | null;
  onPlaylistUpdated?: () => void;
}

/**
 * EditPlaylistDialog - Dialog for editing playlist name and description
 *
 * Features:
 * - Edit playlist name and description
 * - Display track count in playlist
 * - Keyboard shortcut support (Enter to save)
 * - Loading state during save
 * - Form validation (playlist name required)
 *
 * @example
 * <EditPlaylistDialog
 *   open={dialogOpen}
 *   onClose={() => setDialogOpen(false)}
 *   playlist={selectedPlaylist}
 *   onPlaylistUpdated={onRefresh}
 * />
 */
export const EditPlaylistDialog: React.FC<EditPlaylistDialogProps> = ({
  open,
  onClose,
  playlist,
  onPlaylistUpdated,
}) => {
  const {
    name,
    setName,
    description,
    setDescription,
    loading,
    handleSave,
    handleClose,
    handleKeyPress,
  } = useEditPlaylistForm({
    playlist,
    onPlaylistUpdated,
    onClose,
  });

  if (!playlist) return null;

  return (
    <StyledDialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <StyledDialogTitle>Edit Playlist</StyledDialogTitle>
      <DialogContent>
        <PlaylistFormFields
          name={name}
          onNameChange={setName}
          description={description}
          onDescriptionChange={setDescription}
          loading={loading}
          onKeyPress={handleKeyPress}
        />
        <PlaylistTrackCount trackCount={playlist.track_count} />
      </DialogContent>
      <EditPlaylistDialogActions
        loading={loading}
        nameEmpty={!name.trim()}
        onSave={handleSave}
        onCancel={handleClose}
      />
    </StyledDialog>
  );
};

export default EditPlaylistDialog;
