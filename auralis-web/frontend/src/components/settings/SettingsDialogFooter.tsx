import React from 'react';

import { RestartAlt as ResetIcon } from '@mui/icons-material';
import { SettingsDialogActions, SaveButtonGradient, FlexSpacer } from './SettingsDialog.styles';
import { Button } from '@/design-system';

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
      <Button onClick={onReset} startIcon={<ResetIcon />} variant="danger">
        Reset to Defaults
      </Button>
      <FlexSpacer />
      <Button onClick={onCancel} variant="ghost">
        Cancel
      </Button>
      <Button onClick={onSave} variant="primary" sx={SaveButtonGradient}>
        Save Changes
      </Button>
    </SettingsDialogActions>
  );
};

export default SettingsDialogFooter;
