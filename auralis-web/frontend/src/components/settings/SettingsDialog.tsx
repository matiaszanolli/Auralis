import React, { useState } from 'react';
import {
  Skeleton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import { Button } from '@/design-system';
import { UserSettings } from '../../services/settingsService';
import { StyledDialog } from '../library/Styles/Dialog.styles';
import { SettingsDialogContent as StyledContent } from './SettingsDialog.styles';
import { SettingsTabNav } from './SettingsTabNav';
import SettingsDialogHeader from './SettingsDialogHeader';
import SettingsDialogContentComponent from './SettingsDialogContent';
import SettingsDialogFooter from './SettingsDialogFooter';
import { useSettingsDialog } from './useSettingsDialog';
import { useScanProgress } from '../../hooks/library/useScanProgress';

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
    loading,
    isSaving,
    removeConfirmFolder,
    handleSettingChange,
    handleSave,
    handleReset,
    handleAddScanFolder,
    handleRemoveScanFolder,
    handleConfirmRemove,
    handleCancelRemove,
    handleScanNow,
    getValue,
  } = useSettingsDialog({ open, onSettingsChange });

  const { isScanning } = useScanProgress();

  const handleScanNowClick = () => {
    const folders: string[] = getValue('scan_folders') ?? [];
    handleScanNow(folders);
  };

  return (
    <>
      <StyledDialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <SettingsDialogHeader onClose={onClose} />

        <SettingsTabNav
          activeTab={activeTab}
          onTabChange={(_e, v) => setActiveTab(v)}
          isScanning={isScanning}
        />

        {loading ? (
          <StyledContent>
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton
                key={i}
                variant="rectangular"
                height={48}
                sx={{ mb: 2, borderRadius: 1 }}
              />
            ))}
          </StyledContent>
        ) : (
          <SettingsDialogContentComponent
            activeTab={activeTab}
            getValue={getValue}
            onSettingChange={handleSettingChange}
            onAddFolder={handleAddScanFolder}
            onRemoveFolder={handleRemoveScanFolder}
            onScanNow={handleScanNowClick}
          />
        )}

        <SettingsDialogFooter
          onReset={handleReset}
          onCancel={onClose}
          onSave={() => handleSave(onClose)}
          isSaving={isSaving}
        />
      </StyledDialog>

      {/* Folder removal confirmation dialog */}
      <Dialog open={removeConfirmFolder !== null} onClose={handleCancelRemove} maxWidth="xs">
        <DialogTitle>Remove folder?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            <strong>{removeConfirmFolder}</strong>
            <br />
            Files will remain on disk. Tracks from this folder will be removed from the library.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button variant="ghost" onClick={handleCancelRemove}>Cancel</Button>
          <Button variant="danger" onClick={handleConfirmRemove}>Remove</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default SettingsDialog;
