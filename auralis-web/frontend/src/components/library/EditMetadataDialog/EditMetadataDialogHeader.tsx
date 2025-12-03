import React from 'react';
import { Typography } from '@mui/material';
import { CircularProgress } from '@/design-system';
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
    <DialogTitleStyled component="div">
      <DialogHeaderBox>
        <Typography variant="h6">Edit Metadata</Typography>
        {loading && <CircularProgress size={24} />}
      </DialogHeaderBox>
    </DialogTitleStyled>
  );
};

export default EditMetadataDialogHeader;
