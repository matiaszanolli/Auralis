import { useState, useEffect, useCallback } from 'react';
import { settingsService, UserSettings, SettingsUpdate } from '../../services/settingsService';

export interface UseSettingsDialogProps {
  open: boolean;
  onSettingsChange?: (settings: UserSettings) => void;
}

/**
 * useSettingsDialog - Manages settings dialog state and operations
 *
 * Handles:
 * - Loading settings
 * - Tracking pending changes
 * - Saving settings (with isSaving indicator)
 * - Resetting to defaults
 * - Folder operations (add, remove with confirm state)
 * - Triggering an immediate library scan
 */
export const useSettingsDialog = ({ open, onSettingsChange }: UseSettingsDialogProps) => {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingChanges, setPendingChanges] = useState<SettingsUpdate>({});
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Folder pending removal — non-null means confirm dialog is open
  const [removeConfirmFolder, setRemoveConfirmFolder] = useState<string | null>(null);

  // Load settings when dialog opens
  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open]);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await settingsService.getSettings();
      setSettings(data);
    } catch (err) {
      console.error('Failed to load settings:', err);
      setError('Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSettingChange = useCallback((key: keyof SettingsUpdate, value: any) => {
    setPendingChanges((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSave = useCallback(
    async (onClose: () => void) => {
      if (Object.keys(pendingChanges).length === 0) {
        onClose();
        return;
      }

      setIsSaving(true);
      setError(null);
      try {
        const result = await settingsService.updateSettings(pendingChanges);
        setSettings(result.settings);
        setPendingChanges({});
        onSettingsChange?.(result.settings);
        onClose();
      } catch (err) {
        console.error('Failed to save settings:', err);
        setError('Failed to save settings');
      } finally {
        setIsSaving(false);
      }
    },
    [pendingChanges, onSettingsChange]
  );

  const handleReset = useCallback(async () => {
    setError(null);
    try {
      const result = await settingsService.resetSettings();
      setSettings(result.settings);
      setPendingChanges({});
      onSettingsChange?.(result.settings);
    } catch (err) {
      console.error('Failed to reset settings:', err);
      setError('Failed to reset settings');
    }
  }, [onSettingsChange]);

  const handleAddScanFolder = useCallback(async () => {
    let folder: string | null = null;

    // Use Electron folder picker if available
    if ((window as any).electronAPI && (window as any).electronAPI.selectFolder) {
      try {
        folder = await (window as any).electronAPI.selectFolder();
      } catch (err) {
        console.error('Electron folder picker failed:', err);
      }
    }

    // Fallback to prompt for web
    if (!folder) {
      folder = prompt('Enter folder path:');
    }

    if (!folder) return;

    setError(null);
    try {
      const result = await settingsService.addScanFolder(folder);
      setSettings(result.settings);
      onSettingsChange?.(result.settings);
      // Auto-scanner wakes up via reload_config() on the backend — no manual scan trigger needed
    } catch (err) {
      console.error('Failed to add scan folder:', err);
      setError('Failed to add scan folder');
    }
  }, [onSettingsChange]);

  /** Open the remove-confirm dialog for the given folder */
  const handleRemoveScanFolder = useCallback((folder: string) => {
    setRemoveConfirmFolder(folder);
  }, []);

  /** Confirm and execute the pending folder removal */
  const handleConfirmRemove = useCallback(async () => {
    if (!removeConfirmFolder) return;
    const folder = removeConfirmFolder;
    setRemoveConfirmFolder(null);
    setError(null);
    try {
      const result = await settingsService.removeScanFolder(folder);
      setSettings(result.settings);
      onSettingsChange?.(result.settings);
    } catch (err) {
      console.error('Failed to remove scan folder:', err);
      setError('Failed to remove scan folder');
    }
  }, [removeConfirmFolder, onSettingsChange]);

  const handleCancelRemove = useCallback(() => {
    setRemoveConfirmFolder(null);
  }, []);

  /** Trigger an immediate library scan on the currently configured folders */
  const handleScanNow = useCallback(async (folders: string[]) => {
    if (folders.length === 0) return;
    setError(null);
    try {
      await settingsService.triggerLibraryScan(folders);
    } catch (err) {
      console.error('Failed to trigger scan:', err);
      setError('Failed to start scan');
    }
  }, []);

  const getValue = useCallback(
    <K extends keyof SettingsUpdate>(key: K): any => {
      if (key in pendingChanges) {
        return pendingChanges[key as keyof SettingsUpdate];
      }
      return settings ? (settings[key as keyof UserSettings] as any) : null;
    },
    [settings, pendingChanges]
  );

  return {
    settings,
    loading,
    pendingChanges,
    isSaving,
    error,
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
  };
};
