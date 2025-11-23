import React from 'react';
import { Alert } from '@mui/material';
import { AlertContainer } from './EditMetadataDialog.styles';

interface MetadataDialogAlertsProps {
  error?: string;
  success?: boolean;
}

/**
 * MetadataDialogAlerts - Displays error and success alerts for metadata dialog
 *
 * Displays:
 * - Error alert if an error occurs during save
 * - Success alert after successful metadata save
 */
export const MetadataDialogAlerts: React.FC<MetadataDialogAlertsProps> = ({ error, success }) => {
  return (
    <>
      {error && (
        <AlertContainer>
          <Alert severity="error">{error}</Alert>
        </AlertContainer>
      )}
      {success && (
        <AlertContainer>
          <Alert severity="success">Metadata saved successfully!</Alert>
        </AlertContainer>
      )}
    </>
  );
};

export default MetadataDialogAlerts;
