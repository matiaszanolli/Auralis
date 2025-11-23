import React, { useState } from 'react';
import { UserSettings } from '../../services/settingsService';
import { StyledDialog } from '../library/Styles/Dialog.styles';
import { SettingsTabNav } from './SettingsTabNav';
import SettingsDialogHeader from './SettingsDialogHeader';
import SettingsDialogContentComponent from './SettingsDialogContent';
import SettingsDialogFooter from './SettingsDialogFooter';
import { useSettingsDialog } from './useSettingsDialog';

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  onSettingsChange?: (settings: UserSettings) => void;
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({
  open,
  onClose,
  onSettingsChange,
}) => {
  const [activeTab, setActiveTab] = useState(0);

  const {
    settings,
    handleSettingChange,
    handleSave,
    handleReset,
    handleAddScanFolder,
    handleRemoveScanFolder,
    handleRescanFolder,
    getValue,
  } = useSettingsDialog({ open, onSettingsChange });

  if (!settings) {
    return null;
  }

  return (
    <StyledDialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <SettingsDialogHeader onClose={onClose} />

      <SettingsTabNav activeTab={activeTab} onTabChange={(e, v) => setActiveTab(v)} />

      <SettingsDialogContentComponent
        activeTab={activeTab}
        getValue={getValue}
        onSettingChange={handleSettingChange}
        onAddFolder={handleAddScanFolder}
        onRemoveFolder={handleRemoveScanFolder}
        onRescanFolder={handleRescanFolder}
      />

      <SettingsDialogFooter
        onReset={handleReset}
        onCancel={onClose}
        onSave={() => handleSave(onClose)}
      />
    </StyledDialog>
  );
};

export default SettingsDialog;
