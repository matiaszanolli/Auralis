import React from 'react';

import { RestartAlt as ResetIcon } from '@mui/icons-material';
import { CircularProgress } from '@mui/material';
import { SettingsDialogActions, SaveButtonGradient, FlexSpacer } from './SettingsDialog.styles';
import { Button } from '@/design-system';

interface SettingsDialogFooterProps {
  onReset: () => void;
  onCancel: () => void;
  onSave: () => void;
  isSaving?: boolean;
}

/**
 * SettingsDialogFooter - Dialog footer with action buttons
 *
 * Shows a saving spinner while the save request is in flight.
 */
export const SettingsDialogFooter: React.FC<SettingsDialogFooterProps> = ({
  onReset,
  onCancel,
  onSave,
  isSaving = false,
}) => {
  return (
    <SettingsDialogActions>
      <Button onClick={onReset} startIcon={<ResetIcon />} variant="danger" disabled={isSaving}>
        Reset to Defaults
      </Button>
      <FlexSpacer />
      <Button onClick={onCancel} variant="ghost" disabled={isSaving}>
        Cancel
      </Button>
      <Button
        onClick={onSave}
        variant="primary"
        sx={SaveButtonGradient}
        disabled={isSaving}
        startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : undefined}
      >
        {isSaving ? 'Saving…' : 'Save Changes'}
      </Button>
    </SettingsDialogActions>
  );
};

export default SettingsDialogFooter;
