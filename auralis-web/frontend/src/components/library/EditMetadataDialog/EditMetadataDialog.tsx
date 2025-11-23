/**
 * EditMetadataDialog Component
 *
 * Dialog for editing track metadata with form state management,
 * error/success feedback, and save functionality.
 *
 * Modular structure:
 * - EditMetadataDialogHeader - Dialog title and loading state
 * - MetadataDialogAlerts - Error and success messages
 * - MetadataFormFields - Form field rendering
 * - useMetadataForm - Form state and operations
 *
 * Features:
 * - Load and display current track metadata
 * - Edit metadata fields (title, artist, album, etc.)
 * - Save metadata with success/error feedback
 * - Loading states during operations
 */

import React from 'react';
import { Dialog, DialogContent, CircularProgress } from '@mui/material';
import { Save as SaveIcon, Close as CloseIcon } from '@mui/icons-material';
import { MetadataFormFields } from './MetadataFormFields';
import { EditMetadataDialogHeader } from './EditMetadataDialogHeader';
import { MetadataDialogAlerts } from './MetadataDialogAlerts';
import {
  MetadataDialogActions,
  SaveButton,
  CancelButtonForDialog,
  DialogPaperProps,
} from '../Styles/Dialog.styles';
import { useMetadataForm, MetadataFields } from './useMetadataForm';

export interface EditMetadataDialogProps {
  open: boolean;
  trackId: number;
  currentMetadata?: MetadataFields;
  onClose: () => void;
  onSave?: (trackId: number, metadata: MetadataFields) => void;
}

export const EditMetadataDialog: React.FC<EditMetadataDialogProps> = ({
  open,
  trackId,
  currentMetadata,
  onClose,
  onSave,
}) => {
  const { metadata, loading, saving, error, success, updateField, saveMetadata, setSuccess } =
    useMetadataForm(trackId, currentMetadata, onSave);

  const handleSave = async () => {
    const result = await saveMetadata();
    if (result) {
      // Close dialog after a brief delay to show success message
      setTimeout(() => {
        onClose();
      }, 1000);
    }
  };

  const handleClose = () => {
    if (!saving) {
      setSuccess(false);
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth PaperProps={DialogPaperProps}>
      <EditMetadataDialogHeader loading={loading} />

      <DialogContent sx={{ mt: 2 }}>
        <MetadataDialogAlerts error={error} success={success} />
        <MetadataFormFields metadata={metadata} loading={loading} onChange={updateField} />
      </DialogContent>

      <MetadataDialogActions>
        <CancelButtonForDialog onClick={handleClose} disabled={saving} startIcon={<CloseIcon />}>
          Cancel
        </CancelButtonForDialog>
        <SaveButton
          onClick={handleSave}
          disabled={saving || loading}
          variant="contained"
          startIcon={saving ? <CircularProgress size={16} /> : <SaveIcon />}
        >
          {saving ? 'Saving...' : 'Save'}
        </SaveButton>
      </MetadataDialogActions>
    </Dialog>
  );
};

export default EditMetadataDialog;
