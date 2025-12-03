import React from 'react';
import { Alert } from '@/design-system';
import { AlertContainer } from './EditMetadataDialog.styles';

interface MetadataDialogAlertsProps {
  error?: string | null;
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
          <Alert variant="error">{error}</Alert>
        </AlertContainer>
      )}
      {success && (
        <AlertContainer>
          <Alert variant="success">Metadata saved successfully!</Alert>
        </AlertContainer>
      )}
    </>
  );
};

export default MetadataDialogAlerts;
