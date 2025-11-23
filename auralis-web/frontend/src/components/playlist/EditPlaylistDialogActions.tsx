import React from 'react';
import { DialogActions } from '@mui/material';
import { CancelButton, GradientButton } from '../library/Styles/Button.styles';

interface EditPlaylistDialogActionsProps {
  loading: boolean;
  nameEmpty: boolean;
  onSave: () => void;
  onCancel: () => void;
}

/**
 * EditPlaylistDialogActions - Dialog action buttons (Cancel and Save Changes)
 *
 * Features:
 * - Save button disabled when name is empty or loading
 * - Both buttons disabled while loading
 * - Loading state shows "Saving..." text
 */
export const EditPlaylistDialogActions: React.FC<EditPlaylistDialogActionsProps> = ({
  loading,
  nameEmpty,
  onSave,
  onCancel,
}) => {
  return (
    <DialogActions sx={{ p: 2, pt: 1 }}>
      <CancelButton onClick={onCancel} disabled={loading}>
        Cancel
      </CancelButton>
      <GradientButton onClick={onSave} disabled={nameEmpty || loading}>
        {loading ? 'Saving...' : 'Save Changes'}
      </GradientButton>
    </DialogActions>
  );
};

export default EditPlaylistDialogActions;
