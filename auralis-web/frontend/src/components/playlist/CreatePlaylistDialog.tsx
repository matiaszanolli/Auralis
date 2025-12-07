import React from 'react';
import { DialogContent } from '@mui/material';
import * as playlistService from '../../services/playlistService';
import { StyledDialog, StyledDialogTitle } from '../library/Styles/Dialog.styles';
import { useCreatePlaylistForm } from './useCreatePlaylistForm';
import { CreatePlaylistFormFields } from './CreatePlaylistFormFields';
import { CreatePlaylistDialogActions } from './CreatePlaylistDialogActions';

interface CreatePlaylistDialogProps {
  open: boolean;
  onClose: () => void;
  onPlaylistCreated?: (playlist: playlistService.Playlist) => void;
  initialTrackIds?: number[];
}

/**
 * CreatePlaylistDialog - Dialog for creating new playlists
 *
 * Features:
 * - Create playlist with name and optional description
 * - Display number of initial tracks to be added
 * - Keyboard shortcut support (Enter to create)
 * - Loading state during creation
 * - Form validation (playlist name required)
 * - Auto-reset form on successful creation
 *
 * @example
 * <CreatePlaylistDialog
 *   open={dialogOpen}
 *   onClose={() => setDialogOpen(false)}
 *   onPlaylistCreated={onRefresh}
 *   initialTrackIds={selectedTrackIds}
 * />
 */
export const CreatePlaylistDialog: React.FC<CreatePlaylistDialogProps> = ({
  open,
  onClose,
  onPlaylistCreated,
  initialTrackIds,
}) => {
  const {
    name,
    setName,
    description,
    setDescription,
    loading,
    handleCreate,
    handleClose,
    handleKeyPress,
  } = useCreatePlaylistForm({
    initialTrackIds,
    onPlaylistCreated,
    onClose,
  });

  return (
    <StyledDialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <StyledDialogTitle>Create New Playlist</StyledDialogTitle>
      <DialogContent>
        <CreatePlaylistFormFields
          name={name}
          onNameChange={setName}
          description={description}
          onDescriptionChange={setDescription}
          loading={loading}
          onKeyDown={handleKeyPress}
          initialTrackIds={initialTrackIds}
        />
      </DialogContent>
      <CreatePlaylistDialogActions
        loading={loading}
        nameEmpty={!name.trim()}
        onCreate={handleCreate}
        onCancel={handleClose}
      />
    </StyledDialog>
  );
};

export default CreatePlaylistDialog;
