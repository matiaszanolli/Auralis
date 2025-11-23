import React from 'react';
import { Button } from '@mui/material';
import { RestartAlt as ResetIcon } from '@mui/icons-material';
import { SettingsDialogActions, SaveButtonGradient, FlexSpacer } from './SettingsDialog.styles';

interface SettingsDialogFooterProps {
  onReset: () => void;
  onCancel: () => void;
  onSave: () => void;
}

/**
 * SettingsDialogFooter - Dialog footer with action buttons
 *
 * Displays reset, cancel, and save buttons.
 */
export const SettingsDialogFooter: React.FC<SettingsDialogFooterProps> = ({
  onReset,
  onCancel,
  onSave,
}) => {
  return (
    <SettingsDialogActions>
      <Button onClick={onReset} startIcon={<ResetIcon />} color="error">
        Reset to Defaults
      </Button>
      <FlexSpacer />
      <Button onClick={onCancel} color="inherit">
        Cancel
      </Button>
      <Button onClick={onSave} variant="contained" sx={SaveButtonGradient}>
        Save Changes
      </Button>
    </SettingsDialogActions>
  );
};

export default SettingsDialogFooter;
