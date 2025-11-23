/**
 * EditMetadataDialog Component (Refactored)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Dialog for editing track metadata
 * Organized modular structure:
 * - MetadataFormFields - Form field rendering
 * - useMetadataForm - Form state and operations
 * - Styled components for dialog layout
 */

import React, { useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material';
import { Save as SaveIcon, Close as CloseIcon } from '@mui/icons-material';
import { MetadataFormFields } from './MetadataFormFields';
import {
  MetadataDialogActions,
  SaveButton,
  CancelButtonForDialog,
} from '../Dialog.styles';
import { useMetadataForm, MetadataFields } from './useMetadataForm';
import { auroraOpacity } from '../../library/Color.styles';
import { tokens } from '@/design-system/tokens';

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
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#1a1f3a',
          backgroundImage: 'linear-gradient(135deg, #1a1f3a 0%, #0f1228 100%)',
        },
      }}
    >
      {/* Dialog Header */}
      <DialogTitle sx={{ color: tokens.colors.text.primary, borderBottom: `1px solid ${auroraOpacity.ultraLight}` }}>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Typography variant="h6">Edit Metadata</Typography>
          {loading && <CircularProgress size={24} />}
        </Box>
      </DialogTitle>

      {/* Dialog Content */}
      <DialogContent sx={{ mt: 2 }}>
        {/* Error Alert */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Success Alert */}
        {success && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Metadata saved successfully!
          </Alert>
        )}

        {/* Metadata Form Fields */}
        <MetadataFormFields metadata={metadata} loading={loading} onChange={updateField} />
      </DialogContent>

      {/* Dialog Actions */}
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
