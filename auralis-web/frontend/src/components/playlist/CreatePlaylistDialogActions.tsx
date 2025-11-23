import React from 'react';
import { DialogActions } from '@mui/material';
import { CancelButton, GradientButton } from '../library/Styles/Button.styles';

interface CreatePlaylistDialogActionsProps {
  loading: boolean;
  nameEmpty: boolean;
  onCreate: () => void;
  onCancel: () => void;
}

/**
 * CreatePlaylistDialogActions - Dialog action buttons (Cancel and Create Playlist)
 *
 * Features:
 * - Create button disabled when name is empty or loading
 * - Both buttons disabled while loading
 * - Loading state shows "Creating..." text
 */
export const CreatePlaylistDialogActions: React.FC<CreatePlaylistDialogActionsProps> = ({
  loading,
  nameEmpty,
  onCreate,
  onCancel,
}) => {
  return (
    <DialogActions sx={{ p: 2, pt: 1 }}>
      <CancelButton onClick={onCancel} disabled={loading}>
        Cancel
      </CancelButton>
      <GradientButton onClick={onCreate} disabled={nameEmpty || loading}>
        {loading ? 'Creating...' : 'Create Playlist'}
      </GradientButton>
    </DialogActions>
  );
};

export default CreatePlaylistDialogActions;
