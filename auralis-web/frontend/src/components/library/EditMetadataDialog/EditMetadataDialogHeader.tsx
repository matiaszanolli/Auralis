import React from 'react';
import { DialogTitle, Typography, CircularProgress } from '@mui/material';
import { DialogHeaderBox, DialogTitleStyled } from './EditMetadataDialog.styles';

interface EditMetadataDialogHeaderProps {
  loading: boolean;
}

/**
 * EditMetadataDialogHeader - Dialog header with title and loading indicator
 *
 * Displays:
 * - "Edit Metadata" title
 * - Loading spinner when fetching metadata
 */
export const EditMetadataDialogHeader: React.FC<EditMetadataDialogHeaderProps> = ({ loading }) => {
  return (
    <DialogTitle sx={DialogTitleStyled}>
      <DialogHeaderBox>
        <Typography variant="h6">Edit Metadata</Typography>
        {loading && <CircularProgress size={24} />}
      </DialogHeaderBox>
    </DialogTitle>
  );
};

export default EditMetadataDialogHeader;
